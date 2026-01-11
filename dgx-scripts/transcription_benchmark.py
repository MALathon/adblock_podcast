#!/usr/bin/env python3
"""
Transcription Model Benchmark

Tests multiple transcription models for speed and accuracy:
1. faster-whisper (base, small, medium, large-v3)
2. faster-whisper turbo (large-v3-turbo)
3. insanely-fast-whisper
4. NVIDIA Parakeet/Canary
5. distil-whisper
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Optional
import tempfile


@dataclass
class BenchmarkResult:
    model_name: str
    audio_duration: float  # seconds
    transcription_time: float  # seconds
    realtime_factor: float  # audio_duration / transcription_time
    memory_used_gb: float
    word_count: int
    sample_text: str
    error: Optional[str] = None


class TranscriptionBenchmark:
    """Benchmark different transcription models."""

    def __init__(self, output_dir: str = "/tmp/transcription_benchmark"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def get_audio_duration(self, audio_path: str) -> float:
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

    def benchmark_faster_whisper(
        self,
        audio_path: str,
        model_size: str = "base",
        device: str = "cuda",
        compute_type: str = "float16",
    ) -> BenchmarkResult:
        """Benchmark faster-whisper."""
        from faster_whisper import WhisperModel

        audio_duration = self.get_audio_duration(audio_path)

        print(f"  Loading faster-whisper {model_size}...")
        start_load = time.time()
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        load_time = time.time() - start_load
        print(f"  Model loaded in {load_time:.1f}s")

        print(f"  Transcribing...")
        start_time = time.time()
        segments, info = model.transcribe(audio_path, beam_size=5)

        # Collect all text
        all_text = []
        word_count = 0
        for segment in segments:
            all_text.append(segment.text)
            word_count += len(segment.text.split())

        transcription_time = time.time() - start_time
        full_text = " ".join(all_text)

        # Get memory usage
        try:
            import torch
            memory_gb = torch.cuda.max_memory_allocated() / 1e9 if torch.cuda.is_available() else 0
        except:
            memory_gb = 0

        return BenchmarkResult(
            model_name=f"faster-whisper-{model_size}",
            audio_duration=audio_duration,
            transcription_time=transcription_time,
            realtime_factor=audio_duration / transcription_time if transcription_time > 0 else 0,
            memory_used_gb=memory_gb,
            word_count=word_count,
            sample_text=full_text[:500] + "...",
        )

    def benchmark_whisper_turbo(
        self,
        audio_path: str,
        device: str = "cuda",
    ) -> BenchmarkResult:
        """Benchmark Whisper large-v3-turbo via faster-whisper."""
        return self.benchmark_faster_whisper(
            audio_path,
            model_size="large-v3-turbo",
            device=device,
            compute_type="float16",
        )

    def benchmark_insanely_fast_whisper(
        self,
        audio_path: str,
    ) -> BenchmarkResult:
        """Benchmark insanely-fast-whisper (CLI-based)."""
        audio_duration = self.get_audio_duration(audio_path)
        output_file = os.path.join(self.output_dir, "insanely_fast_output.json")

        print(f"  Running insanely-fast-whisper...")
        start_time = time.time()

        try:
            result = subprocess.run(
                [
                    "insanely-fast-whisper",
                    "--file-name", audio_path,
                    "--model-name", "openai/whisper-large-v3",
                    "--batch-size", "24",
                    "--flash", "True",
                    "--transcript-path", output_file,
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )

            transcription_time = time.time() - start_time

            if os.path.exists(output_file):
                with open(output_file) as f:
                    data = json.load(f)
                text = data.get("text", "")
                word_count = len(text.split())
            else:
                text = result.stdout
                word_count = len(text.split())

            return BenchmarkResult(
                model_name="insanely-fast-whisper",
                audio_duration=audio_duration,
                transcription_time=transcription_time,
                realtime_factor=audio_duration / transcription_time if transcription_time > 0 else 0,
                memory_used_gb=0,
                word_count=word_count,
                sample_text=text[:500] + "...",
            )

        except subprocess.TimeoutExpired:
            return BenchmarkResult(
                model_name="insanely-fast-whisper",
                audio_duration=audio_duration,
                transcription_time=600,
                realtime_factor=0,
                memory_used_gb=0,
                word_count=0,
                sample_text="",
                error="Timeout after 600s",
            )
        except FileNotFoundError:
            return BenchmarkResult(
                model_name="insanely-fast-whisper",
                audio_duration=audio_duration,
                transcription_time=0,
                realtime_factor=0,
                memory_used_gb=0,
                word_count=0,
                sample_text="",
                error="insanely-fast-whisper not installed",
            )

    def benchmark_nvidia_parakeet(
        self,
        audio_path: str,
    ) -> BenchmarkResult:
        """Benchmark NVIDIA Parakeet TDT model."""
        audio_duration = self.get_audio_duration(audio_path)

        try:
            import nemo.collections.asr as nemo_asr

            print(f"  Loading NVIDIA Parakeet...")
            start_load = time.time()
            model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-1.1b")
            load_time = time.time() - start_load
            print(f"  Model loaded in {load_time:.1f}s")

            print(f"  Transcribing...")
            start_time = time.time()
            transcription = model.transcribe([audio_path])
            transcription_time = time.time() - start_time

            text = transcription[0] if transcription else ""
            word_count = len(text.split())

            try:
                import torch
                memory_gb = torch.cuda.max_memory_allocated() / 1e9
            except:
                memory_gb = 0

            return BenchmarkResult(
                model_name="nvidia-parakeet-tdt-1.1b",
                audio_duration=audio_duration,
                transcription_time=transcription_time,
                realtime_factor=audio_duration / transcription_time if transcription_time > 0 else 0,
                memory_used_gb=memory_gb,
                word_count=word_count,
                sample_text=text[:500] + "...",
            )

        except ImportError:
            return BenchmarkResult(
                model_name="nvidia-parakeet-tdt-1.1b",
                audio_duration=audio_duration,
                transcription_time=0,
                realtime_factor=0,
                memory_used_gb=0,
                word_count=0,
                sample_text="",
                error="NeMo not installed",
            )
        except Exception as e:
            return BenchmarkResult(
                model_name="nvidia-parakeet-tdt-1.1b",
                audio_duration=audio_duration,
                transcription_time=0,
                realtime_factor=0,
                memory_used_gb=0,
                word_count=0,
                sample_text="",
                error=str(e),
            )

    def benchmark_distil_whisper(
        self,
        audio_path: str,
    ) -> BenchmarkResult:
        """Benchmark distil-whisper."""
        audio_duration = self.get_audio_duration(audio_path)

        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

            device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

            print(f"  Loading distil-whisper...")
            start_load = time.time()

            model_id = "distil-whisper/distil-large-v3"
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

            load_time = time.time() - start_load
            print(f"  Model loaded in {load_time:.1f}s")

            print(f"  Transcribing...")
            start_time = time.time()
            result = pipe(audio_path, return_timestamps=True)
            transcription_time = time.time() - start_time

            text = result.get("text", "")
            word_count = len(text.split())
            memory_gb = torch.cuda.max_memory_allocated() / 1e9 if torch.cuda.is_available() else 0

            return BenchmarkResult(
                model_name="distil-whisper-large-v3",
                audio_duration=audio_duration,
                transcription_time=transcription_time,
                realtime_factor=audio_duration / transcription_time if transcription_time > 0 else 0,
                memory_used_gb=memory_gb,
                word_count=word_count,
                sample_text=text[:500] + "...",
            )

        except Exception as e:
            return BenchmarkResult(
                model_name="distil-whisper-large-v3",
                audio_duration=audio_duration,
                transcription_time=0,
                realtime_factor=0,
                memory_used_gb=0,
                word_count=0,
                sample_text="",
                error=str(e),
            )

    def run_all_benchmarks(
        self,
        audio_path: str,
        models: Optional[list[str]] = None,
    ) -> list[BenchmarkResult]:
        """Run benchmarks for all specified models."""
        if models is None:
            models = [
                "faster-whisper-base",
                "faster-whisper-small",
                "faster-whisper-medium",
                "faster-whisper-large-v3",
                "faster-whisper-turbo",
                "distil-whisper",
                "insanely-fast-whisper",
                "nvidia-parakeet",
            ]

        results = []
        print(f"\nBenchmarking {len(models)} models on: {audio_path}")
        print("=" * 70)

        for model in models:
            print(f"\n[{model}]")

            try:
                import torch
                torch.cuda.reset_peak_memory_stats()
            except:
                pass

            if model.startswith("faster-whisper-"):
                size = model.replace("faster-whisper-", "")
                if size == "turbo":
                    result = self.benchmark_whisper_turbo(audio_path)
                else:
                    result = self.benchmark_faster_whisper(audio_path, model_size=size)
            elif model == "distil-whisper":
                result = self.benchmark_distil_whisper(audio_path)
            elif model == "insanely-fast-whisper":
                result = self.benchmark_insanely_fast_whisper(audio_path)
            elif model == "nvidia-parakeet":
                result = self.benchmark_nvidia_parakeet(audio_path)
            else:
                print(f"  Unknown model: {model}")
                continue

            results.append(result)

            if result.error:
                print(f"  ERROR: {result.error}")
            else:
                print(f"  Audio: {result.audio_duration:.1f}s")
                print(f"  Time: {result.transcription_time:.1f}s")
                print(f"  RTF: {result.realtime_factor:.1f}x realtime")
                print(f"  Memory: {result.memory_used_gb:.1f} GB")
                print(f"  Words: {result.word_count}")

        return results

    def print_results_table(self, results: list[BenchmarkResult]):
        """Print results as a formatted table."""
        print("\n" + "=" * 90)
        print("TRANSCRIPTION BENCHMARK RESULTS")
        print("=" * 90)
        print(f"{'Model':<30} {'Audio':<8} {'Time':<8} {'RTF':<10} {'Memory':<8} {'Words':<8}")
        print("-" * 90)

        for r in sorted(results, key=lambda x: -x.realtime_factor if not x.error else 0):
            if r.error:
                print(f"{r.model_name:<30} {'ERROR: ' + r.error[:40]}")
            else:
                print(f"{r.model_name:<30} {r.audio_duration:>6.0f}s {r.transcription_time:>6.1f}s "
                      f"{r.realtime_factor:>8.1f}x {r.memory_used_gb:>6.1f}GB {r.word_count:>6}")

        print("=" * 90)
        print("RTF = Realtime Factor (higher = faster, e.g., 10x means 10 min audio in 1 min)")

    def save_results(self, results: list[BenchmarkResult], output_file: str):
        """Save results to JSON."""
        data = {
            "results": [
                {
                    "model": r.model_name,
                    "audio_duration": r.audio_duration,
                    "transcription_time": r.transcription_time,
                    "realtime_factor": r.realtime_factor,
                    "memory_gb": r.memory_used_gb,
                    "word_count": r.word_count,
                    "sample_text": r.sample_text,
                    "error": r.error,
                }
                for r in results
            ]
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nResults saved to: {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark transcription models")
    parser.add_argument("audio_file", help="Audio file to transcribe")
    parser.add_argument("--models", nargs="+", help="Specific models to test")
    parser.add_argument("--output", default="benchmark_results.json", help="Output JSON file")

    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"Audio file not found: {args.audio_file}")
        return

    benchmark = TranscriptionBenchmark()
    results = benchmark.run_all_benchmarks(args.audio_file, models=args.models)
    benchmark.print_results_table(results)
    benchmark.save_results(results, args.output)


if __name__ == "__main__":
    main()
