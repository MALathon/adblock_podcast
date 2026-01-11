#!/usr/bin/env python3
"""
LLM-based Ad Detector - Simpler approach using windowed LLM classification.

Based on Podly's proven approach: scan transcript in windows, use LLM for classification.
"""

import json
import time
import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class AdSegment:
    start: float
    end: float
    confidence: float
    text_preview: str
    method: str


class LLMAdDetector:
    """
    Detect ads using LLM on windowed transcript chunks.

    Simpler and more effective than complex ensemble approaches.
    """

    # System prompt based on Podly's approach
    SYSTEM_PROMPT = """You are an expert podcast ad detector. Analyze the transcript text and determine if it contains advertising content.

ADVERTISING indicators:
- Sponsor mentions: "brought to you by", "sponsored by", "today's sponsor"
- Promo codes: "use code", "discount code", "% off"
- URLs: "visit X.com", "go to X.com", "check out X"
- Call to action: "sign up", "try for free", "download now"
- Product pitches: detailed product descriptions with sales intent

NON-ADVERTISING:
- Host discussing topics organically
- Passing mentions of products without sales intent
- Educational content about companies/products
- Self-promotion by the hosts themselves

Respond with ONLY a JSON object:
{"is_ad": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}"""

    def __init__(
        self,
        model: str = "qwen2.5:1.5b",
        ollama_url: str = "http://localhost:11434",
        window_size: float = 45.0,  # seconds
        window_hop: float = 15.0,   # seconds
        confidence_threshold: float = 0.5,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.window_size = window_size
        self.window_hop = window_hop
        self.confidence_threshold = confidence_threshold

    # Fast rule-based patterns for pre-filtering
    AD_PATTERNS = [
        r'\bbrought to you by\b',
        r'\bsponsored by\b',
        r'\bthis episode is\b',
        r'\btoday\'?s sponsor\b',
        r'\bpromo code\b',
        r'\bdiscount code\b',
        r'\buse code\b',
        r'\b\d+%\s*off\b',
        r'\bvisit\s+\w+\.com\b',
        r'\bgo to\s+\w+\.com\b',
        r'\bsign up\b',
        r'\bfree trial\b',
        r'\btry.+free\b',
    ]

    def detect(self, transcript: list[dict]) -> list[dict]:
        """
        Two-stage detection:
        1. Fast rule-based filter to find suspicious windows
        2. LLM verification only on suspicious windows
        """
        import re

        print(f"\n{'='*60}")
        print(f"TWO-STAGE AD DETECTOR")
        print(f"Stage 1: Rule-based filter")
        print(f"Stage 2: LLM verification ({self.model})")
        print(f"{'='*60}")

        start_time = time.time()

        if not transcript:
            return []

        # Compile patterns
        patterns = [re.compile(p, re.IGNORECASE) for p in self.AD_PATTERNS]

        # Get total duration
        max_time = max(t.get("end", 0) for t in transcript)
        print(f"Total duration: {max_time:.0f}s ({max_time/60:.1f} min)")

        # Stage 1: Fast rule-based scan
        print(f"\nStage 1: Rule-based scanning...")
        suspicious_windows = []
        window_start = 0.0

        while window_start < max_time:
            window_end = window_start + self.window_size

            window_segs = [
                t for t in transcript
                if window_start <= t.get("start", 0) < window_end
            ]

            if window_segs:
                window_text = " ".join([t.get("text", "") for t in window_segs])
                actual_start = window_segs[0].get("start", window_start)
                actual_end = window_segs[-1].get("end", window_end)

                # Check for ad patterns
                pattern_matches = sum(1 for p in patterns if p.search(window_text))

                if pattern_matches >= 1:  # At least one ad indicator
                    suspicious_windows.append({
                        "start": actual_start,
                        "end": actual_end,
                        "text": window_text,
                        "pattern_count": pattern_matches,
                    })

            window_start += self.window_hop

        print(f"  Found {len(suspicious_windows)} suspicious windows")

        # Stage 2: LLM verification
        print(f"\nStage 2: LLM verification...")
        ad_windows = []

        for i, window in enumerate(suspicious_windows):
            print(f"  Verifying {i+1}/{len(suspicious_windows)}: {window['start']:.0f}s-{window['end']:.0f}s...")

            is_ad, confidence, reason = self._classify_window(window["text"])

            if is_ad and confidence >= self.confidence_threshold:
                ad_windows.append(AdSegment(
                    start=window["start"],
                    end=window["end"],
                    confidence=confidence,
                    text_preview=window["text"][:100] + "...",
                    method="llm_verified",
                ))
                print(f"    -> AD detected ({confidence:.0%})")
            else:
                print(f"    -> Not an ad ({confidence:.0%})")

        # Merge adjacent ad windows
        ads = self._merge_adjacent(ad_windows, gap=20.0)

        elapsed = time.time() - start_time
        print(f"\nDetection complete in {elapsed:.1f}s")
        print(f"Found {len(ads)} ad segments")

        return [self._format_result(ad) for ad in ads]

    def _classify_window(self, text: str) -> tuple[bool, float, str]:
        """Classify a window of text as ad or content."""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "system": self.SYSTEM_PROMPT,
                    "prompt": f"Analyze this podcast transcript:\n\n{text[:1000]}",
                    "stream": False,
                    "format": "json",
                },
                timeout=30,
            )

            result = response.json().get("response", "")

            # Parse JSON response
            try:
                data = json.loads(result)
                is_ad = data.get("is_ad", False)
                confidence = float(data.get("confidence", 0.5))
                reason = data.get("reason", "")
                return is_ad, confidence, reason
            except json.JSONDecodeError:
                # Fallback: look for "true" or "yes" in response
                lower = result.lower()
                if "true" in lower or "is_ad\": true" in lower:
                    return True, 0.6, "parsed from text"
                return False, 0.4, "could not parse"

        except Exception as e:
            print(f"  LLM error: {e}")
            return False, 0.0, str(e)

    def _merge_adjacent(self, ads: list[AdSegment], gap: float = 10.0) -> list[AdSegment]:
        """Merge adjacent ad windows."""
        if len(ads) <= 1:
            return ads

        # Sort by start time
        ads = sorted(ads, key=lambda x: x.start)

        merged = [ads[0]]
        for ad in ads[1:]:
            last = merged[-1]
            if ad.start - last.end <= gap:
                # Merge
                merged[-1] = AdSegment(
                    start=last.start,
                    end=ad.end,
                    confidence=(last.confidence + ad.confidence) / 2,
                    text_preview=last.text_preview,
                    method="llm_window_merged",
                )
            else:
                merged.append(ad)

        return merged

    def _format_result(self, ad: AdSegment) -> dict:
        """Format result for output."""
        return {
            "start": round(ad.start, 2),
            "end": round(ad.end, 2),
            "confidence": round(ad.confidence, 3),
            "text_preview": ad.text_preview,
            "method": ad.method,
        }


