#!/usr/bin/env python3
"""
Podcast Ad Removal Pipeline

Downloads a podcast episode, transcribes it with faster-whisper,
identifies ad segments using Ollama, and removes them with ffmpeg.

Usage:
    python process_podcast.py <audio_url_or_path> [--model MODEL] [--output OUTPUT]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests
import torch

# Try OpenAI whisper (GPU support) first, fallback to faster-whisper
try:
    import whisper
    USE_OPENAI_WHISPER = True
except ImportError:
    from faster_whisper import WhisperModel
    USE_OPENAI_WHISPER = False


def parse_timestamp(value) -> float | None:
    """
    Parse timestamp from various formats LLMs may return:
    - "0.0s" -> 0.0
    - "27.5s" -> 27.5
    - 27.5 -> 27.5
    - "27.5" -> 27.5
    - "1:30" or "1:30.5" -> 90.0 or 90.5
    """
    if value is None:
        return None

    # Already a number
    if isinstance(value, (int, float)):
        return float(value)

    # String processing
    if isinstance(value, str):
        # Remove "s" or "sec" suffix
        value = value.strip().lower()
        value = re.sub(r'\s*(s|sec|seconds?)$', '', value)

        # Handle MM:SS or MM:SS.ms format
        if ':' in value:
            parts = value.split(':')
            try:
                if len(parts) == 2:
                    mins, secs = parts
                    return float(mins) * 60 + float(secs)
                elif len(parts) == 3:
                    hours, mins, secs = parts
                    return float(hours) * 3600 + float(mins) * 60 + float(secs)
            except ValueError:
                return None

        # Try direct float conversion
        try:
            return float(value)
        except ValueError:
            return None

    return None


def download_audio(url: str, output_path: str) -> str:
    """Download audio file from URL."""
    print(f"Downloading: {url}")
    start = time.time()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    response = requests.get(url, stream=True, timeout=300, headers=headers)
    response.raise_for_status()

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    elapsed = time.time() - start
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Downloaded {size_mb:.1f}MB in {elapsed:.1f}s")
    return output_path


def transcribe_audio(audio_path: str, whisper_model: str = "base") -> list[dict]:
    """
    Transcribe audio using OpenAI whisper (with GPU) or faster-whisper (CPU fallback).
    Returns list of segments with start, end, and text.
    """
    print(f"Transcribing with whisper model: {whisper_model}")
    start = time.time()

    if USE_OPENAI_WHISPER:
        # OpenAI whisper with GPU support
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using OpenAI whisper on {device.upper()}")
        model = whisper.load_model(whisper_model, device=device)
        result = model.transcribe(audio_path, language="en")

        transcript = []
        for segment in result["segments"]:
            transcript.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip()
            })

        elapsed = time.time() - start
        print(f"Transcription complete in {elapsed:.1f}s ({len(transcript)} segments)")
    else:
        # Faster-whisper fallback
        print("Using faster-whisper (CPU int8)")
        model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, beam_size=1, language="en")

        transcript = []
        for segment in segments:
            transcript.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })

        elapsed = time.time() - start
        duration = info.duration
        rtf = duration / elapsed if elapsed > 0 else 0
        print(f"Transcription complete in {elapsed:.1f}s ({rtf:.1f}x realtime, {len(transcript)} segments)")

    return transcript


def format_transcript_for_llm(transcript: list[dict]) -> str:
    """Format transcript segments for LLM analysis."""
    lines = []
    for seg in transcript:
        timestamp = f"[{seg['start']:.1f}s - {seg['end']:.1f}s]"
        lines.append(f"{timestamp} {seg['text']}")
    return "\n".join(lines)


def chunk_transcript(transcript: list[dict], chunk_duration: float = 300.0) -> list[list[dict]]:
    """
    Split transcript into chunks of approximately chunk_duration seconds.
    This prevents overwhelming the LLM with too much context.
    """
    if not transcript:
        return []

    chunks = []
    current_chunk = []
    chunk_start = 0.0

    for seg in transcript:
        current_chunk.append(seg)
        # Start new chunk when we exceed duration
        if seg["end"] - chunk_start >= chunk_duration:
            chunks.append(current_chunk)
            current_chunk = []
            chunk_start = seg["end"]

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def analyze_chunk_for_ads(
    chunk: list[dict],
    model: str,
    ollama_host: str,
    podcast_context: Optional[dict] = None
) -> list[dict]:
    """Analyze a single transcript chunk for ads."""
    formatted = format_transcript_for_llm(chunk)

    # Build context section if podcast info provided
    context_section = ""
    if podcast_context:
        context_section = f"""
