#!/usr/bin/env python3
"""
Ensemble Ad Detector - Temporal approach using change point detection.

Uses multiple fast signals + ruptures for finding ad boundaries.
No LLM needed for most cases - sub-second processing.
"""

import re
import json
import numpy as np
from dataclasses import dataclass
from typing import Optional

# Optional imports - graceful degradation
try:
    import ruptures as rpt
    HAS_RUPTURES = True
except ImportError:
    HAS_RUPTURES = False
    print("Warning: ruptures not installed. Using fallback threshold method.")

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    print("Warning: sentence-transformers not installed. Embedding features disabled.")


@dataclass
class AdSegment:
    start: float
    end: float
    confidence: float
    signals: dict


class EnsembleAdDetector:
    """
    Multi-signal ad detector using change point detection.

    Signals:
    - keyword: Regex patterns for ad-related phrases
    - embedding: Cosine similarity to known ad patterns
    - transition: Phrases that signal topic change
    - boundary: Semantic coherence breaks

    Weights are tunable per-signal.
    """

    # Common ad keywords and patterns
    AD_KEYWORDS = [
        # Sponsor phrases
        r'\bbrought to you by\b',
        r'\bsponsored by\b',
        r'\bthis episode is sponsored\b',
        r'\btoday\'?s sponsor\b',
        r'\bour sponsor\b',
        r'\bpartner\b',

        # Promo codes
        r'\bpromo code\b',
        r'\bcode [A-Z]{2,}\b',
        r'\bdiscount code\b',
        r'\buse code\b',
        r'\b\d+%?\s*off\b',

        # Call to action
        r'\bvisit\s+\w+\.com\b',
        r'\bgo to\s+\w+\.com\b',
        r'\bcheck out\s+\w+\.com\b',
        r'\bhead to\s+\w+\.com\b',
        r'\bsign up\b',
        r'\bfree trial\b',
        r'\bclick the link\b',
        r'\bin the description\b',

        # Product pitch phrases
        r'\byou\'?ll love\b',
        r'\bI use .* every day\b',
        r'\bpersonally recommend\b',
        r'\bgame changer\b',
        r'\blife changing\b',

        # Common sponsor names (extend as needed)
        r'\bsquarespace\b',
        r'\baudible\b',
        r'\bbetterhelp\b',
        r'\bblue apron\b',
        r'\bcasper\b',
        r'\bdoorDash\b',
        r'\bexpressvpn\b',
        r'\bhello ?fresh\b',
        r'\bhoney\b',
        r'\bmanscaped\b',
        r'\bnordvpn\b',
        r'\braid:? shadow legends\b',
        r'\brocket ?money\b',
        r'\bskillshare\b',
        r'\bstamps\.?com\b',
        r'\bseatgeek\b',
        r'\bprogressive\b',
        r'\bebay\b',
        r'\bhelix\b',
        r'\baspca\b',
        r'\bfactor\b',
        r'\bprolon\b',
    ]

    # Transition phrases that often precede/follow ads
    TRANSITION_PHRASES = [
        r'\bnow let me tell you about\b',
        r'\bspeaking of which\b',
        r'\bbefore we (continue|get back)\b',
        r'\blet\'?s take a (quick )?(break|moment)\b',
        r'\band now\b',
        r'\banyway,? (back to|let\'?s get back)\b',
        r'\balright,? (so )?(back to|where were we)\b',
        r'\bok,? (so )?(back to|anyway)\b',
        r'\bmoving on\b',
        r'\bthat said\b',
        r'\bwith that\b',
    ]

    # Example ad text patterns for embedding similarity
    AD_EXAMPLES = [
        "This episode is brought to you by Progressive Insurance. Get a quote at progressive.com.",
        "Use code PODCAST for 20% off your first order at our sponsor's website.",
        "BetterHelp is online therapy. Visit betterhelp.com/show for 10% off.",
        "Thanks to Squarespace for sponsoring this episode. Build your website today.",
        "Download the app and use promo code SAVE for a free trial.",
        "Our sponsor today is HelloFresh. Get fresh ingredients delivered to your door.",
    ]

    def __init__(
        self,
        weights: Optional[dict] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        min_ad_duration: float = 10.0,
        max_ad_gap: float = 5.0,
    ):
        """
        Initialize detector.

        Args:
            weights: Signal weights, must sum to 1.0
            embedding_model: Sentence transformer model name
            min_ad_duration: Minimum seconds for an ad segment
            max_ad_gap: Maximum gap to merge adjacent ads
        """
        self.weights = weights or {
            'keyword': 0.35,
            'embedding': 0.25,
            'transition': 0.20,
            'boundary': 0.20,
        }

        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}

        self.min_ad_duration = min_ad_duration
        self.max_ad_gap = max_ad_gap

        # Compile regex patterns
        self.keyword_patterns = [re.compile(p, re.IGNORECASE) for p in self.AD_KEYWORDS]
        self.transition_patterns = [re.compile(p, re.IGNORECASE) for p in self.TRANSITION_PHRASES]

        # Load embedding model if available
        self.embedding_model = None
        self.ad_embeddings = None
        if HAS_EMBEDDINGS:
            try:
                print(f"Loading embedding model: {embedding_model}")
                self.embedding_model = SentenceTransformer(embedding_model)
                # Pre-compute ad example embeddings
                self.ad_embeddings = self.embedding_model.encode(self.AD_EXAMPLES)
                print(f"Loaded {len(self.AD_EXAMPLES)} ad pattern embeddings")
            except Exception as e:
                print(f"Warning: Could not load embedding model: {e}")

    def keyword_score(self, text: str) -> float:
        """Score based on ad keyword matches."""
        if not text:
            return 0.0

        matches = sum(1 for p in self.keyword_patterns if p.search(text))
        # Normalize: 3+ matches = 1.0
        return min(matches / 3.0, 1.0)

    def transition_score(self, text: str, position: str = "middle") -> float:
        """Score based on transition phrase detection."""
        if not text:
            return 0.0

        matches = sum(1 for p in self.transition_patterns if p.search(text))
        # Transitions at segment boundaries are more significant
        multiplier = 1.5 if position in ("start", "end") else 1.0
        return min(matches * 0.5 * multiplier, 1.0)

    def embedding_score(self, text: str) -> float:
        """Score based on embedding similarity to ad patterns."""
        if not text or self.embedding_model is None or self.ad_embeddings is None:
            return 0.0

        try:
            text_embedding = self.embedding_model.encode([text])[0]
            # Cosine similarity with each ad example
            similarities = np.dot(self.ad_embeddings, text_embedding) / (
                np.linalg.norm(self.ad_embeddings, axis=1) * np.linalg.norm(text_embedding)
            )
            # Return max similarity, scaled
            max_sim = float(np.max(similarities))
            # Similarity > 0.5 is quite high for this task
            return min(max(max_sim - 0.2, 0) / 0.5, 1.0)
        except Exception as e:
            print(f"Embedding error: {e}")
            return 0.0

    def boundary_score(self, prev_text: str, curr_text: str) -> float:
        """Score based on semantic boundary (topic shift)."""
        if not prev_text or not curr_text or self.embedding_model is None:
            return 0.0

        try:
            embeddings = self.embedding_model.encode([prev_text, curr_text])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            # Low similarity = high boundary score
            # Similarity < 0.5 indicates topic shift
            return max(0.7 - similarity, 0) / 0.4
        except Exception:
            return 0.0

    def compute_signal(self, transcript: list[dict]) -> np.ndarray:
        """
        Compute multi-dimensional signal for change point detection.

        Returns array of shape (n_segments, n_features) where features are:
        [keyword_score, embedding_score, transition_score, boundary_score]
        """
        n = len(transcript)
        if n == 0:
            return np.array([])

        signals = np.zeros((n, 4))

        for i, seg in enumerate(transcript):
            text = seg.get("text", "")
            prev_text = transcript[i-1].get("text", "") if i > 0 else ""

            # Determine position for transition scoring
            position = "start" if i < 3 else ("end" if i >= n - 3 else "middle")

            signals[i, 0] = self.keyword_score(text)
            signals[i, 1] = self.embedding_score(text)
            signals[i, 2] = self.transition_score(text, position)
            signals[i, 3] = self.boundary_score(prev_text, text)

        return signals

    def compute_weighted_signal(self, signals: np.ndarray) -> np.ndarray:
        """Combine multi-dim signal into single weighted signal."""
        weights = np.array([
            self.weights['keyword'],
            self.weights['embedding'],
            self.weights['transition'],
            self.weights['boundary'],
        ])
        return np.dot(signals, weights)

    def detect_change_points(self, signal: np.ndarray, timestamps: np.ndarray) -> list[float]:
        """Find change points in the signal using ruptures."""
        if len(signal) < 5:
            return []

        if HAS_RUPTURES:
            # Use PELT with RBF kernel
            try:
                algo = rpt.Pelt(model="rbf", min_size=3, jump=1).fit(signal.reshape(-1, 1))
                # Penalty controls sensitivity (lower = more change points)
                change_indices = algo.predict(pen=0.5)
                # Remove last index (always included by ruptures)
                change_indices = [i for i in change_indices if i < len(signal)]
                return [float(timestamps[min(i, len(timestamps)-1)]) for i in change_indices]
            except Exception as e:
                print(f"Ruptures error: {e}, using fallback")

        # Fallback: threshold-based detection
        threshold = 0.4
        change_points = []
        above_threshold = signal[0] > threshold

        for i in range(1, len(signal)):
            curr_above = signal[i] > threshold
            if curr_above != above_threshold:
                change_points.append(float(timestamps[i]))
                above_threshold = curr_above

        return change_points

    def classify_segments(
        self,
        transcript: list[dict],
        signals: np.ndarray,
        change_points: list[float]
    ) -> list[AdSegment]:
        """
        Classify segments between change points as AD or CONTENT.
        """
        if not change_points:
            # No change points - check if entire thing is an ad
            weighted = self.compute_weighted_signal(signals)
            avg_score = float(np.mean(weighted))
            if avg_score > 0.5:
                return [AdSegment(
                    start=transcript[0]["start"],
                    end=transcript[-1]["end"],
                    confidence=avg_score,
                    signals={"avg_weighted": avg_score}
                )]
            return []

        # Add start and end boundaries
        boundaries = [transcript[0]["start"]] + change_points + [transcript[-1]["end"]]
        ads = []

        for i in range(len(boundaries) - 1):
            start_time = boundaries[i]
            end_time = boundaries[i + 1]

            # Find segments in this range
            seg_indices = [
                j for j, seg in enumerate(transcript)
                if seg["start"] >= start_time and seg["end"] <= end_time
            ]

            if not seg_indices:
                continue

            # Average score for this segment
            seg_signals = signals[seg_indices]
            weighted = self.compute_weighted_signal(seg_signals)
            avg_score = float(np.mean(weighted))

            # Classify as ad if score > 0.5
            if avg_score > 0.4:
                # Get individual signal averages for debugging
                signal_avgs = {
                    'keyword': float(np.mean(seg_signals[:, 0])),
                    'embedding': float(np.mean(seg_signals[:, 1])),
                    'transition': float(np.mean(seg_signals[:, 2])),
                    'boundary': float(np.mean(seg_signals[:, 3])),
                }

                ads.append(AdSegment(
                    start=start_time,
                    end=end_time,
                    confidence=avg_score,
                    signals=signal_avgs
                ))

        return ads

    def merge_adjacent_ads(self, ads: list[AdSegment]) -> list[AdSegment]:
        """Merge ads that are close together."""
        if len(ads) <= 1:
            return ads

        merged = [ads[0]]
        for ad in ads[1:]:
            last = merged[-1]
            if ad.start - last.end <= self.max_ad_gap:
                # Merge
                merged[-1] = AdSegment(
                    start=last.start,
                    end=ad.end,
                    confidence=(last.confidence + ad.confidence) / 2,
                    signals={k: (last.signals.get(k, 0) + ad.signals.get(k, 0)) / 2
                             for k in set(last.signals) | set(ad.signals)}
                )
            else:
                merged.append(ad)

        return merged

    def filter_short_ads(self, ads: list[AdSegment]) -> list[AdSegment]:
        """Remove ads shorter than minimum duration."""
        return [ad for ad in ads if ad.end - ad.start >= self.min_ad_duration]

    def detect(self, transcript: list[dict]) -> list[dict]:
        """
        Main detection method.

        Args:
            transcript: List of segments with 'start', 'end', 'text' keys

        Returns:
            List of ad segments: [{"start": float, "end": float, "confidence": float, ...}]
        """
        if not transcript:
            return []

        print(f"Processing {len(transcript)} segments...")

        # Extract timestamps
        timestamps = np.array([seg["start"] for seg in transcript])

        # Compute multi-signal features
        print("Computing signal features...")
        signals = self.compute_signal(transcript)

        # Get weighted signal for change point detection
        weighted_signal = self.compute_weighted_signal(signals)

        # Find change points
        print("Detecting change points...")
        change_points = self.detect_change_points(weighted_signal, timestamps)
        print(f"Found {len(change_points)} change points")

        # Classify segments
        print("Classifying segments...")
        ads = self.classify_segments(transcript, signals, change_points)

        # Post-process
        ads = self.merge_adjacent_ads(ads)
        ads = self.filter_short_ads(ads)

        print(f"Detected {len(ads)} ad segments")

        # Convert to dict format
        return [
            {
                "start": ad.start,
                "end": ad.end,
                "confidence": round(ad.confidence, 3),
                "signals": {k: round(v, 3) for k, v in ad.signals.items()}
            }
            for ad in ads
        ]


