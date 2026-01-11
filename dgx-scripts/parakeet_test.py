#!/usr/bin/env python3
"""Test NVIDIA Parakeet ASR - optimized for NVIDIA GPUs"""
import time
import sys

audio_file = sys.argv[1] if len(sys.argv) > 1 else "/data/135067274_Lebanon completes first phase of plan to disarm He.mp3"

print("Testing NVIDIA Parakeet TDT 1.1B...")
print(f"Audio: {audio_file}")

try:
    import nemo.collections.asr as nemo_asr

    print("Loading Parakeet model...")
    start_load = time.time()
    model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-1.1b")
    print(f"Model loaded in {time.time() - start_load:.1f}s")

    print("Transcribing...")
    start = time.time()
    transcription = model.transcribe([audio_file])
    elapsed = time.time() - start

    text = transcription[0] if transcription else ""

    # Get audio duration
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_file],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())

    print(f"\nAudio duration: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"Transcription time: {elapsed:.1f}s")
    print(f"RTF: {duration/elapsed:.1f}x realtime")
    print(f"Words: {len(text.split())}")
    print(f"\nFirst 200 chars: {text[:200]}...")

except ImportError as e:
    print(f"NeMo not available: {e}")
    print("\nTrying alternative: whisper with CPU (faster-whisper)...")

    from faster_whisper import WhisperModel

    print("Loading whisper-tiny on CPU...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")

    print("Transcribing...")
    start = time.time()
    segments, info = model.transcribe(audio_file, beam_size=1)

    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)

    elapsed = time.time() - start
    duration = info.duration

    print(f"\nAudio duration: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"Transcription time: {elapsed:.1f}s")
    print(f"RTF: {duration/elapsed:.1f}x realtime")
    print(f"Words: {len(' '.join(text_parts).split())}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
