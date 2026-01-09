"""
FastAPI backend for ad-free podcast processing.
Handles communication with DGX Spark for audio processing.
"""

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Optional

import paramiko
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Ad-Free Podcast API")

# CORS for SvelteKit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DGX_HOST = os.getenv("DGX_HOST", "192.168.4.62")
DGX_USER = os.getenv("DGX_USER", "mlifson")
DGX_PASSWORD = os.getenv("DGX_PASSWORD", "")
PROCESSED_DIR = Path("processed")
PROCESSED_DIR.mkdir(exist_ok=True)

# In-memory job tracking
jobs: dict[str, dict] = {}


class ProcessRequest(BaseModel):
    episode_id: str
    audio_url: str
    title: str
    podcast_title: str


class ProcessResponse(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    processed_audio_url: Optional[str] = None
    ads_removed: Optional[float] = None
    duration: Optional[float] = None
    error: Optional[str] = None


def get_ssh_client() -> paramiko.SSHClient:
    """Create SSH connection to DGX."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        DGX_HOST,
        username=DGX_USER,
        password=DGX_PASSWORD,
        timeout=30
    )
    return client


def generate_job_id(episode_id: str, audio_url: str) -> str:
    """Generate deterministic job ID from episode and URL."""
    content = f"{episode_id}:{audio_url}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]


async def process_on_dgx(job_id: str, audio_url: str, title: str, podcast_title: str):
    """Process audio on DGX in background."""
    try:
        jobs[job_id]["status"] = "downloading"
        jobs[job_id]["progress"] = 10

        # Connect to DGX
        client = get_ssh_client()

        # Create processing command
        # Uses Docker with NGC PyTorch container for GPU whisper
        cmd = f"""
cd ~/podcast_processor && \\
docker run --rm --gpus all --network host --ipc=host \\
  -v ~/podcast_processor:/workspace \\
  -v /tmp:/tmp \\
  nvcr.io/nvidia/pytorch:25.12-py3 \\
  bash -c "apt-get update -qq && apt-get install -qq -y ffmpeg > /dev/null 2>&1 && \\
           pip install -q openai-whisper requests && \\
           python /workspace/process_podcast.py \\
             --url '{audio_url}' \\
             --podcast-title '{podcast_title}' \\
             --podcast-description '{title}' \\
             --output /tmp/processed_{job_id}.mp3"
"""

        jobs[job_id]["status"] = "transcribing"
        jobs[job_id]["progress"] = 30

        # Execute on DGX
        stdin, stdout, stderr = client.exec_command(cmd, timeout=600)

        # Wait for completion
        exit_status = stdout.channel.recv_exit_status()

        if exit_status != 0:
            error = stderr.read().decode()
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = error[:500]
            client.close()
            return

        jobs[job_id]["status"] = "cutting"
        jobs[job_id]["progress"] = 80

        # Download processed file
        sftp = client.open_sftp()
        remote_path = f"/tmp/processed_{job_id}.mp3"
        local_path = PROCESSED_DIR / f"{job_id}.mp3"

        try:
            sftp.get(remote_path, str(local_path))
        except FileNotFoundError:
            # File might be named differently, try original output path
            output = stdout.read().decode()
            # Parse output to find actual file path
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = f"Processed file not found. Output: {output[:200]}"
            sftp.close()
            client.close()
            return

        sftp.close()
        client.close()

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["processed_audio_url"] = f"/audio/{job_id}"

        # TODO: Parse output for actual duration and ads removed

    except paramiko.SSHException as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = f"SSH error: {str(e)}"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.post("/process", response_model=ProcessResponse)
async def process_episode(
    request: ProcessRequest,
    background_tasks: BackgroundTasks
):
    """Start processing an episode to remove ads."""
    job_id = generate_job_id(request.episode_id, request.audio_url)

    # Check if already processed
    local_path = PROCESSED_DIR / f"{job_id}.mp3"
    if local_path.exists():
        return ProcessResponse(
            job_id=job_id,
            status="complete",
            progress=100,
            processed_audio_url=f"/audio/{job_id}"
        )

    # Check if already processing
    if job_id in jobs:
        job = jobs[job_id]
        return ProcessResponse(
            job_id=job_id,
            status=job["status"],
            progress=job.get("progress", 0),
            processed_audio_url=job.get("processed_audio_url"),
            error=job.get("error")
        )

    # Start new job
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "episode_id": request.episode_id,
        "audio_url": request.audio_url
    }

    background_tasks.add_task(
        process_on_dgx,
        job_id,
        request.audio_url,
        request.title,
        request.podcast_title
    )

    return ProcessResponse(
        job_id=job_id,
        status="queued",
        progress=0
    )


@app.get("/status/{job_id}", response_model=ProcessResponse)
async def get_status(job_id: str):
    """Get processing job status."""
    # Check if file exists (completed in previous session)
    local_path = PROCESSED_DIR / f"{job_id}.mp3"
    if local_path.exists():
        return ProcessResponse(
            job_id=job_id,
            status="complete",
            progress=100,
            processed_audio_url=f"/audio/{job_id}"
        )

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return ProcessResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", 0),
        processed_audio_url=job.get("processed_audio_url"),
        error=job.get("error")
    )


@app.get("/audio/{job_id}")
async def get_audio(job_id: str):
    """Serve processed audio file."""
    local_path = PROCESSED_DIR / f"{job_id}.mp3"

    if not local_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        local_path,
        media_type="audio/mpeg",
        filename=f"{job_id}.mp3"
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Try DGX connection
    dgx_status = "unknown"
    try:
        client = get_ssh_client()
        client.close()
        dgx_status = "connected"
    except Exception as e:
        dgx_status = f"error: {str(e)[:50]}"

    return {
        "status": "ok",
        "dgx": dgx_status,
        "jobs": len(jobs)
    }
