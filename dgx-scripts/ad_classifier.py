#!/usr/bin/env python3
"""
Ad Classifier - Determines if a segment is an ad based on multiple features.

This runs AFTER boundary detection to classify each segment.
Uses features specific to what makes an ad an ad.
"""

import re
import numpy as np
from dataclasses import dataclass
from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False


@dataclass
class SegmentFeatures:
    """Features extracted from a segment for classification."""
    # Text features
    keyword_count: int
    keyword_score: float
    has_url: bool
    has_promo_code: bool
    has_call_to_action: bool
    has_sponsor_phrase: bool

    # Transition features
    has_intro_transition: bool  # "Let me tell you about..."
    has_outro_transition: bool  # "Anyway, back to..."

    # Duration features
    duration: float
    is_standard_ad_length: bool  # 30s, 60s, 90s ± 10s

    # Context features
    topic_similarity_before: float  # How related to previous segment
    topic_similarity_after: float   # How related to next segment
    is_topic_island: bool           # Unrelated to both neighbors

    # Combined
    confidence: float


class AdClassifier:
    """
    Classify segments as ads based on ad-specific features.

    Unlike generic change point detection, this uses
    domain knowledge about what makes an ad.
    """

    # Definitive ad indicators (high confidence)
    SPONSOR_PHRASES = [
        r'\bbrought to you by\b',
        r'\bsponsored by\b',
        r'\bthis (episode|podcast|show) is (brought|sponsored)\b',
        r'\btoday\'?s sponsor\b',
        r'\bour (sponsor|partner)\b',
        r'\bsponsor of (this|the)\b',
    ]

    PROMO_CODE_PATTERNS = [
        r'\b(promo|discount|coupon)\s*code\b',
        r'\bcode\s+[A-Z]{2,}\b',
        r'\buse\s+(code|my code)\b',
        r'\b\d{1,2}%\s*off\b',
        r'\bsave\s+\$?\d+\b',
    ]

    URL_PATTERNS = [
        r'\b\w+\.(com|org|net|co)\b',
        r'\bvisit\s+\w+\b',
        r'\bgo\s+to\s+\w+\b',
        r'\bhead\s+(to|over)\s+\w+\b',
    ]

    CALL_TO_ACTION = [
        r'\bsign\s*up\b',
        r'\bget\s+started\b',
        r'\btry\s+(it\s+)?(for\s+)?free\b',
        r'\bfree\s+trial\b',
        r'\bclick\s+(the\s+)?link\b',
        r'\bcheck\s+(it\s+)?out\b',
        r'\bdownload\b',
        r'\bsubscribe\b',
    ]

    # Transition phrases
    INTRO_TRANSITIONS = [
        r'\b(let\s+me|i\s+want\s+to)\s+tell\s+you\s+about\b',
        r'\bspeaking\s+of\s+(which)?\b',
        r'\bbefore\s+we\s+(continue|go\s+on|get\s+back)\b',
        r'\blet\'?s\s+take\s+a\s+(quick\s+)?(break|moment)\b',
        r'\bi\'?m\s+excited\s+to\s+tell\s+you\s+about\b',
        r'\breal\s+quick\b',
        r'\bquick\s+break\b',
    ]

    OUTRO_TRANSITIONS = [
        r'\b(anyway|alright|ok),?\s*(so\s+)?(back\s+to|where\s+were\s+we)\b',
        r'\bmoving\s+on\b',
        r'\blet\'?s\s+get\s+back\b',
        r'\bnow,?\s*(back\s+to|where\s+were\s+we)\b',
        r'\bso,?\s+anyway\b',
    ]

    # Standard ad durations (seconds)
    STANDARD_DURATIONS = [30, 60, 90, 120]
    DURATION_TOLERANCE = 10

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        """Initialize classifier."""
        # Compile patterns
        self.sponsor_patterns = [re.compile(p, re.IGNORECASE) for p in self.SPONSOR_PHRASES]
        self.promo_patterns = [re.compile(p, re.IGNORECASE) for p in self.PROMO_CODE_PATTERNS]
        self.url_patterns = [re.compile(p, re.IGNORECASE) for p in self.URL_PATTERNS]
        self.cta_patterns = [re.compile(p, re.IGNORECASE) for p in self.CALL_TO_ACTION]
        self.intro_patterns = [re.compile(p, re.IGNORECASE) for p in self.INTRO_TRANSITIONS]
        self.outro_patterns = [re.compile(p, re.IGNORECASE) for p in self.OUTRO_TRANSITIONS]

        # Load embedding model
        self.embedding_model = None
        if HAS_EMBEDDINGS:
            try:
                self.embedding_model = SentenceTransformer(embedding_model)
            except Exception as e:
                print(f"Could not load embedding model: {e}")

    def _count_pattern_matches(self, text: str, patterns: list) -> int:
        """Count how many patterns match."""
        return sum(1 for p in patterns if p.search(text))

    def _has_pattern(self, text: str, patterns: list) -> bool:
        """Check if any pattern matches."""
        return any(p.search(text) for p in patterns)

    def _is_standard_duration(self, duration: float) -> bool:
        """Check if duration matches standard ad lengths."""
        for std in self.STANDARD_DURATIONS:
            if abs(duration - std) <= self.DURATION_TOLERANCE:
                return True
        return False

    def _compute_topic_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts."""
        if not text1 or not text2 or not self.embedding_model:
            return 0.5  # Neutral

        try:
            embeddings = self.embedding_model.encode([text1, text2])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception:
            return 0.5

    def extract_features(
        self,
        text: str,
        duration: float,
        text_before: str = "",
        text_after: str = "",
    ) -> SegmentFeatures:
        """Extract classification features from a segment."""

        # Keyword features
        sponsor_matches = self._count_pattern_matches(text, self.sponsor_patterns)
        promo_matches = self._count_pattern_matches(text, self.promo_patterns)
        url_matches = self._count_pattern_matches(text, self.url_patterns)
        cta_matches = self._count_pattern_matches(text, self.cta_patterns)

        total_keywords = sponsor_matches + promo_matches + url_matches + cta_matches
        keyword_score = min(total_keywords / 5.0, 1.0)  # Normalize

        # Transition features
        has_intro = self._has_pattern(text[:200], self.intro_patterns) if len(text) > 200 else self._has_pattern(text, self.intro_patterns)
        has_outro = self._has_pattern(text[-200:], self.outro_patterns) if len(text) > 200 else False

        # Duration features
        is_standard = self._is_standard_duration(duration)

        # Context features
        sim_before = self._compute_topic_similarity(text, text_before)
        sim_after = self._compute_topic_similarity(text, text_after)
        is_island = sim_before < 0.4 and sim_after < 0.4

        # Compute confidence
        confidence = self._compute_confidence(
            keyword_score=keyword_score,
            has_sponsor=sponsor_matches > 0,
            has_promo=promo_matches > 0,
            has_url=url_matches > 0,
            has_cta=cta_matches > 0,
            has_intro=has_intro,
            has_outro=has_outro,
            is_standard_length=is_standard,
            is_topic_island=is_island,
        )

        return SegmentFeatures(
            keyword_count=total_keywords,
            keyword_score=keyword_score,
            has_url=url_matches > 0,
            has_promo_code=promo_matches > 0,
            has_call_to_action=cta_matches > 0,
            has_sponsor_phrase=sponsor_matches > 0,
            has_intro_transition=has_intro,
            has_outro_transition=has_outro,
            duration=duration,
            is_standard_ad_length=is_standard,
            topic_similarity_before=sim_before,
            topic_similarity_after=sim_after,
            is_topic_island=is_island,
            confidence=confidence,
        )

    def _compute_confidence(
        self,
        keyword_score: float,
        has_sponsor: bool,
        has_promo: bool,
        has_url: bool,
        has_cta: bool,
        has_intro: bool,
        has_outro: bool,
        is_standard_length: bool,
        is_topic_island: bool,
    ) -> float:
        """
        Compute ad confidence score.

        Weighted combination of features with domain knowledge.
        """
        score = 0.0

        # Strong indicators (high weight)
        if has_sponsor:
            score += 0.35  # "Brought to you by" is very strong
        if has_promo:
            score += 0.25  # Promo codes are definitive

        # Medium indicators
        if has_url:
            score += 0.15
        if has_cta:
            score += 0.15

        # Weak but supportive indicators
        if has_intro:
            score += 0.10
        if has_outro:
            score += 0.05
        if is_standard_length:
            score += 0.10
        if is_topic_island:
            score += 0.15

        # Keyword density bonus
        score += keyword_score * 0.20

        return min(score, 1.0)

    def classify(
        self,
        text: str,
        duration: float,
        text_before: str = "",
        text_after: str = "",
        threshold: float = 0.4,
    ) -> tuple[bool, float, SegmentFeatures]:
        """
        Classify a segment as ad or content.

        Returns:
            (is_ad, confidence, features)
        """
        features = self.extract_features(text, duration, text_before, text_after)
        is_ad = features.confidence >= threshold

        return is_ad, features.confidence, features

    def classify_segments(
        self,
        segments: list[dict],
        transcript: list[dict],
        threshold: float = 0.4,
    ) -> list[dict]:
        """
        Classify multiple segments.

        Args:
            segments: List of {"start": float, "end": float} boundaries
            transcript: Full transcript with text
            threshold: Classification threshold

        Returns:
            List of ad segments with classification details
        """
        ads = []

        for i, seg in enumerate(segments):
            start, end = seg["start"], seg["end"]
            duration = end - start

            # Get text for this segment
            seg_text = " ".join([
                t["text"] for t in transcript
                if start <= t["start"] < end
            ])

            # Get context text
            text_before = " ".join([
                t["text"] for t in transcript
                if start - 60 <= t["start"] < start
            ])
            text_after = " ".join([
                t["text"] for t in transcript
                if end <= t["start"] < end + 60
            ])

            # Classify
            is_ad, confidence, features = self.classify(
                text=seg_text,
                duration=duration,
                text_before=text_before,
                text_after=text_after,
                threshold=threshold,
            )

            if is_ad:
                ads.append({
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "confidence": round(confidence, 3),
                    "features": {
                        "keyword_count": features.keyword_count,
                        "has_sponsor": features.has_sponsor_phrase,
                        "has_promo": features.has_promo_code,
                        "has_url": features.has_url,
                        "has_cta": features.has_call_to_action,
                        "has_intro": features.has_intro_transition,
                        "has_outro": features.has_outro_transition,
                        "is_standard_length": features.is_standard_ad_length,
                        "is_topic_island": features.is_topic_island,
                        "topic_sim_before": round(features.topic_similarity_before, 3),
                        "topic_sim_after": round(features.topic_similarity_after, 3),
                    }
                })

        return ads


def test_classifier():
    """Test the classifier on example texts."""
    classifier = AdClassifier()

    test_cases = [
        # Clear ad
        (
            "This episode is brought to you by Progressive Insurance. "
            "Get a quote at progressive.com and save up to 30% on your car insurance. "
            "Use code PODCAST for an extra discount.",
            60.0,
            True,
        ),
        # Clear content
        (
            "So the dragon landed on the castle and the party had to decide "
            "whether to fight or run. The barbarian wanted to fight of course "
            "but the wizard suggested a more diplomatic approach.",
            45.0,
            False,
        ),
        # Borderline - product mention but not ad
        (
            "I was using Google Maps the other day to find this restaurant "
            "and it took me to completely the wrong place. Has that ever "
            "happened to you?",
            30.0,
            False,
        ),
        # Clear ad with promo code
        (
            "BetterHelp is online therapy that matches you with a licensed therapist. "
            "Visit betterhelp.com/show and get 10% off your first month. "
            "That's betterhelp.com/show for 10% off.",
            45.0,
            True,
        ),
    ]

    print("=" * 60)
    print("AD CLASSIFIER TEST")
    print("=" * 60)

    for text, duration, expected in test_cases:
        is_ad, confidence, features = classifier.classify(text, duration)

        status = "✓" if is_ad == expected else "✗"
        print(f"\n{status} Expected: {'AD' if expected else 'CONTENT'}, "
              f"Got: {'AD' if is_ad else 'CONTENT'} ({confidence:.0%})")
        print(f"  Text: {text[:80]}...")
        print(f"  Duration: {duration}s")
        print(f"  Features: sponsor={features.has_sponsor_phrase}, "
              f"promo={features.has_promo_code}, url={features.has_url}, "
              f"cta={features.has_call_to_action}")


if __name__ == "__main__":
    test_classifier()
