#!/usr/bin/env python3
"""Test if better transcription (small vs base) enables smaller LLMs to detect ads"""
import whisper
import requests
import tempfile
import time
import json
import os

# Ground truth ads (manually verified)
GROUND_TRUTH = [
    {"start": 0, "end": 28, "description": "Progressive Insurance pre-roll"},
    {"start": 28, "end": 90, "description": "eBay Motors pre-roll"},
    {"start": 1860, "end": 2100, "description": "Mid-roll: Helix, ASPCA, Progressive"},
    {"start": 4680, "end": 4920, "description": "Mid-roll: Rocket Money, Factor, Prolon"},
]

def download_test_audio():
    """Download test podcast"""
    url = "https://sphinx.acast.com/p/acast/s/dungeons-and-daddies/e/6940b888891c3619dc4b3b3e/media.mp3"
    cache_path = "/tmp/test_podcast.mp3"

    if os.path.exists(cache_path):
        print(f"Using cached audio: {cache_path}")
        return cache_path

    print(f"Downloading: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, stream=True, timeout=60)

    with open(cache_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)

    print(f"Downloaded to {cache_path}")
    return cache_path

def transcribe_with_model(audio_path: str, model_name: str) -> tuple[list[dict], float]:
    """Transcribe audio and return transcript + time"""
    print(f"\nTranscribing with whisper {model_name}...")

    device = "cuda"
    model = whisper.load_model(model_name, device=device)

    start = time.time()
    result = model.transcribe(audio_path, language="en")
    elapsed = time.time() - start

    transcript = []
    for seg in result["segments"]:
        transcript.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip()
        })

    print(f"  Transcribed in {elapsed:.1f}s ({len(transcript)} segments)")
    return transcript, elapsed

def get_section(transcript: list[dict], start: float, end: float) -> str:
    """Extract transcript section"""
    text_parts = []
    for seg in transcript:
        if start <= seg["start"] <= end:
            text_parts.append(seg["text"])
    return " ".join(text_parts)

def test_llm_detection(transcript: list[dict], llm_model: str) -> tuple[list[dict], float]:
    """Test LLM ad detection on pre-roll only (faster test)"""

    # Just test pre-roll section (0-120s) for speed
    section = get_section(transcript, 0, 120)

    prompt = f"""Analyze this podcast transcript section and identify advertising segments.
Ads include: sponsor reads, promo codes, product pitches, "brought to you by", calls to action.

Transcript (0:00 - 2:00):
{section}

Return ONLY valid JSON array of ad segments found:
[{{"start": <seconds>, "end": <seconds>, "reason": "<brief reason>"}}]

If no ads found, return: []"""

    start = time.time()
    # Use Ollama API instead of CLI (running on host via --network host)
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": llm_model, "prompt": prompt, "stream": False},
        timeout=120
    )
    elapsed = time.time() - start

    output = response.json().get("response", "").strip()

    # Parse JSON from response
    try:
        # Find JSON array in response
        import re
        match = re.search(r'\[.*?\]', output, re.DOTALL)
        if match:
            ads = json.loads(match.group())
            return ads, elapsed
    except:
        pass

    return [], elapsed

def check_detection_accuracy(detected: list[dict], ground_truth_section: dict) -> dict:
    """Check if detection covers ground truth ad"""
    gt_start = ground_truth_section["start"]
    gt_end = ground_truth_section["end"]

    for ad in detected:
        ad_start = ad.get("start", 0)
        ad_end = ad.get("end", 0)

        # Check for overlap
        overlap_start = max(gt_start, ad_start)
        overlap_end = min(gt_end, ad_end)

        if overlap_start < overlap_end:
            overlap = overlap_end - overlap_start
            coverage = overlap / (gt_end - gt_start)
            if coverage > 0.5:  # >50% coverage = detected
                return {"detected": True, "coverage": coverage, "ad": ad}

    return {"detected": False, "coverage": 0, "ad": None}

