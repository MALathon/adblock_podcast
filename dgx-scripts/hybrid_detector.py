#!/usr/bin/env python3
"""
Hybrid Ad Detector - Combines audio + text features.

Modes:
1. FAST: Audio-only (no transcription) - ~10s for 90min podcast
2. BALANCED: Audio + keyword scan from transcript - ~2min
3. ACCURATE: Audio + full text analysis - ~2-3min

All modes use temporal change point detection for start/end times.
"""

import json
import time
import numpy as np
from dataclasses import dataclass
from typing import Optional, Literal

# Import our modules
try:
    from audio_features import AudioFeatureExtractor, HAS_LIBROSA
except ImportError:
    from dgx_scripts.audio_features import AudioFeatureExtractor, HAS_LIBROSA

try:
    from ensemble_detector import EnsembleAdDetector, HAS_EMBEDDINGS, HAS_RUPTURES
except ImportError:
    from dgx_scripts.ensemble_detector import EnsembleAdDetector, HAS_EMBEDDINGS, HAS_RUPTURES

try:
    from ad_classifier import AdClassifier
except ImportError:
    from dgx_scripts.ad_classifier import AdClassifier


@dataclass
class DetectionResult:
    start: float
    end: float
    confidence: float
    signals: dict
    method: str


class HybridAdDetector:
    """
    Multi-mode ad detector combining audio and text signals.

    The detector uses temporal change point detection to find
    precise start/end times rather than classifying fixed segments.
    """

    def __init__(
        self,
        mode: Literal["fast", "balanced", "accurate"] = "balanced",
        weights: Optional[dict] = None,
        min_ad_duration: float = 10.0,
        llm_model: str = "qwen2.5:1.5b",  # Small & fast for uncertain cases
        llm_threshold: tuple[float, float] = (0.35, 0.65),
    ):
        """
        Args:
            mode: Detection mode
                - fast: Audio only, no transcription
                - balanced: Audio + keyword/transition from text
                - accurate: All signals including embeddings
            weights: Override default signal weights
            min_ad_duration: Minimum ad length in seconds
            llm_model: Model for uncertain cases (only in accurate mode)
            llm_threshold: (low, high) - use LLM when confidence is between these
        """
        self.mode = mode
        self.min_ad_duration = min_ad_duration
        self.llm_model = llm_model
        self.llm_threshold = llm_threshold

        # Default weights per mode
        if weights is None:
            if mode == "fast":
                weights = {
                    'audio_energy': 0.25,
                    'audio_spectral': 0.25,
                    'audio_change': 0.30,
                    'audio_speech': 0.20,
                }
            elif mode == "balanced":
                weights = {
                    'audio_energy': 0.15,
                    'audio_spectral': 0.15,
                    'audio_change': 0.15,
                    'keyword': 0.30,
                    'transition': 0.25,
                }
            else:  # accurate
                weights = {
                    'audio_energy': 0.10,
                    'audio_spectral': 0.10,
                    'audio_change': 0.10,
                    'keyword': 0.25,
                    'transition': 0.15,
                    'embedding': 0.20,
                    'boundary': 0.10,
                }

        self.weights = weights

        # Initialize extractors
        self.audio_extractor = AudioFeatureExtractor(
            frame_duration=1.0,
            hop_duration=0.5,
        ) if HAS_LIBROSA else None

        self.text_detector = EnsembleAdDetector(
            weights={'keyword': 0.4, 'embedding': 0.3, 'transition': 0.2, 'boundary': 0.1}
        )

        # Ad classifier for domain-specific features
        self.ad_classifier = AdClassifier()

    def detect(
        self,
        audio_path: Optional[str] = None,
        transcript: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Detect ad segments.

        Args:
            audio_path: Path to audio file
            transcript: Pre-computed transcript (list of {start, end, text})

        Returns:
            List of ad segments with start/end times
        """
        print(f"\n{'='*60}")
        print(f"HYBRID AD DETECTOR - Mode: {self.mode.upper()}")
        print(f"{'='*60}")

        start_time = time.time()

        # Collect signals based on mode
        all_signals = {}
        timestamps = None

        # Audio signals
        if audio_path and self.audio_extractor and self.mode in ("fast", "balanced", "accurate"):
            audio_signals, timestamps = self._extract_audio_signals(audio_path)
            all_signals.update(audio_signals)

        # Text signals
        if transcript and self.mode in ("balanced", "accurate"):
            text_signals, text_timestamps = self._extract_text_signals(transcript)
            all_signals.update(text_signals)

            # Use text timestamps if no audio
            if timestamps is None:
                timestamps = text_timestamps

        if not all_signals or timestamps is None:
            print("No signals extracted!")
            return []

        # Align all signals to common timestamps
        aligned_signals = self._align_signals(all_signals, timestamps)

        # Compute weighted combined signal
        combined = self._combine_signals(aligned_signals)

        # Find change points
        change_points = self._detect_change_points(combined, timestamps)
        print(f"Found {len(change_points)} change points")

        # Classify segments between change points using domain-specific features
        ads = self._classify_segments(
            timestamps, combined, change_points, aligned_signals, transcript
        )

        # Post-process with positional propagation
        ads = self._propagate_context(ads, timestamps, combined, transcript)
        ads = self._merge_adjacent(ads, gap=15.0)  # Larger gap for ad blocks
        ads = self._filter_short(ads)

        # LLM verification for uncertain cases (accurate mode only)
        if self.mode == "accurate" and transcript:
            ads = self._llm_verify(ads, transcript)

        elapsed = time.time() - start_time
        print(f"\nDetection complete in {elapsed:.1f}s")
        print(f"Found {len(ads)} ad segments")

        return [self._format_result(ad) for ad in ads]

    def _extract_audio_signals(self, audio_path: str) -> tuple[dict, np.ndarray]:
        """Extract signals from audio."""
        print("\nExtracting audio features...")
        frames = self.audio_extractor.extract_features(audio_path)

        timestamps = np.array([f.start for f in frames])

        signals = {
            'audio_energy': np.array([f.energy for f in frames]),
            'audio_spectral': np.array([f.spectral_centroid / 5000 for f in frames]),
            'audio_speech': np.array([float(f.is_speech) for f in frames]),
        }

        # Compute change signal
        change_scores = self.audio_extractor.compute_change_scores(frames)
        # Pad to match length
        signals['audio_change'] = np.concatenate([[0], change_scores])

        print(f"  Extracted {len(frames)} audio frames")
        return signals, timestamps

    def _extract_text_signals(self, transcript: list[dict]) -> tuple[dict, np.ndarray]:
        """Extract signals from transcript."""
        print("\nExtracting text features...")

        timestamps = np.array([seg["start"] for seg in transcript])
        n = len(transcript)

        signals = {
            'keyword': np.zeros(n),
            'transition': np.zeros(n),
        }

        if self.mode == "accurate" and HAS_EMBEDDINGS:
            signals['embedding'] = np.zeros(n)
            signals['boundary'] = np.zeros(n)

        for i, seg in enumerate(transcript):
            text = seg.get("text", "")
            prev_text = transcript[i-1].get("text", "") if i > 0 else ""

            signals['keyword'][i] = self.text_detector.keyword_score(text)
            signals['transition'][i] = self.text_detector.transition_score(text)

            if 'embedding' in signals:
                signals['embedding'][i] = self.text_detector.embedding_score(text)
            if 'boundary' in signals:
                signals['boundary'][i] = self.text_detector.boundary_score(prev_text, text)

        print(f"  Extracted features from {n} segments")
        return signals, timestamps

    def _align_signals(self, signals: dict, timestamps: np.ndarray) -> dict:
        """Ensure all signals have same length as timestamps."""
        n = len(timestamps)
        aligned = {}

        for name, signal in signals.items():
            if len(signal) == n:
                aligned[name] = signal
            elif len(signal) > n:
                aligned[name] = signal[:n]
            else:
                # Pad with zeros
                aligned[name] = np.concatenate([signal, np.zeros(n - len(signal))])

        return aligned

    def _combine_signals(self, signals: dict) -> np.ndarray:
        """Combine signals using weights."""
        n = len(list(signals.values())[0])
        combined = np.zeros(n)

        total_weight = 0
        for name, signal in signals.items():
            if name in self.weights:
                weight = self.weights[name]
                # Normalize signal to 0-1
                sig_min, sig_max = signal.min(), signal.max()
                if sig_max > sig_min:
                    normalized = (signal - sig_min) / (sig_max - sig_min)
                else:
                    normalized = signal
                combined += weight * normalized
                total_weight += weight

        if total_weight > 0:
            combined /= total_weight

        return combined

    def _detect_change_points(self, signal: np.ndarray, timestamps: np.ndarray) -> list[float]:
        """Find change points in combined signal."""
        if len(signal) < 10:
            return []

        if HAS_RUPTURES:
            try:
                import ruptures as rpt
                algo = rpt.Pelt(model="rbf", min_size=5, jump=1).fit(signal.reshape(-1, 1))
                indices = algo.predict(pen=0.3)
                indices = [i for i in indices if i < len(timestamps)]
                return [float(timestamps[i]) for i in indices]
            except Exception as e:
                print(f"Ruptures failed: {e}")

        # Fallback: gradient-based detection
        gradient = np.abs(np.gradient(signal))
        threshold = np.percentile(gradient, 90)
        peaks = np.where(gradient > threshold)[0]

        # Cluster nearby peaks
        change_points = []
        last_cp = -10
        for idx in peaks:
            if idx - last_cp > 5:  # Minimum gap
                change_points.append(float(timestamps[idx]))
                last_cp = idx

        return change_points

    def _classify_segments(
        self,
        timestamps: np.ndarray,
        combined: np.ndarray,
        change_points: list[float],
        signals: dict,
        transcript: Optional[list[dict]] = None,
    ) -> list[DetectionResult]:
        """Classify segments between change points using domain-specific ad features."""
        boundaries = [float(timestamps[0])] + change_points + [float(timestamps[-1])]
        ads = []

        for i in range(len(boundaries) - 1):
            start, end = boundaries[i], boundaries[i+1]
            duration = end - start

            # Find indices in this range
            mask = (timestamps >= start) & (timestamps < end)
            if not np.any(mask):
                continue

            # Average combined signal (from audio/text features)
            signal_score = float(np.mean(combined[mask]))

            # Get individual signal averages
            sig_avgs = {
                name: float(np.mean(sig[mask]))
                for name, sig in signals.items()
            }

            # Use AdClassifier if we have transcript
            classifier_confidence = 0.0
            classifier_features = {}

            if transcript:
                # Get text for this segment
                seg_text = " ".join([
                    t.get("text", "") for t in transcript
                    if start <= t.get("start", 0) < end
                ])

                # Get context text (before and after)
                text_before = " ".join([
                    t.get("text", "") for t in transcript
                    if start - 60 <= t.get("start", 0) < start
                ])
                text_after = " ".join([
                    t.get("text", "") for t in transcript
                    if end <= t.get("start", 0) < end + 60
                ])

                if seg_text:
                    is_ad, confidence, features = self.ad_classifier.classify(
                        text=seg_text,
                        duration=duration,
                        text_before=text_before,
                        text_after=text_after,
                        threshold=0.3,  # Lower threshold, we'll combine with signal score
                    )
                    classifier_confidence = confidence
                    classifier_features = {
                        "has_sponsor": features.has_sponsor_phrase,
                        "has_promo": features.has_promo_code,
                        "has_url": features.has_url,
                        "has_cta": features.has_call_to_action,
                        "has_intro": features.has_intro_transition,
                        "has_outro": features.has_outro_transition,
                        "is_standard_length": features.is_standard_ad_length,
                        "is_topic_island": features.is_topic_island,
                    }

            # Combine signal score with classifier confidence
            # Weight: 40% signals, 60% domain-specific classifier
            if transcript:
                final_confidence = 0.4 * signal_score + 0.6 * classifier_confidence
            else:
                # Audio-only mode: rely on signal score
                final_confidence = signal_score

            # Threshold for classification
            if final_confidence > 0.35:
                sig_avgs.update(classifier_features)
                sig_avgs["signal_score"] = round(signal_score, 3)
                sig_avgs["classifier_score"] = round(classifier_confidence, 3)

                ads.append(DetectionResult(
                    start=start,
                    end=end,
                    confidence=final_confidence,
                    signals=sig_avgs,
                    method=self.mode,
                ))

        return ads

    def _propagate_context(
        self,
        ads: list[DetectionResult],
        timestamps: np.ndarray,
        combined: np.ndarray,
        transcript: Optional[list[dict]] = None,
    ) -> list[DetectionResult]:
        """
        Propagate ad likelihood to adjacent segments.

        Key insight: If we detect an ad indicator, the surrounding
        segments are more likely to be part of the same ad block.
        """
        # ALWAYS check opening ads (very common location)
        opening_ads = self._check_opening_ads(timestamps, combined, transcript)
        if opening_ads:
            # Add opening ads to detected ads
            ads = opening_ads + ads

        if not ads:
            return ads

        # For each detected ad, look at surrounding 60 seconds
        expanded_ads = []

        for ad in ads:
            # Look backwards from ad start
            look_back = 30.0  # seconds
            look_forward = 30.0

            new_start = ad.start
            new_end = ad.end

            if transcript:
                # Find segments before the ad that might be part of it
                before_segs = [
                    t for t in transcript
                    if ad.start - look_back <= t.get("start", 0) < ad.start
                ]

                # Check if any have ad indicators
                for seg in reversed(before_segs):
                    text = seg.get("text", "")
                    _, conf, features = self.ad_classifier.classify(
                        text=text,
                        duration=seg.get("end", 0) - seg.get("start", 0),
                        threshold=0.25,  # Lower threshold for expansion
                    )
                    if conf > 0.25 or features.has_sponsor_phrase or features.has_intro_transition:
                        new_start = min(new_start, seg.get("start", new_start))

                # Find segments after the ad
                after_segs = [
                    t for t in transcript
                    if ad.end < t.get("start", 0) <= ad.end + look_forward
                ]

                for seg in after_segs:
                    text = seg.get("text", "")
                    _, conf, features = self.ad_classifier.classify(
                        text=text,
                        duration=seg.get("end", 0) - seg.get("start", 0),
                        threshold=0.25,
                    )
                    if conf > 0.25 or features.has_promo_code or features.has_outro_transition:
                        new_end = max(new_end, seg.get("end", new_end))

            expanded_ads.append(DetectionResult(
                start=new_start,
                end=new_end,
                confidence=ad.confidence,
                signals=ad.signals,
                method=ad.method + "+expanded",
            ))

        return expanded_ads

    def _check_opening_ads(
        self,
        timestamps: np.ndarray,
        combined: np.ndarray,
        transcript: Optional[list[dict]] = None,
    ) -> list[DetectionResult]:
        """
        Check the first 3 minutes for opening ads (very common).

        Uses 30-second sliding windows for better context.
        """
        if not transcript:
            return []

        # Get first 3 minutes of transcript
        opening_segs = [t for t in transcript if t.get("start", 0) < 180]

        if not opening_segs:
            return []

        # Use 30-second windows with 15-second hop
        window_size = 30.0
        hop_size = 15.0
        max_time = opening_segs[-1].get("end", 180)

        ads = []
        window_start = 0.0

        while window_start < max_time:
            window_end = window_start + window_size

            # Get all segments in this window
            window_segs = [
                t for t in opening_segs
                if window_start <= t.get("start", 0) < window_end
            ]

            if window_segs:
                # Combine text from all segments in window
                window_text = " ".join([t.get("text", "") for t in window_segs])
                actual_start = window_segs[0].get("start", window_start)
                actual_end = window_segs[-1].get("end", window_end)
                duration = actual_end - actual_start

                # Classify the combined window text
                _, conf, features = self.ad_classifier.classify(
                    text=window_text,
                    duration=duration,
                    threshold=0.3,
                )

                is_ad_window = (
                    conf > 0.3 or
                    features.has_sponsor_phrase or
                    features.has_promo_code
                )

                if is_ad_window:
                    ads.append(DetectionResult(
                        start=actual_start,
                        end=actual_end,
                        confidence=max(conf, 0.5),
                        signals={
                            "opening_ad": True,
                            "has_sponsor": features.has_sponsor_phrase,
                            "has_promo": features.has_promo_code,
                            "has_url": features.has_url,
                            "has_cta": features.has_call_to_action,
                        },
                        method="opening_window",
                    ))

            window_start += hop_size

        # Merge overlapping windows
        if ads:
            ads = self._merge_adjacent(ads, gap=20.0)

        return ads

    def _merge_adjacent(self, ads: list[DetectionResult], gap: float = 5.0) -> list[DetectionResult]:
        """Merge ads within gap seconds of each other."""
        if len(ads) <= 1:
            return ads

        merged = [ads[0]]
        for ad in ads[1:]:
            last = merged[-1]
            if ad.start - last.end <= gap:
                merged[-1] = DetectionResult(
                    start=last.start,
                    end=ad.end,
                    confidence=(last.confidence + ad.confidence) / 2,
                    signals={k: (last.signals.get(k, 0) + ad.signals.get(k, 0)) / 2
                             for k in set(last.signals) | set(ad.signals)},
                    method=last.method,
                )
            else:
                merged.append(ad)

        return merged

    def _filter_short(self, ads: list[DetectionResult]) -> list[DetectionResult]:
        """Remove ads shorter than minimum duration."""
        return [ad for ad in ads if ad.end - ad.start >= self.min_ad_duration]

    def _llm_verify(
        self,
        ads: list[DetectionResult],
        transcript: list[dict],
    ) -> list[DetectionResult]:
        """Use LLM to verify uncertain detections."""
        verified = []

        for ad in ads:
            if self.llm_threshold[0] < ad.confidence < self.llm_threshold[1]:
                # Uncertain - ask LLM
                text = " ".join([
                    seg["text"] for seg in transcript
                    if ad.start <= seg["start"] <= ad.end
                ])

                if self._llm_is_ad(text):
                    ad.confidence = 0.8  # Boost confidence
                    ad.method = f"{ad.method}+llm"
                    verified.append(ad)
                # else: drop it
            else:
                verified.append(ad)

        return verified

    def _llm_is_ad(self, text: str) -> bool:
        """Quick LLM check - is this text an ad?"""
        try:
            import requests

            prompt = f"""Is this podcast text an advertisement? Answer only YES or NO.

Text: {text[:500]}

Answer:"""

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=10,
            )

            answer = response.json().get("response", "").strip().upper()
            return answer.startswith("YES")

        except Exception:
            return True  # Default to keeping it

    def _format_result(self, ad: DetectionResult) -> dict:
        """Format result for output."""
        return {
            "start": round(ad.start, 2),
            "end": round(ad.end, 2),
            "confidence": round(ad.confidence, 3),
            "signals": {k: round(v, 3) for k, v in ad.signals.items()},
            "method": ad.method,
        }


def main():
    """Test the hybrid detector."""
    import sys
    import os

    # Paths
    audio_path = "/tmp/test_podcast.mp3"
    transcript_path = "/tmp/transcript_base.json"

    # Parse args
    mode = "balanced"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    # Load transcript if available
    transcript = None
    if os.path.exists(transcript_path):
        with open(transcript_path) as f:
            transcript = json.load(f)
        print(f"Loaded transcript: {len(transcript)} segments")

    # Check audio
    has_audio = os.path.exists(audio_path) and HAS_LIBROSA

    if not has_audio and not transcript:
        print("Need either audio file or transcript!")
        print(f"  Audio: {audio_path} (exists: {os.path.exists(audio_path)})")
        print(f"  Transcript: {transcript_path} (exists: {os.path.exists(transcript_path)})")
        return

    # Ground truth
    GROUND_TRUTH = [
        {"start": 0, "end": 28, "description": "Progressive Insurance"},
        {"start": 28, "end": 90, "description": "eBay Motors"},
        {"start": 1860, "end": 2100, "description": "Mid-roll ads"},
        {"start": 4680, "end": 4920, "description": "Mid-roll ads"},
    ]

    # Run detection
    detector = HybridAdDetector(mode=mode)

    ads = detector.detect(
        audio_path=audio_path if has_audio else None,
        transcript=transcript,
    )

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
        print(f"  Confidence: {ad['confidence']:.1%} ({ad['method']})")
        print(f"  Signals: {ad['signals']}")

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
