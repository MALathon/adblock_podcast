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
from faster_whisper import WhisperModel


def download_audio(url: str, output_path: str) -> str:
    """Download audio file from URL."""
    print(f"Downloading: {url}")
    start = time.time()

    response = requests.get(url, stream=True, timeout=300)
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
    Transcribe audio using faster-whisper.
    Returns list of segments with start, end, and text.
    """
    print(f"Transcribing with whisper model: {whisper_model}")
    start = time.time()

    model = WhisperModel(whisper_model, device="cuda", compute_type="float16")
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)

    transcript = []
    for segment in segments:
        transcript.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        })

    elapsed = time.time() - start
    print(f"Transcription complete in {elapsed:.1f}s ({len(transcript)} segments)")
    return transcript


def format_transcript_for_llm(transcript: list[dict]) -> str:
    """Format transcript segments for LLM analysis."""
    lines = []
    for seg in transcript:
        timestamp = f"[{seg['start']:.1f}s - {seg['end']:.1f}s]"
        lines.append(f"{timestamp} {seg['text']}")
    return "\n".join(lines)


def identify_ads_with_ollama(
    transcript: list[dict],
    model: str = "llama3.1:70b",
    ollama_host: str = "http://localhost:11434"
) -> list[dict]:
    """
    Use Ollama to identify ad segments in transcript.
    Returns list of {start, end} dicts for ad segments.
    """
    print(f"Analyzing transcript with Ollama model: {model}")
    start = time.time()

    formatted_transcript = format_transcript_for_llm(transcript)

    prompt = f"""You are an expert at identifying advertisements in podcast transcripts.

Analyze this podcast transcript and identify all advertising segments. Ads typically include:
- Sponsor reads ("This episode is brought to you by...", "Thanks to our sponsor...")
- Promo codes and discount offers
- Product pitches and calls to action
- Mid-roll ad breaks (often introduced with "We'll be right back" or similar)
- Mentions of visiting sponsor websites or using coupon codes

IMPORTANT: Return ONLY a valid JSON array of ad segments. Each segment should have "start" and "end" times in seconds.
If no ads are found, return an empty array: []

Example output format:
[{{"start": 125.5, "end": 187.2}}, {{"start": 542.0, "end": 610.5}}]

TRANSCRIPT:
{formatted_transcript}

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

    # Extract JSON from response (handle markdown code blocks)
    json_match = re.search(r'\[.*?\]', llm_response, re.DOTALL)
    if json_match:
        try:
            ad_segments = json.loads(json_match.group())
            elapsed = time.time() - start
            print(f"Found {len(ad_segments)} ad segments in {elapsed:.1f}s")
            return ad_segments
        except json.JSONDecodeError:
            print(f"Warning: Could not parse LLM response as JSON: {llm_response[:200]}")
            return []

    print("Warning: No JSON array found in LLM response")
    return []


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


def create_ffmpeg_filter(ad_segments: list[dict], total_duration: float) -> str:
    """
    Create ffmpeg filter_complex to remove ad segments.
    Returns filter string for concatenating non-ad segments.
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

    # Build filter_complex string
    filter_parts = []
    concat_inputs = []

    for i, seg in enumerate(keep_segments):
        # Create trim filter for each segment
        filter_parts.append(
            f"[0:a]atrim=start={seg['start']:.3f}:end={seg['end']:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )
        concat_inputs.append(f"[a{i}]")

    # Concatenate all segments
    concat_input_str = "".join(concat_inputs)
    filter_parts.append(f"{concat_input_str}concat=n={len(keep_segments)}:v=0:a=1[out]")

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
    whisper_model: str = "base",
    ollama_model: str = "llama3.1:70b",
    keep_intermediate: bool = False
) -> dict:
    """
    Main pipeline: download, transcribe, identify ads, remove ads.

    Returns dict with timing stats and results.
    """
    stats = {
        "source": audio_source,
        "whisper_model": whisper_model,
        "ollama_model": ollama_model,
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
        ad_segments = identify_ads_with_ollama(transcript, ollama_model)
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
    parser.add_argument("--ollama-model", "-m", default="llama3.1:70b",
                        help="Ollama model for ad detection (default: llama3.1:70b)")
    parser.add_argument("--keep-intermediate", "-k", action="store_true",
                        help="Keep intermediate files")

    args = parser.parse_args()

    stats = process_podcast(
        audio_source=args.audio,
        output_path=args.output,
        whisper_model=args.whisper_model,
        ollama_model=args.ollama_model,
        keep_intermediate=args.keep_intermediate
    )

    print_stats(stats)

    # Output JSON stats for programmatic use
    print("\nJSON Stats:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
