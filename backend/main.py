"""
FastAPI backend for ad-free podcast processing.
Handles communication with DGX Spark for audio processing.
Uses SQLite for job storage to work with multiple uvicorn workers.
"""

import hashlib
import os
import sqlite3
from contextlib import contextmanager
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
DB_PATH = Path("jobs.db")


# SQLite job storage (shared across workers)
def init_db():
    """Initialize SQLite database for job tracking."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                episode_id TEXT,
                audio_url TEXT,
                status TEXT DEFAULT 'queued',
                progress INTEGER DEFAULT 0,
                processed_audio_url TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


@contextmanager
def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    """Get job from database."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row:
            return dict(row)
    return None


def update_job(job_id: str, **kwargs):
    """Update job in database."""
    if not kwargs:
        return

    with get_db() as conn:
        sets = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [job_id]
        conn.execute(f"UPDATE jobs SET {sets} WHERE job_id = ?", values)
        conn.commit()


def create_job(job_id: str, episode_id: str, audio_url: str):
    """Create new job in database."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (job_id, episode_id, audio_url, status, progress) VALUES (?, ?, ?, 'queued', 0)",
            (job_id, episode_id, audio_url)
        )
        conn.commit()


# Initialize database on module load
init_db()


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


def process_on_dgx(job_id: str, audio_url: str, title: str, podcast_title: str):
    """Process audio on DGX in background (runs in thread pool)."""
    try:
        update_job(job_id, status="downloading", progress=10)

        # Connect to DGX
        client = get_ssh_client()

        # Create processing command
        # Uses existing fda_mcp container (CUDA 13, faster-whisper pre-installed)
        # Escape single quotes in shell arguments
        safe_podcast_title = podcast_title.replace("'", "'\\''")
        safe_title = title.replace("'", "'\\''")
        safe_audio_url = audio_url.replace("'", "'\\''")

        cmd = f"""docker exec fda_mcp python3 /workspace/podcast_processor/process_podcast.py \\
  '{safe_audio_url}' \\
  --podcast-title '{safe_podcast_title}' \\
  --podcast-description '{safe_title}' \\
  --output /tmp/processed_{job_id}.mp3"""

        update_job(job_id, status="transcribing", progress=30)

        # Execute on DGX
        stdin, stdout, stderr = client.exec_command(cmd, timeout=600)

        # Wait for completion
        exit_status = stdout.channel.recv_exit_status()

        if exit_status != 0:
            error = stderr.read().decode()
            update_job(job_id, status="error", error=error[:500])
            client.close()
            return

        update_job(job_id, status="cutting", progress=80)

        # Copy file from container to host, then download via SFTP
        container_path = f"/tmp/processed_{job_id}.mp3"
        host_path = f"/home/mlifson/processed_{job_id}.mp3"
        local_path = PROCESSED_DIR / f"{job_id}.mp3"

        # Copy from container to DGX host
        copy_cmd = f"docker cp fda_mcp:{container_path} {host_path}"
        stdin, stdout, stderr = client.exec_command(copy_cmd, timeout=60)
        copy_exit = stdout.channel.recv_exit_status()

        if copy_exit != 0:
            error = stderr.read().decode()
            update_job(job_id, status="error", error=f"Failed to copy from container: {error[:200]}")
            client.close()
            return

        # Download from DGX host via SFTP
        sftp = client.open_sftp()
        try:
            sftp.get(host_path, str(local_path))
            # Clean up host file
            client.exec_command(f"rm {host_path}")
        except FileNotFoundError:
            output = stderr.read().decode()
            update_job(job_id, status="error", error=f"Processed file not found on host. Error: {output[:200]}")
            sftp.close()
            client.close()
            return

        sftp.close()
        client.close()

        update_job(
            job_id,
            status="complete",
            progress=100,
            processed_audio_url=f"/audio/{job_id}"
        )

    except paramiko.SSHException as e:
        update_job(job_id, status="error", error=f"SSH error: {str(e)}")
    except Exception as e:
        update_job(job_id, status="error", error=str(e))


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

    # Check if already processing (in database)
    existing_job = get_job(job_id)
    if existing_job:
        return ProcessResponse(
            job_id=job_id,
            status=existing_job["status"],
            progress=existing_job["progress"] or 0,
            processed_audio_url=existing_job.get("processed_audio_url"),
            error=existing_job.get("error")
        )

    # Start new job
    create_job(job_id, request.episode_id, request.audio_url)

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

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return ProcessResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"] or 0,
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

    # Count jobs in database
    with get_db() as conn:
        job_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    return {
        "status": "ok",
        "dgx": dgx_status,
        "jobs": job_count
    }
