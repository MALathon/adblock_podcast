#!/usr/bin/env python3
"""Quick test: base whisper + qwen3-coder for optimal speed"""
import requests
import time
import json
import re

print("Loading cached transcript from base whisper run...")
try:
    with open("/tmp/transcript_base.json") as f:
        transcript = json.load(f)
    print(f"Loaded {len(transcript)} segments")
except FileNotFoundError:
    print("ERROR: No cached transcript. Run full test first.")
    exit(1)

# Extract pre-roll section
section = " ".join([s["text"] for s in transcript if 0 <= s["start"] <= 120])

prompt = f"""Analyze this podcast transcript section and identify advertising segments.
Ads include: sponsor reads, promo codes, product pitches, "brought to you by", calls to action.

Transcript (0:00 - 2:00):
{section}

Return ONLY valid JSON array of ad segments found:
[{{"start": <seconds>, "end": <seconds>, "reason": "<brief reason>"}}]

If no ads found, return: []"""

print("\nTesting: base whisper + qwen3-coder:latest")
start = time.time()
response = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "qwen3-coder:latest", "prompt": prompt, "stream": False},
    timeout=120
)
elapsed = time.time() - start

output = response.json().get("response", "").strip()
print(f"LLM response time: {elapsed:.1f}s")

# Parse JSON
match = re.search(r'\[.*?\]', output, re.DOTALL)
if match:
    ads = json.loads(match.group())
    print(f"\nDetected ads: {json.dumps(ads, indent=2)}")

    # Check against ground truth
    progressive_detected = any(
        ad.get("start", 99) <= 28 and ad.get("end", 0) >= 10
        for ad in ads
    )
    ebay_detected = any(
        ad.get("start", 99) <= 90 and ad.get("end", 0) >= 50
        for ad in ads
    )

    print(f"\nResults:")
    print(f"  Progressive (0-28s): {'✓ DETECTED' if progressive_detected else '✗ MISSED'}")
    print(f"  eBay (28-90s): {'✓ DETECTED' if ebay_detected else '✗ MISSED'}")

    accuracy = ((1 if progressive_detected else 0) + (1 if ebay_detected else 0)) / 2 * 100
    print(f"  Accuracy: {accuracy:.0f}%")

    print(f"\n{'=' * 60}")
    print("OPTIMAL CONFIG: base whisper (~127s) + qwen3-coder (~{:.1f}s)".format(elapsed))
    print(f"Total estimated time: ~{127 + elapsed:.0f}s for 90 min podcast")
    print("=" * 60)
else:
    print(f"ERROR: Could not parse JSON from response:\n{output[:500]}")
