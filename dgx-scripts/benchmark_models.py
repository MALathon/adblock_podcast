#!/usr/bin/env python3
"""
Benchmark different model combinations for ad removal pipeline.

Tests various Whisper and Ollama model combinations to find
the best balance of speed and quality.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent))
from process_podcast import process_podcast, transcribe_audio, identify_ads_with_ollama

# Test configurations
WHISPER_MODELS = ["tiny", "base", "small"]
OLLAMA_MODELS = ["hermes3:8b", "hermes3:70b", "llama3.1:70b"]

# Sample podcast URL (short episode with known ads for testing)
# You can replace this with any podcast URL
SAMPLE_URL = "https://www.podtrac.com/pts/redirect.mp3/pdst.fm/e/chrt.fm/track/524GE/traffic.megaphone.fm/VMP3891942786.mp3"


def benchmark_transcription(audio_path: str) -> dict:
    """Benchmark Whisper model transcription times."""
    results = {}

    for model in WHISPER_MODELS:
        print(f"\nTesting Whisper model: {model}")
        start = time.time()
        try:
            transcript = transcribe_audio(audio_path, model)
            elapsed = time.time() - start
            results[model] = {
                "time": elapsed,
                "segments": len(transcript),
                "status": "success"
            }
            print(f"  {model}: {elapsed:.1f}s ({len(transcript)} segments)")
        except Exception as e:
            results[model] = {
                "time": 0,
                "status": "error",
                "error": str(e)
            }
            print(f"  {model}: ERROR - {e}")

    return results


def benchmark_ad_detection(transcript: list[dict]) -> dict:
    """Benchmark Ollama model ad detection times."""
    results = {}

    for model in OLLAMA_MODELS:
        print(f"\nTesting Ollama model: {model}")
        start = time.time()
        try:
            ads = identify_ads_with_ollama(transcript, model)
            elapsed = time.time() - start
            results[model] = {
                "time": elapsed,
                "ads_found": len(ads),
                "ad_segments": ads,
                "status": "success"
            }
            print(f"  {model}: {elapsed:.1f}s ({len(ads)} ads found)")
        except Exception as e:
            results[model] = {
                "time": 0,
                "status": "error",
                "error": str(e)
            }
            print(f"  {model}: ERROR - {e}")

    return results


def run_full_benchmark(audio_url: str) -> dict:
    """Run complete benchmark of all model combinations."""
    import tempfile
    import requests

    print("="*60)
    print("PODCAST AD REMOVAL BENCHMARK")
    print("="*60)

    results = {
        "audio_url": audio_url,
        "whisper_benchmarks": {},
        "ollama_benchmarks": {},
        "full_pipeline": {}
    }

    # Download sample audio first
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        print(f"\nDownloading sample audio...")
        response = requests.get(audio_url, stream=True, timeout=300)
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)
        audio_path = tmp.name
        print(f"Downloaded to: {audio_path}")

    try:
        # Benchmark Whisper models
        print("\n" + "-"*40)
        print("WHISPER TRANSCRIPTION BENCHMARKS")
        print("-"*40)
        results["whisper_benchmarks"] = benchmark_transcription(audio_path)

        # Use best whisper model for Ollama benchmarks
        best_whisper = min(
            [(k, v) for k, v in results["whisper_benchmarks"].items() if v.get("status") == "success"],
            key=lambda x: x[1]["time"]
        )[0]
        print(f"\nUsing {best_whisper} for Ollama benchmarks (fastest)")

        # Get transcript with best model
        transcript = transcribe_audio(audio_path, best_whisper)

        # Benchmark Ollama models
        print("\n" + "-"*40)
        print("OLLAMA AD DETECTION BENCHMARKS")
        print("-"*40)
        results["ollama_benchmarks"] = benchmark_ad_detection(transcript)

        # Full pipeline test with recommended config
        print("\n" + "-"*40)
        print("FULL PIPELINE TEST")
        print("-"*40)

        # Test with small+hermes3:8b (fast) and base+llama3.1:70b (quality)
        configs = [
            ("tiny", "hermes3:8b", "fast"),
            ("base", "llama3.1:70b", "quality"),
        ]

        for whisper, ollama, label in configs:
            print(f"\nTesting {label} config: whisper={whisper}, ollama={ollama}")
            output_path = f"/tmp/benchmark_{label}_output.mp3"
            start = time.time()
            try:
                stats = process_podcast(
                    audio_source=audio_path,
                    output_path=output_path,
                    whisper_model=whisper,
                    ollama_model=ollama
                )
                results["full_pipeline"][label] = {
                    "config": {"whisper": whisper, "ollama": ollama},
                    "total_time": stats["timings"]["total"],
                    "timings": stats["timings"],
                    "ads_found": len(stats["ad_segments"]),
                    "status": "success"
                }
            except Exception as e:
                results["full_pipeline"][label] = {
                    "config": {"whisper": whisper, "ollama": ollama},
                    "status": "error",
                    "error": str(e)
                }

    finally:
        # Cleanup
        os.unlink(audio_path)

    # Summary
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)

    print("\nWhisper Model Times:")
    for model, data in results["whisper_benchmarks"].items():
        if data.get("status") == "success":
            print(f"  {model}: {data['time']:.1f}s")

    print("\nOllama Model Times:")
    for model, data in results["ollama_benchmarks"].items():
        if data.get("status") == "success":
            print(f"  {model}: {data['time']:.1f}s ({data['ads_found']} ads)")

    print("\nFull Pipeline:")
    for label, data in results["full_pipeline"].items():
        if data.get("status") == "success":
            print(f"  {label}: {data['total_time']:.1f}s total ({data['ads_found']} ads)")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark ad removal pipeline")
    parser.add_argument("--url", default=SAMPLE_URL,
                        help="URL of podcast to test with")
    parser.add_argument("--output", "-o", help="Save results to JSON file")

    args = parser.parse_args()

    results = run_full_benchmark(args.url)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    print("\nJSON Results:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
