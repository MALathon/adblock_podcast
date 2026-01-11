#!/usr/bin/env python3
"""
Transcription Quality Benchmark

Compares faster Whisper models against distil-large-v3 (ground truth).
Measures: Speed (RTF), Quality (WER), Memory usage.

Uses HuggingFace transformers for all models (GPU compatible).
"""

import json
import os
import time
import subprocess
from dataclasses import dataclass
from typing import Optional
import difflib
import sys


@dataclass
class BenchmarkResult:
    model_name: str
    audio_file: str
    audio_duration: float
    transcription_time: float
    rtf: float  # Realtime factor (higher = faster)
    word_count: int
    wer: float  # Word Error Rate vs ground truth
    transcript: str
    error: Optional[str] = None


def get_audio_duration(audio_path: str) -> float:
    """Get audio file duration using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 0.0


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Calculate Word Error Rate between reference and hypothesis.
    WER = (S + D + I) / N where S=substitutions, D=deletions, I=insertions, N=words in reference
    """
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    if not ref_words:
        return 1.0 if hyp_words else 0.0

    # Use difflib for alignment
    matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)

    # Count operations
    substitutions = 0
    deletions = 0
    insertions = 0

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'replace':
            substitutions += max(i2 - i1, j2 - j1)
        elif op == 'delete':
            deletions += i2 - i1
        elif op == 'insert':
            insertions += j2 - j1

    wer = (substitutions + deletions + insertions) / len(ref_words)
    return min(wer, 1.0)  # Cap at 100%


# Model ID mappings for HuggingFace
MODEL_IDS = {
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large-v3": "openai/whisper-large-v3",
    "large-v3-turbo": "openai/whisper-large-v3-turbo",
    "distil-large-v3": "distil-whisper/distil-large-v3",
    "distil-medium": "distil-whisper/distil-medium.en",
    "distil-small": "distil-whisper/distil-small.en",
}


def transcribe_with_transformers(audio_path: str, model_id: str) -> tuple[str, float]:
    """Transcribe using HuggingFace transformers pipeline."""
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    print(f"    Loading {model_id}...", flush=True)

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    model.to(device)

    processor = AutoProcessor.from_pretrained(model_id)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch_dtype,
        device=device,
    )

    print(f"    Transcribing...", flush=True)
    start = time.time()
    result = pipe(audio_path, return_timestamps=True)
    elapsed = time.time() - start

    text = result.get("text", "")

    # Clean up GPU memory
    del model, pipe
    try:
        import torch
        torch.cuda.empty_cache()
    except:
        pass

    return text, elapsed