def main():
    """Test the LLM detector."""
    import os

    transcript_path = "/tmp/transcript_base.json"

    if not os.path.exists(transcript_path):
        print(f"Transcript not found: {transcript_path}")
        return

    with open(transcript_path) as f:
        transcript = json.load(f)
    print(f"Loaded transcript: {len(transcript)} segments")

    # Ground truth
    GROUND_TRUTH = [
        {"start": 0, "end": 28, "description": "Progressive Insurance"},
        {"start": 28, "end": 90, "description": "eBay Motors"},
        {"start": 1860, "end": 2100, "description": "Mid-roll ads"},
        {"start": 4680, "end": 4920, "description": "Mid-roll ads"},
    ]

    # Run detection
    detector = LLMAdDetector(
        model="qwen3-coder:latest",  # Fast and available on DGX
        window_size=60.0,  # Larger windows
        window_hop=30.0,   # Larger hops = fewer windows
        confidence_threshold=0.5,
    )

    ads = detector.detect(transcript)

    # Print results
    print(f"\n{'='*60}")
    print("DETECTED ADS")
    print(f"{'='*60}")

    for ad in ads:
        mins = int(ad["start"] // 60)
        secs = int(ad["start"] % 60)
        end_mins = int(ad["end"] // 60)
        end_secs = int(ad["end"] % 60)
        duration = ad["end"] - ad["start"]

        print(f"\n[{mins:02d}:{secs:02d} - {end_mins:02d}:{end_secs:02d}] ({duration:.0f}s)")
        print(f"  Confidence: {ad['confidence']:.1%}")
        print(f"  Preview: {ad['text_preview'][:80]}...")

    # Compare to ground truth
    print(f"\n{'='*60}")
    print("GROUND TRUTH COMPARISON")
    print(f"{'='*60}")

    hits = 0
    for gt in GROUND_TRUTH:
        detected = False
        for ad in ads:
            overlap_start = max(gt["start"], ad["start"])
            overlap_end = min(gt["end"], ad["end"])
            if overlap_start < overlap_end:
                overlap = overlap_end - overlap_start
                coverage = overlap / (gt["end"] - gt["start"])
                if coverage > 0.3:
                    detected = True
                    hits += 1
                    print(f"  ✓ {gt['description']}: DETECTED ({coverage:.0%} coverage)")
                    break
        if not detected:
            print(f"  ✗ {gt['description']}: MISSED")

    print(f"\n  Accuracy: {hits}/{len(GROUND_TRUTH)} = {hits/len(GROUND_TRUTH):.0%}")


if __name__ == "__main__":
    main()