PODCAST CONTEXT (use this to distinguish show content from ads):
- Show: {podcast_context.get('title', 'Unknown')}
- Description: {podcast_context.get('description', 'No description')}
- Typical topics: Content related to the show description is NOT an ad.
- Ads are promotional content for EXTERNAL products/services, not the show itself.

"""

    prompt = f"""You are an expert at identifying advertisements in podcast transcripts.
{context_section}
Analyze this podcast transcript and identify all advertising segments. Ads typically include:
- Sponsor reads ("This episode is brought to you by...", "Thanks to our sponsor...")
- Promo codes and discount offers
- Product pitches and calls to action for EXTERNAL products (not the podcast itself)
- Mid-roll ad breaks (often introduced with "We'll be right back" or similar)
- Mentions of visiting sponsor websites or using coupon codes
- Pre-roll ads at the very START of the episode (before any show content)

IMPORTANT: Podcasts often start DIRECTLY with an ad before any intro music or host greeting.
Look for phrases like "This episode is brought to you by..." at timestamp 0:00.

NOT ADS (keep these):
- Intro/outro music and show theme songs
- Host introductions and episode previews
- Mentions of the podcast's own Patreon, merch, or upcoming episodes
- Listener questions and show segments

IMPORTANT: Return ONLY a valid JSON array of ad segments. Each segment should have "start" and "end" times in seconds.
If no ads are found, return an empty array: []

Example output format:
[{{"start": 125.5, "end": 187.2}}, {{"start": 542.0, "end": 610.5}}]

TRANSCRIPT:
{formatted}