def main():
    audio_path = download_test_audio()

    print("\n" + "=" * 70)
    print("HYPOTHESIS: Better transcription → Better ad detection with small LLMs")
    print("=" * 70)

    # Test configurations
    configs = [
        ("base", "hermes3:8b"),    # Previous: 0% accuracy
        ("small", "hermes3:8b"),   # Hypothesis: might work better
        ("small", "qwen3-coder:latest"),  # Control: known good model
    ]

    results = []

    for whisper_model, llm_model in configs:
        print(f"\n{'=' * 70}")
        print(f"CONFIG: whisper={whisper_model}, llm={llm_model}")
        print("=" * 70)

        # Transcribe
        transcript, trans_time = transcribe_with_model(audio_path, whisper_model)

        # Cache transcript for debugging
        cache_file = f"/tmp/transcript_{whisper_model}.json"
        with open(cache_file, "w") as f:
            json.dump(transcript, f, indent=2)

        # Test LLM on pre-roll (ground truth: Progressive 0-28s, eBay 28-90s)
        detected, llm_time = test_llm_detection(transcript, llm_model)

        print(f"\nDetected ads: {json.dumps(detected, indent=2)}")

        # Check accuracy against first two ground truth ads
        gt_progressive = {"start": 0, "end": 28, "description": "Progressive"}
        gt_ebay = {"start": 28, "end": 90, "description": "eBay"}

        prog_result = check_detection_accuracy(detected, gt_progressive)
        ebay_result = check_detection_accuracy(detected, gt_ebay)

        accuracy = (1 if prog_result["detected"] else 0) + (1 if ebay_result["detected"] else 0)
        accuracy_pct = accuracy / 2 * 100

        print(f"\nResults:")
        print(f"  Progressive (0-28s): {'✓ DETECTED' if prog_result['detected'] else '✗ MISSED'}")
        print(f"  eBay (28-90s): {'✓ DETECTED' if ebay_result['detected'] else '✗ MISSED'}")
        print(f"  Accuracy: {accuracy_pct:.0f}%")
        print(f"  Transcription time: {trans_time:.1f}s")
        print(f"  LLM time: {llm_time:.1f}s")
        print(f"  Total time: {trans_time + llm_time:.1f}s")

        results.append({
            "whisper": whisper_model,
            "llm": llm_model,
            "accuracy": accuracy_pct,
            "trans_time": trans_time,
            "llm_time": llm_time,
            "total_time": trans_time + llm_time,
            "detected": detected
        })

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Whisper':<10} {'LLM':<20} {'Accuracy':<10} {'Trans':<8} {'LLM':<8} {'Total':<8}")
    print("-" * 70)
    for r in results:
        print(f"{r['whisper']:<10} {r['llm']:<20} {r['accuracy']:.0f}%{'':<6} {r['trans_time']:.1f}s{'':<4} {r['llm_time']:.1f}s{'':<4} {r['total_time']:.1f}s")

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    # Check if hypothesis holds
    base_hermes = next((r for r in results if r["whisper"] == "base" and "hermes" in r["llm"]), None)
    small_hermes = next((r for r in results if r["whisper"] == "small" and "hermes" in r["llm"]), None)

    if base_hermes and small_hermes:
        if small_hermes["accuracy"] > base_hermes["accuracy"]:
            print("✓ HYPOTHESIS CONFIRMED: Better transcription improves small LLM accuracy!")
            print(f"  hermes3:8b accuracy: {base_hermes['accuracy']:.0f}% (base) → {small_hermes['accuracy']:.0f}% (small)")
        else:
            print("✗ HYPOTHESIS NOT CONFIRMED: Transcription quality didn't help")
            print(f"  hermes3:8b accuracy: {base_hermes['accuracy']:.0f}% (base) → {small_hermes['accuracy']:.0f}% (small)")

if __name__ == "__main__":
    main()
