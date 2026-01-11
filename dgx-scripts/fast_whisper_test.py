#!/usr/bin/env python3
"""Test faster-whisper with CUDA"""
import time
import sys

try:
    from faster_whisper import WhisperModel

    print("Loading whisper-tiny with faster-whisper...")
    model = WhisperModel("tiny", device="cuda", compute_type="float16")

    audio_file = sys.argv[1] if len(sys.argv) > 1 else "/data/135067274_Lebanon completes first phase of plan to disarm He.mp3"

    print(f"Transcribing: {audio_file}")
    start = time.time()
    segments, info = model.transcribe(audio_file, beam_size=1)

    # Must iterate to actually transcribe
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)

    elapsed = time.time() - start
    text = " ".join(text_parts)
    duration = info.duration

    print(f"Audio duration: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"Transcription time: {elapsed:.1f}s")
    print(f"RTF: {duration/elapsed:.1f}x realtime")
    print(f"Words: {len(text.split())}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