def main():
    """Test on cached transcript."""
    import time

    # Try to load cached transcript
    transcript_path = "/tmp/transcript_base.json"
    try:
        with open(transcript_path) as f:
            transcript = json.load(f)
        print(f"Loaded transcript: {len(transcript)} segments")
    except FileNotFoundError:
        print(f"No cached transcript at {transcript_path}")
        print("Run process_podcast.py first to generate transcript")
        return

    # Ground truth for comparison
    GROUND_TRUTH = [
        {"start": 0, "end": 28, "description": "Progressive Insurance"},
        {"start": 28, "end": 90, "description": "eBay Motors"},
        {"start": 1860, "end": 2100, "description": "Mid-roll ads"},
        {"start": 4680, "end": 4920, "description": "Mid-roll ads"},
    ]

    print("\n" + "=" * 60)
    print("ENSEMBLE AD DETECTOR TEST")
    print("=" * 60)

    # Initialize detector
    detector = EnsembleAdDetector()

    # Time the detection
    start_time = time.time()
    detected_ads = detector.detect(transcript)
    elapsed = time.time() - start_time

    print(f"\nDetection completed in {elapsed:.2f}s")
    print(f"\nDetected {len(detected_ads)} ad segments:")

    for ad in detected_ads:
        mins = int(ad["start"] // 60)
        secs = int(ad["start"] % 60)
        end_mins = int(ad["end"] // 60)
        end_secs = int(ad["end"] % 60)
        duration = ad["end"] - ad["start"]

        print(f"\n  [{mins:02d}:{secs:02d} - {end_mins:02d}:{end_secs:02d}] ({duration:.0f}s)")
        print(f"    Confidence: {ad['confidence']:.1%}")
        print(f"    Signals: {ad['signals']}")

    # Compare to ground truth
    print("\n" + "=" * 60)
    print("GROUND TRUTH COMPARISON")
    print("=" * 60)

    for gt in GROUND_TRUTH:
        gt_start, gt_end = gt["start"], gt["end"]

        # Check if any detected ad overlaps
        detected = False
        for ad in detected_ads:
            overlap_start = max(gt_start, ad["start"])
            overlap_end = min(gt_end, ad["end"])
            if overlap_start < overlap_end:
                overlap = overlap_end - overlap_start
                coverage = overlap / (gt_end - gt_start)
                if coverage > 0.3:
                    detected = True
                    print(f"  ✓ {gt['description']} ({gt_start}-{gt_end}s): DETECTED ({coverage:.0%} coverage)")
                    break

        if not detected:
            print(f"  ✗ {gt['description']} ({gt_start}-{gt_end}s): MISSED")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Processing time: {elapsed:.2f}s")
    print(f"  Segments processed: {len(transcript)}")
    print(f"  Speed: {len(transcript)/elapsed:.0f} segments/second")
    print(f"  Ads detected: {len(detected_ads)}")


if __name__ == "__main__":
    main()