JSON RESPONSE (ad segments only):"""

    response = requests.post(
        f"{ollama_host}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 1024
            }
        },
        timeout=600
    )
    response.raise_for_status()

    result = response.json()
    llm_response = result.get("response", "[]")

    # Extract JSON from response
    json_match = re.search(r'\[[\s\S]*\]', llm_response)
    if json_match:
        try:
            ad_segments = json.loads(json_match.group())
            valid_segments = []
            for seg in ad_segments:
                # Try multiple key names LLMs might use
                # NOTE: Can't use `or` because 0 is a valid timestamp but falsy!
                start_time = seg.get("start")
                if start_time is None:
                    start_time = seg.get("start_time")
                if start_time is None:
                    start_time = seg.get("begin")

                end_time = seg.get("end")
                if end_time is None:
                    end_time = seg.get("end_time")
                if end_time is None:
                    end_time = seg.get("stop")

                # Parse timestamps (handles "0.0s", "1:30", etc.)
                start_parsed = parse_timestamp(start_time)
                end_parsed = parse_timestamp(end_time)

                if start_parsed is not None and end_parsed is not None:
                    valid_segments.append({
                        "start": start_parsed,
                        "end": end_parsed
                    })
                    print(f"    Parsed ad: {start_parsed:.1f}s - {end_parsed:.1f}s")
            return valid_segments
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def identify_ads_with_ollama(
    transcript: list[dict],
    model: str = "qwen3-coder:latest",
    ollama_host: str = "http://localhost:11434",
    chunk_duration: float = 300.0,
    podcast_context: Optional[dict] = None
) -> list[dict]:
    """
    Use Ollama to identify ad segments in transcript.
    Chunks transcript into smaller pieces to avoid overwhelming the model.

    Args:
        transcript: List of {start, end, text} dicts
        model: Ollama model name
        ollama_host: Ollama API URL
        chunk_duration: Seconds per chunk (default 5 min)
        podcast_context: Optional dict with 'title' and 'description' to help
                        distinguish show content from ads

    Returns list of {start, end} dicts for ad segments.
    """
    print(f"Analyzing transcript with Ollama model: {model}")
    if podcast_context:
        print(f"  Using podcast context: {podcast_context.get('title', 'Unknown')}")
    start = time.time()

    # Chunk transcript to avoid context length issues
    chunks = chunk_transcript(transcript, chunk_duration)
    print(f"Split transcript into {len(chunks)} chunks of ~{chunk_duration/60:.0f} min each")

    all_ads = []
    for i, chunk in enumerate(chunks):
        chunk_start = chunk[0]["start"] if chunk else 0
        chunk_end = chunk[-1]["end"] if chunk else 0
        print(f"  Analyzing chunk {i+1}/{len(chunks)} ({chunk_start:.0f}s - {chunk_end:.0f}s)...")

        chunk_ads = analyze_chunk_for_ads(chunk, model, ollama_host, podcast_context)
        if chunk_ads:
            print(f"    Found {len(chunk_ads)} ads in chunk")
            all_ads.extend(chunk_ads)

    elapsed = time.time() - start
    print(f"Found {len(all_ads)} total ad segments in {elapsed:.1f}s")
    return all_ads


def merge_overlapping_segments(segments: list[dict], buffer: float = 0.5) -> list[dict]:
    """Merge overlapping or adjacent ad segments."""
    if not segments:
        return []

    # Sort by start time
    sorted_segs = sorted(segments, key=lambda x: x["start"])
    merged = [sorted_segs[0].copy()]

    for seg in sorted_segs[1:]:
        last = merged[-1]
        # Merge if overlapping or within buffer distance
        if seg["start"] <= last["end"] + buffer:
            last["end"] = max(last["end"], seg["end"])
        else:
            merged.append(seg.copy())

    return merged


def create_ffmpeg_filter(
    ad_segments: list[dict],
    total_duration: float,
    crossfade_ms: int = 50
) -> str:
    """
    Create ffmpeg filter_complex to remove ad segments with crossfade.

    Args:
        ad_segments: List of {start, end} dicts for ad segments
        total_duration: Total audio duration in seconds
        crossfade_ms: Crossfade duration in milliseconds (default 50ms for subtle transition)

    Returns filter string for concatenating non-ad segments with crossfade.
    Note: We must re-encode (can't stream copy) because we're applying filters.
    Using crossfade avoids jarring cuts when ads are removed.
    """
    if not ad_segments:
        return ""

    # Build list of segments to KEEP (inverse of ad segments)
    keep_segments = []
    current_pos = 0.0

    for ad in ad_segments:
        if ad["start"] > current_pos:
            keep_segments.append({"start": current_pos, "end": ad["start"]})
        current_pos = ad["end"]

    # Add final segment after last ad
    if current_pos < total_duration:
        keep_segments.append({"start": current_pos, "end": total_duration})

    if not keep_segments:
        return ""

    # If only one segment, no crossfade needed
    if len(keep_segments) == 1:
        seg = keep_segments[0]
        return f"[0:a]atrim=start={seg['start']:.3f}:end={seg['end']:.3f},asetpts=PTS-STARTPTS[out]"

    # Build filter_complex with crossfade between segments
    # Crossfade creates smoother transitions where ads were removed
    crossfade_sec = crossfade_ms / 1000.0
    filter_parts = []

    # First, trim all segments
    for i, seg in enumerate(keep_segments):
        filter_parts.append(
            f"[0:a]atrim=start={seg['start']:.3f}:end={seg['end']:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )

    # Chain crossfades: a0 x a1 -> t0, t0 x a2 -> t1, etc.
    current_output = "[a0]"
    for i in range(1, len(keep_segments)):
        next_input = f"[a{i}]"
        if i == len(keep_segments) - 1:
            # Last crossfade outputs to [out]
            output = "[out]"
        else:
            output = f"[t{i-1}]"

        filter_parts.append(
            f"{current_output}{next_input}acrossfade=d={crossfade_sec:.3f}:c1=tri:c2=tri{output}"
        )
        current_output = output if output != "[out]" else None

    return ";".join(filter_parts)


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ],
        capture_output=True,
        text=True,
        check=True
    )
    return float(result.stdout.strip())


def remove_ads_with_ffmpeg(
    input_path: str,
    output_path: str,
    ad_segments: list[dict]
) -> str:
    """Remove ad segments from audio using ffmpeg."""
    print(f"Removing {len(ad_segments)} ad segments with ffmpeg")
    start = time.time()

    if not ad_segments:
        # No ads to remove, just copy
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path],
            check=True,
            capture_output=True
        )
        return output_path

    # Get total duration
    duration = get_audio_duration(input_path)

    # Merge overlapping segments
    merged_ads = merge_overlapping_segments(ad_segments)

    # Calculate total ad time
    total_ad_time = sum(ad["end"] - ad["start"] for ad in merged_ads)
    print(f"Total ad time: {total_ad_time:.1f}s ({total_ad_time/duration*100:.1f}% of episode)")

    # Create filter
    filter_complex = create_ffmpeg_filter(merged_ads, duration)

    if not filter_complex:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path],
            check=True,
            capture_output=True
        )
        return output_path

    # Run ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame",
        "-q:a", "2",
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    elapsed = time.time() - start
    new_duration = get_audio_duration(output_path)
    print(f"Processing complete in {elapsed:.1f}s")
    print(f"Original: {duration:.1f}s -> Clean: {new_duration:.1f}s (removed {duration-new_duration:.1f}s)")

    return output_path


def process_podcast(
    audio_source: str,
    output_path: Optional[str] = None,
    whisper_model: str = "tiny",
    ollama_model: str = "qwen3-coder:latest",
    keep_intermediate: bool = False,
    podcast_context: Optional[dict] = None
) -> dict:
    """
    Main pipeline: download, transcribe, identify ads, remove ads.

    Args:
        audio_source: URL or local path to podcast audio
        output_path: Where to save cleaned audio
        whisper_model: Whisper model size for transcription
        ollama_model: Ollama model for ad detection
        keep_intermediate: Keep temp files after processing
        podcast_context: Optional dict with 'title' and 'description' to help
                        distinguish show content from ads

    Returns dict with timing stats and results.
    """
    stats = {
        "source": audio_source,
        "whisper_model": whisper_model,
        "ollama_model": ollama_model,
        "podcast_context": podcast_context,
        "timings": {},
        "ad_segments": [],
        "output_path": None
    }

    total_start = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Get audio file
        if audio_source.startswith(("http://", "https://")):
            raw_audio = os.path.join(tmpdir, "raw.mp3")
            t0 = time.time()
            download_audio(audio_source, raw_audio)
            stats["timings"]["download"] = time.time() - t0
        else:
            raw_audio = audio_source
            stats["timings"]["download"] = 0

        # Step 2: Transcribe
        t0 = time.time()
        transcript = transcribe_audio(raw_audio, whisper_model)
        stats["timings"]["transcribe"] = time.time() - t0
        stats["transcript_segments"] = len(transcript)

        # Step 3: Identify ads
        t0 = time.time()
        ad_segments = identify_ads_with_ollama(
            transcript,
            ollama_model,
            podcast_context=podcast_context
        )
        stats["timings"]["ad_detection"] = time.time() - t0
        stats["ad_segments"] = ad_segments

        # Step 4: Remove ads
        if output_path is None:
            base = Path(audio_source).stem if not audio_source.startswith("http") else "podcast"
            output_path = f"{base}_clean.mp3"

        t0 = time.time()
        remove_ads_with_ffmpeg(raw_audio, output_path, ad_segments)
        stats["timings"]["ffmpeg"] = time.time() - t0
        stats["output_path"] = output_path

    stats["timings"]["total"] = time.time() - total_start

    return stats


def print_stats(stats: dict):
    """Print processing statistics."""
    print("\n" + "="*60)
    print("PROCESSING SUMMARY")
    print("="*60)
    print(f"Source: {stats['source']}")
    if stats.get('podcast_context'):
        ctx = stats['podcast_context']
        print(f"Podcast: {ctx.get('title', 'Unknown')}")
    print(f"Whisper model: {stats['whisper_model']}")
    print(f"Ollama model: {stats['ollama_model']}")
    print(f"Transcript segments: {stats.get('transcript_segments', 'N/A')}")
    print(f"Ad segments found: {len(stats['ad_segments'])}")
    print(f"Output: {stats['output_path']}")
    print("\nTimings:")
    for step, duration in stats["timings"].items():
        print(f"  {step}: {duration:.1f}s")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="Remove ads from podcast episodes")
    parser.add_argument("audio", help="URL or path to podcast audio file")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--whisper-model", "-w", default="base",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--ollama-model", "-m", default="qwen3-coder:latest",
                        help="Ollama model for ad detection (default: qwen3-coder:latest)")
    parser.add_argument("--keep-intermediate", "-k", action="store_true",
                        help="Keep intermediate files")
    parser.add_argument("--podcast-title", "-t",
                        help="Podcast title to help distinguish show content from ads")
    parser.add_argument("--podcast-description", "-d",
                        help="Podcast description to help identify show topics vs ads")

    args = parser.parse_args()

    # Build podcast context if title or description provided
    podcast_context = None
    if args.podcast_title or args.podcast_description:
        podcast_context = {
            "title": args.podcast_title or "Unknown",
            "description": args.podcast_description or "No description"
        }

    stats = process_podcast(
        audio_source=args.audio,
        output_path=args.output,
        whisper_model=args.whisper_model,
        ollama_model=args.ollama_model,
        keep_intermediate=args.keep_intermediate,
        podcast_context=podcast_context
    )

    print_stats(stats)

    # Output JSON stats for programmatic use
    print("\nJSON Stats:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