def benchmark_model(
    audio_path: str,
    model_name: str,
    ground_truth: Optional[str] = None
) -> BenchmarkResult:
    """Benchmark a single model on an audio file."""

    audio_duration = get_audio_duration(audio_path)

    try:
        model_id = MODEL_IDS.get(model_name, model_name)
        transcript, elapsed = transcribe_with_transformers(audio_path, model_id)

        rtf = audio_duration / elapsed if elapsed > 0 else 0
        word_count = len(transcript.split())

        # Calculate WER if ground truth provided
        wer = calculate_wer(ground_truth, transcript) if ground_truth else 0.0

        return BenchmarkResult(
            model_name=model_name,
            audio_file=os.path.basename(audio_path),
            audio_duration=audio_duration,
            transcription_time=elapsed,
            rtf=rtf,
            word_count=word_count,
            wer=wer,
            transcript=transcript,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return BenchmarkResult(
            model_name=model_name,
            audio_file=os.path.basename(audio_path),
            audio_duration=audio_duration,
            transcription_time=0,
            rtf=0,
            word_count=0,
            wer=1.0,
            transcript="",
            error=str(e),
        )


def run_benchmark(audio_files: list[str], output_file: str = "transcription_benchmark_results.json"):
    """Run full benchmark suite."""

    # Models to test (ordered by expected speed, fastest first)
    # All use HuggingFace transformers for GPU compatibility
    models = [
        "tiny",              # Fastest, lowest quality (39M params)
        "base",              # Fast (74M params)
        "small",             # Balanced (244M params)
        "distil-small",      # Distilled small - English only
        "distil-medium",     # Distilled medium - English only
        "distil-large-v3",   # Distilled large - high quality (756M params)
        "large-v3-turbo",    # Turbo variant (809M params)
    ]

    all_results = []

    print("=" * 70, flush=True)
    print("TRANSCRIPTION QUALITY BENCHMARK", flush=True)
    print("=" * 70, flush=True)
    print(f"Testing {len(models)} models on {len(audio_files)} audio files", flush=True)
    print(f"Ground truth model: distil-large-v3", flush=True)
    print("=" * 70, flush=True)
    sys.stdout.flush()

    for audio_path in audio_files:
        print(f"\n{'='*70}", flush=True)
        print(f"Audio: {os.path.basename(audio_path)}", flush=True)
        duration = get_audio_duration(audio_path)
        print(f"Duration: {duration:.0f}s ({duration/60:.1f} min)", flush=True)
        print("=" * 70, flush=True)
        sys.stdout.flush()

        # First, get ground truth transcription
        print(f"\n[Ground Truth] distil-large-v3", flush=True)
        gt_result = benchmark_model(audio_path, "distil-large-v3")

        if gt_result.error:
            print(f"  ERROR: {gt_result.error}", flush=True)
            continue

        print(f"  Time: {gt_result.transcription_time:.1f}s", flush=True)
        print(f"  RTF: {gt_result.rtf:.1f}x", flush=True)
        print(f"  Words: {gt_result.word_count}", flush=True)
        sys.stdout.flush()

        ground_truth_text = gt_result.transcript
        gt_result.wer = 0.0  # Ground truth has 0% WER by definition
        all_results.append(gt_result)

        # Test other models
        for model in models:
            if model == "distil-large-v3":
                continue  # Already done as ground truth

            print(f"\n[Testing] {model}", flush=True)
            sys.stdout.flush()
            result = benchmark_model(audio_path, model, ground_truth_text)

            if result.error:
                print(f"  ERROR: {result.error}", flush=True)
            else:
                print(f"  Time: {result.transcription_time:.1f}s", flush=True)
                print(f"  RTF: {result.rtf:.1f}x", flush=True)
                print(f"  Words: {result.word_count}", flush=True)
                print(f"  WER: {result.wer:.1%}", flush=True)
            sys.stdout.flush()

            all_results.append(result)

    # Summary table
    print("\n" + "=" * 90, flush=True)
    print("SUMMARY: SPEED VS QUALITY", flush=True)
    print("=" * 90, flush=True)
    print(f"{'Model':<20} {'RTF':>8} {'Time':>10} {'WER':>10} {'Words':>8} {'Status':<10}", flush=True)
    print("-" * 90, flush=True)

    # Group by model and average
    model_stats = {}
    for r in all_results:
        if r.model_name not in model_stats:
            model_stats[r.model_name] = {"rtf": [], "time": [], "wer": [], "words": [], "errors": 0}

        if r.error:
            model_stats[r.model_name]["errors"] += 1
        else:
            model_stats[r.model_name]["rtf"].append(r.rtf)
            model_stats[r.model_name]["time"].append(r.transcription_time)
            model_stats[r.model_name]["wer"].append(r.wer)
            model_stats[r.model_name]["words"].append(r.word_count)

    # Sort by RTF (fastest first)
    sorted_models = sorted(
        model_stats.items(),
        key=lambda x: sum(x[1]["rtf"]) / len(x[1]["rtf"]) if x[1]["rtf"] else 0,
        reverse=True
    )

    for model, stats in sorted_models:
        if stats["rtf"]:
            avg_rtf = sum(stats["rtf"]) / len(stats["rtf"])
            avg_time = sum(stats["time"]) / len(stats["time"])
            avg_wer = sum(stats["wer"]) / len(stats["wer"])
            avg_words = sum(stats["words"]) / len(stats["words"])
            status = "OK"
        else:
            avg_rtf = avg_time = avg_wer = avg_words = 0
            status = "FAILED"

        print(f"{model:<20} {avg_rtf:>7.1f}x {avg_time:>9.1f}s {avg_wer:>9.1%} {avg_words:>8.0f} {status:<10}", flush=True)

    print("=" * 90, flush=True)
    print("RTF = Realtime Factor (higher = faster)", flush=True)
    print("WER = Word Error Rate vs distil-large-v3 (lower = better, 0% = identical)", flush=True)
    print("=" * 90, flush=True)

    # Recommendation
    print("\nRECOMMENDATION:", flush=True)
    best_fast = None
    for model, stats in sorted_models:
        if stats["wer"] and model != "distil-large-v3":
            avg_wer = sum(stats["wer"]) / len(stats["wer"])
            avg_rtf = sum(stats["rtf"]) / len(stats["rtf"])
            # Find fastest model with <15% WER (allowing some tolerance)
            if avg_wer < 0.15:
                if best_fast is None or avg_rtf > best_fast[1]:
                    best_fast = (model, avg_rtf, avg_wer)

    if best_fast:
        print(f"  BEST FAST MODEL with <15% WER: {best_fast[0]}", flush=True)
        print(f"  Speed: {best_fast[1]:.1f}x RTF", flush=True)
        print(f"  Quality: {best_fast[2]:.1%} WER vs distil-large-v3", flush=True)
        speedup = best_fast[1] / (sum(model_stats["distil-large-v3"]["rtf"]) / len(model_stats["distil-large-v3"]["rtf"]))
        print(f"  Speedup: {speedup:.1f}x faster than distil-large-v3", flush=True)
    else:
        print("  No model found with <15% WER. Stick with distil-large-v3.", flush=True)

    sys.stdout.flush()

    # Save results
    results_data = {
        "summary": {
            model: {
                "avg_rtf": sum(stats["rtf"]) / len(stats["rtf"]) if stats["rtf"] else 0,
                "avg_time": sum(stats["time"]) / len(stats["time"]) if stats["time"] else 0,
                "avg_wer": sum(stats["wer"]) / len(stats["wer"]) if stats["wer"] else 0,
                "avg_words": sum(stats["words"]) / len(stats["words"]) if stats["words"] else 0,
                "errors": stats["errors"],
            }
            for model, stats in model_stats.items()
        },
        "detailed_results": [
            {
                "model": r.model_name,
                "audio_file": r.audio_file,
                "audio_duration": r.audio_duration,
                "transcription_time": r.transcription_time,
                "rtf": r.rtf,
                "word_count": r.word_count,
                "wer": r.wer,
                "error": r.error,
            }
            for r in all_results
        ],
        "recommendation": {
            "model": best_fast[0] if best_fast else "distil-large-v3",
            "rtf": best_fast[1] if best_fast else 0,
            "wer": best_fast[2] if best_fast else 0,
        } if best_fast else {"model": "distil-large-v3", "rtf": 0, "wer": 0}
    }

    with open(output_file, "w") as f:
        json.dump(results_data, f, indent=2)

    print(f"\nResults saved to: {output_file}", flush=True)

    return results_data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark transcription models")
    parser.add_argument("audio_files", nargs="+", help="Audio files to test")
    parser.add_argument("--output", "-o", default="transcription_benchmark_results.json",
                        help="Output JSON file")

    args = parser.parse_args()

    # Verify files exist
    valid_files = []
    for f in args.audio_files:
        if os.path.exists(f):
            valid_files.append(f)
        else:
            print(f"Warning: File not found: {f}")

    if not valid_files:
        print("No valid audio files found!")
        return

    run_benchmark(valid_files, args.output)


if __name__ == "__main__":
    main()
