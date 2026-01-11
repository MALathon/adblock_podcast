#!/usr/bin/env python3
"""
Direct audio feature extraction for ad detection.
No transcription needed - works on raw audio.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional
import warnings

# Optional imports
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("Warning: librosa not installed. Audio features disabled.")

try:
    from pyannote.audio import Pipeline
    HAS_PYANNOTE = True
except ImportError:
    HAS_PYANNOTE = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@dataclass
class AudioFrame:
    """Audio features for a time window."""
    start: float
    end: float
    energy: float           # RMS energy (volume)
    spectral_centroid: float  # Brightness
    spectral_rolloff: float   # High frequency content
    zcr: float              # Zero crossing rate (speech vs music)
    mfcc_mean: np.ndarray   # MFCC averages
    is_speech: bool         # Speech vs non-speech
    speaker_id: Optional[int] = None  # Speaker diarization


class AudioFeatureExtractor:
    """
    Extract audio features for ad detection without transcription.

    Features that help detect ads:
    - Energy changes (ads often louder/normalized differently)
    - Spectral changes (music in ad intros)
    - Voice changes (different narrator)
    - Speech vs music/silence patterns
    """

    def __init__(
        self,
        frame_duration: float = 1.0,
        hop_duration: float = 0.5,
        sample_rate: int = 16000,
        use_diarization: bool = False,
    ):
        """
        Args:
            frame_duration: Analysis window in seconds
            hop_duration: Hop between windows in seconds
            sample_rate: Audio sample rate
            use_diarization: Enable speaker diarization (slow but useful)
        """
        self.frame_duration = frame_duration
        self.hop_duration = hop_duration
        self.sample_rate = sample_rate
        self.use_diarization = use_diarization

        # Load diarization pipeline if requested
        self.diarization_pipeline = None
        if use_diarization and HAS_PYANNOTE and HAS_TORCH:
            try:
                self.diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1"
                )
                print("Loaded speaker diarization pipeline")
            except Exception as e:
                print(f"Could not load diarization: {e}")

    def load_audio(self, audio_path: str) -> tuple[np.ndarray, int]:
        """Load audio file."""
        if not HAS_LIBROSA:
            raise ImportError("librosa required for audio loading")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y, sr = librosa.load(audio_path, sr=self.sample_rate, mono=True)

        return y, sr

    def extract_frame_features(
        self,
        y: np.ndarray,
        sr: int,
        start_sample: int,
        end_sample: int
    ) -> dict:
        """Extract features for a single frame."""
        frame = y[start_sample:end_sample]

        if len(frame) == 0:
            return None

        # RMS Energy (volume)
        energy = float(np.sqrt(np.mean(frame ** 2)))

        # Spectral centroid (brightness)
        centroid = librosa.feature.spectral_centroid(y=frame, sr=sr)
        spectral_centroid = float(np.mean(centroid))

        # Spectral rolloff (high frequency content)
        rolloff = librosa.feature.spectral_rolloff(y=frame, sr=sr)
        spectral_rolloff = float(np.mean(rolloff))

        # Zero crossing rate (speech vs music indicator)
        zcr = librosa.feature.zero_crossing_rate(frame)
        zcr_mean = float(np.mean(zcr))

        # MFCCs (spectral shape)
        mfccs = librosa.feature.mfcc(y=frame, sr=sr, n_mfcc=13)
        mfcc_mean = np.mean(mfccs, axis=1)

        # Simple speech detection (based on energy and zcr)
        is_speech = energy > 0.01 and 0.02 < zcr_mean < 0.15

        return {
            'energy': energy,
            'spectral_centroid': spectral_centroid,
            'spectral_rolloff': spectral_rolloff,
            'zcr': zcr_mean,
            'mfcc_mean': mfcc_mean,
            'is_speech': is_speech,
        }

    def extract_features(self, audio_path: str) -> list[AudioFrame]:
        """
        Extract features from audio file.

        Returns list of AudioFrame objects, one per time window.
        """
        if not HAS_LIBROSA:
            raise ImportError("librosa required")

        print(f"Loading audio: {audio_path}")
        y, sr = self.load_audio(audio_path)
        duration = len(y) / sr
        print(f"Audio duration: {duration:.1f}s")

        # Calculate frame parameters
        frame_samples = int(self.frame_duration * sr)
        hop_samples = int(self.hop_duration * sr)

        frames = []
        position = 0

        print("Extracting features...")
        while position + frame_samples <= len(y):
            start_time = position / sr
            end_time = (position + frame_samples) / sr

            features = self.extract_frame_features(y, sr, position, position + frame_samples)

            if features:
                frames.append(AudioFrame(
                    start=start_time,
                    end=end_time,
                    energy=features['energy'],
                    spectral_centroid=features['spectral_centroid'],
                    spectral_rolloff=features['spectral_rolloff'],
                    zcr=features['zcr'],
                    mfcc_mean=features['mfcc_mean'],
                    is_speech=features['is_speech'],
                ))

            position += hop_samples

        print(f"Extracted {len(frames)} frames")

        # Run speaker diarization if enabled
        if self.diarization_pipeline:
            self._add_speaker_labels(audio_path, frames)

        return frames

    def _add_speaker_labels(self, audio_path: str, frames: list[AudioFrame]):
        """Add speaker labels using diarization."""
        print("Running speaker diarization...")
        try:
            diarization = self.diarization_pipeline(audio_path)

            for frame in frames:
                mid_time = (frame.start + frame.end) / 2
                # Find speaker at this time
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    if turn.start <= mid_time <= turn.end:
                        # Convert speaker label to int
                        frame.speaker_id = hash(speaker) % 100
                        break

            print("Diarization complete")
        except Exception as e:
            print(f"Diarization failed: {e}")

    def to_signal_array(self, frames: list[AudioFrame]) -> np.ndarray:
        """
        Convert frames to numpy array for change point detection.

        Returns array of shape (n_frames, n_features).
        """
        features = []
        for f in frames:
            features.append([
                f.energy,
                f.spectral_centroid / 5000,  # Normalize
                f.spectral_rolloff / 10000,   # Normalize
                f.zcr,
                float(f.is_speech),
            ])

        return np.array(features)

    def compute_change_scores(self, frames: list[AudioFrame]) -> np.ndarray:
        """
        Compute change scores between consecutive frames.

        High score = likely boundary (topic/speaker change).
        """
        if len(frames) < 2:
            return np.array([])

        scores = []
        for i in range(1, len(frames)):
            prev, curr = frames[i-1], frames[i]

            # Energy change
            energy_change = abs(curr.energy - prev.energy) / (prev.energy + 0.001)

            # Spectral change
            spectral_change = abs(curr.spectral_centroid - prev.spectral_centroid) / 5000

            # MFCC distance
            mfcc_dist = np.linalg.norm(curr.mfcc_mean - prev.mfcc_mean)

            # Speech/non-speech transition
            speech_change = float(curr.is_speech != prev.is_speech)

            # Speaker change
            speaker_change = 0.0
            if prev.speaker_id is not None and curr.speaker_id is not None:
                speaker_change = float(prev.speaker_id != curr.speaker_id)

            # Combined score
            score = (
                0.2 * min(energy_change, 1.0) +
                0.2 * min(spectral_change, 1.0) +
                0.3 * min(mfcc_dist / 50, 1.0) +
                0.15 * speech_change +
                0.15 * speaker_change
            )

            scores.append(score)

        return np.array(scores)


class AudioOnlyAdDetector:
    """
    Detect ads using only audio features (no transcription).

    Faster than transcription-based detection.
    """

    def __init__(
        self,
        frame_duration: float = 1.0,
        min_ad_duration: float = 15.0,
        use_diarization: bool = False,
    ):
        self.extractor = AudioFeatureExtractor(
            frame_duration=frame_duration,
            use_diarization=use_diarization,
        )
        self.min_ad_duration = min_ad_duration

    def detect(self, audio_path: str) -> list[dict]:
        """
        Detect ad segments from audio file.

        Returns list of {"start": float, "end": float, "confidence": float}
        """
        try:
            import ruptures as rpt
            has_ruptures = True
        except ImportError:
            has_ruptures = False

        # Extract features
        frames = self.extractor.extract_features(audio_path)
        if not frames:
            return []

        # Get signal array
        signal = self.extractor.to_signal_array(frames)
        timestamps = np.array([f.start for f in frames])

        # Detect change points
        if has_ruptures and len(signal) > 10:
            try:
                algo = rpt.Pelt(model="rbf", min_size=5).fit(signal)
                change_indices = algo.predict(pen=1.0)
                change_indices = [i for i in change_indices if i < len(frames)]
            except Exception as e:
                print(f"Ruptures error: {e}")
                change_indices = []
        else:
            change_indices = []

        # Convert to timestamps
        change_times = [frames[min(i, len(frames)-1)].start for i in change_indices]

        # Classify segments based on audio characteristics
        ads = self._classify_segments(frames, change_times)

        return ads

    def _classify_segments(
        self,
        frames: list[AudioFrame],
        change_times: list[float]
    ) -> list[dict]:
        """Classify segments as ads based on audio features."""
        if not change_times:
            return []

        # Add start/end boundaries
        boundaries = [frames[0].start] + change_times + [frames[-1].end]
        ads = []

        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            duration = end - start

            if duration < self.min_ad_duration:
                continue

            # Get frames in this segment
            seg_frames = [f for f in frames if start <= f.start < end]
            if not seg_frames:
                continue

            # Compute segment statistics
            avg_energy = np.mean([f.energy for f in seg_frames])
            energy_variance = np.var([f.energy for f in seg_frames])
            speech_ratio = np.mean([float(f.is_speech) for f in seg_frames])

            # Ad indicators:
            # - More consistent energy (normalized)
            # - High speech ratio
            # - Different spectral characteristics from surrounding

            # This is a simplified heuristic
            # Real implementation would use a trained classifier
            ad_score = 0.0

            # Consistent energy (low variance) suggests produced content
            if energy_variance < 0.01:
                ad_score += 0.3

            # High speech ratio
            if speech_ratio > 0.7:
                ad_score += 0.2

            # Check for speaker change at boundaries
            if i > 0 and len(seg_frames) > 0:
                prev_frames = [f for f in frames if boundaries[i-1] <= f.start < start]
                if prev_frames and seg_frames:
                    if prev_frames[-1].speaker_id != seg_frames[0].speaker_id:
                        ad_score += 0.3

            if ad_score > 0.3:
                ads.append({
                    "start": start,
                    "end": end,
                    "confidence": ad_score,
                    "audio_features": {
                        "avg_energy": round(avg_energy, 4),
                        "energy_variance": round(energy_variance, 6),
                        "speech_ratio": round(speech_ratio, 2),
                    }
                })

        return ads


def main():
    """Test audio feature extraction."""
    import sys

    # Test file
    audio_path = "/tmp/test_podcast.mp3"

    if len(sys.argv) > 1:
        audio_path = sys.argv[1]

    if not HAS_LIBROSA:
        print("librosa required. Install with: pip install librosa")
        return

    import os
    if not os.path.exists(audio_path):
        print(f"Audio file not found: {audio_path}")
        return

    print("=" * 60)
    print("AUDIO-ONLY AD DETECTION TEST")
    print("=" * 60)

    import time

    detector = AudioOnlyAdDetector(
        frame_duration=1.0,
        min_ad_duration=15.0,
        use_diarization=False,  # Set True if pyannote available
    )

    start = time.time()
    ads = detector.detect(audio_path)
    elapsed = time.time() - start

    print(f"\nDetection completed in {elapsed:.2f}s")
    print(f"Detected {len(ads)} potential ad segments:")

    for ad in ads:
        mins = int(ad["start"] // 60)
        secs = int(ad["start"] % 60)
        end_mins = int(ad["end"] // 60)
        end_secs = int(ad["end"] % 60)
        duration = ad["end"] - ad["start"]

        print(f"\n  [{mins:02d}:{secs:02d} - {end_mins:02d}:{end_secs:02d}] ({duration:.0f}s)")
        print(f"    Confidence: {ad['confidence']:.1%}")
        print(f"    Audio: {ad['audio_features']}")


if __name__ == "__main__":
    main()
