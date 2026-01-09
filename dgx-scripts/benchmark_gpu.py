#!/usr/bin/env python3
"""Benchmark whisper models on GPU"""
import whisper
import time
import requests
import tempfile
import os

print("Downloading test audio (~30MB)...")
url = "https://sphinx.acast.com/p/acast/s/dungeons-and-daddies/e/6940b888891c3619dc4b3b3e/media.mp3"
with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, stream=True, timeout=60)
    total = 0
    for chunk in resp.iter_content(8192):
        f.write(chunk)
        total += len(chunk)
        if total > 30 * 1024 * 1024:
            break
    audio_path = f.name
print(f"Downloaded {total/1024/1024:.1f}MB (~10 min audio)")

print("\n" + "=" * 50)
print("WHISPER GPU BENCHMARK (CUDA 13.1)")
print("=" * 50)

results = []
for model_name in ["tiny", "base", "small"]:
    print(f"\nLoading {model_name}...", end=" ", flush=True)
    model = whisper.load_model(model_name, device="cuda")
    print("transcribing...", end=" ", flush=True)

    start = time.time()
    result = model.transcribe(audio_path, language="en")
    elapsed = time.time() - start

    num_segs = len(result["segments"])
    print(f"done!")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Segments: {num_segs}")
    results.append((model_name, elapsed, num_segs))

os.unlink(audio_path)

print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)
for name, t, segs in results:
    print(f"{name:>8}: {t:6.1f}s ({segs} segments)")
