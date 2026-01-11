#!/usr/bin/env python3
"""Test faster-whisper on CPU with int8 quantization"""
import time
import sys

# Use specific file or first found
if len(sys.argv) > 1:
    audio_file = sys.argv[1]
else:
    import glob
    audio_files = sorted(glob.glob("/data/*.mp3"))
    # Find the Lebanon file (30 min)
    audio_file = next((f for f in audio_files if "Lebanon" in f), audio_files[0])

print(f"Testing: {audio_file}")

from faster_whisper import WhisperModel

print("Loading whisper-tiny on CPU (int8)...")
model = WhisperModel("tiny", device="cpu", compute_type="int8")

print("Transcribing...")
start = time.time()
segments, info = model.transcribe(audio_file, beam_size=1)

text_parts = []
for seg in segments:
    text_parts.append(seg.text)

elapsed = time.time() - start
text = " ".join(text_parts)

print(f"\nResults:")
print(f"  Audio: {info.duration:.0f}s ({info.duration/60:.1f} min)")
print(f"  Time: {elapsed:.1f}s")
print(f"  RTF: {info.duration/elapsed:.1f}x realtime")
print(f"  Words: {len(text.split())}")
print(f"\nFor 108 podcasts (~40h): {40*3600/info.duration*elapsed/3600:.1f} hours")
