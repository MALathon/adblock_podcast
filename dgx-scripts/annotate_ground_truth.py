#!/usr/bin/env python3
"""
Ground Truth Annotation Tool

Semi-automated workflow for annotating ad segments:
1. Run fast ad detection to get candidate segments
2. Present candidates for human verification
3. Allow manual adjustment of start/end times
4. Save ground truth JSON

For headless servers, outputs a review file that can be annotated locally.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class AdAnnotation:
    start: float
    end: float
    label: str  # "ad", "self_promo", "content"
    confidence: str  # "certain", "likely", "unsure"
    notes: str = ""


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except:
        return 0.0


def extract_audio_clips(
    audio_path: str,
    segments: list[dict],
    output_dir: str,
    context_seconds: float = 5.0,
) -> list[str]:
    """Extract audio clips for each candidate segment with context."""
    os.makedirs(output_dir, exist_ok=True)
    clips = []

    for i, seg in enumerate(segments):
        start = max(0, seg["start"] - context_seconds)
        end = seg["end"] + context_seconds

        clip_path = os.path.join(output_dir, f"segment_{i:03d}_{start:.0f}s_{end:.0f}s.mp3")

        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", audio_path,
                "-ss", str(start), "-to", str(end),
                "-acodec", "libmp3lame", "-q:a", "4",
                clip_path
            ], capture_output=True, timeout=60)

            clips.append({
                "clip_path": clip_path,
                "original_start": seg["start"],
                "original_end": seg["end"],
                "clip_start": start,
                "clip_end": end,
                "detection_confidence": seg.get("confidence", 0),
            })
        except Exception as e:
            print(f"  Error extracting clip {i}: {e}")

    return clips


def run_initial_detection(audio_path: str, transcript_path: Optional[str] = None) -> list[dict]:
    """Run our detector to get initial candidates."""
    # If we have a transcript, use our two-stage detector
    if transcript_path and os.path.exists(transcript_path):
        try:
            from llm_detector import LLMAdDetector

            with open(transcript_path) as f:
                transcript = json.load(f)

            detector = LLMAdDetector(
                model="qwen3-coder:latest",
                window_size=60.0,
                window_hop=30.0,
            )

            return detector.detect(transcript)
        except ImportError:
            pass

    # Fallback: return empty (user marks from scratch)
    return []


def create_annotation_template(
    audio_path: str,
    candidates: list[dict],
    output_file: str,
):
    """Create annotation template file for manual review."""
    duration = get_audio_duration(audio_path)

    template = {
        "audio_file": audio_path,
        "audio_duration_seconds": duration,
        "audio_duration_formatted": f"{int(duration//60)}:{int(duration%60):02d}",
        "instructions": """
ANNOTATION INSTRUCTIONS:
1. Listen to each candidate segment
2. Update 'verified_label' to: "ad", "self_promo", or "content"
3. Adjust 'verified_start' and 'verified_end' if needed
4. Set 'confidence' to: "certain", "likely", or "unsure"
5. Add any notes about the segment
6. Add any MISSED ads to the 'additional_ads' section

Labels:
- ad: External sponsor/advertisement
- self_promo: Host promoting their own show/products
- content: Regular podcast content (false positive)
        """,
        "candidates": [
            {
                "index": i,
                "detected_start": seg.get("start", 0),
                "detected_end": seg.get("end", 0),
                "detected_start_formatted": f"{int(seg.get('start', 0)//60)}:{int(seg.get('start', 0)%60):02d}",
                "detected_end_formatted": f"{int(seg.get('end', 0)//60)}:{int(seg.get('end', 0)%60):02d}",
                "detection_confidence": seg.get("confidence", 0),
                "text_preview": seg.get("text_preview", "")[:200],
                # Fields to fill in:
                "verified_label": "ad",  # Change to: "ad", "self_promo", or "content"
                "verified_start": seg.get("start", 0),  # Adjust if needed
                "verified_end": seg.get("end", 0),  # Adjust if needed
                "confidence": "likely",  # Change to: "certain", "likely", "unsure"
                "notes": "",
            }
            for i, seg in enumerate(candidates)
        ],
        "additional_ads": [
            # Add any ads that were MISSED by detection
            # {"start": 0, "end": 0, "label": "ad", "notes": ""}
        ],
        "annotator": "",
        "annotation_date": "",
    }

    with open(output_file, "w") as f:
        json.dump(template, f, indent=2)

    print(f"\nAnnotation template saved to: {output_file}")
    print(f"\nInstructions:")
    print(f"1. Open {output_file} in a text editor")
    print(f"2. Listen to the audio file: {audio_path}")
    print(f"3. Review each candidate and update the verified_* fields")
    print(f"4. Add any missed ads to additional_ads section")
    print(f"5. Save the file when done")

    return template


def process_annotations(annotation_file: str) -> dict:
    """Process completed annotations into ground truth format."""
    with open(annotation_file) as f:
        data = json.load(f)

    ground_truth = {
        "audio_file": data["audio_file"],
        "audio_duration": data["audio_duration_seconds"],
        "ads": [],
        "self_promos": [],
        "false_positives": [],
    }

    # Process candidates
    for candidate in data.get("candidates", []):
        label = candidate.get("verified_label", "content")
        segment = {
            "start": candidate.get("verified_start", candidate.get("detected_start", 0)),
            "end": candidate.get("verified_end", candidate.get("detected_end", 0)),
            "confidence": candidate.get("confidence", "likely"),
            "notes": candidate.get("notes", ""),
        }

        if label == "ad":
            ground_truth["ads"].append(segment)
        elif label == "self_promo":
            ground_truth["self_promos"].append(segment)
        elif label == "content":
            ground_truth["false_positives"].append(segment)

    # Process additional ads
    for ad in data.get("additional_ads", []):
        if ad.get("start", 0) > 0 or ad.get("end", 0) > 0:
            ground_truth["ads"].append({
                "start": ad["start"],
                "end": ad["end"],
                "confidence": "certain",
                "notes": ad.get("notes", "manually added"),
            })

    return ground_truth


def batch_create_annotations(
    podcast_samples_file: str,
    audio_dir: str,
    transcript_dir: str,
    output_dir: str,
):
    """Create annotation templates for all podcasts in a batch."""
    with open(podcast_samples_file) as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    for i, episode in enumerate(data.get("episodes", [])):
        podcast_id = episode.get("podcast_id", f"unknown_{i}")
        safe_title = "".join(c if c.isalnum() or c in "._- " else "_"
                           for c in episode.get("episode_title", "")[:30])

        audio_path = os.path.join(audio_dir, f"{podcast_id}_{safe_title}.mp3")
        transcript_path = os.path.join(transcript_dir, f"{podcast_id}_{safe_title}.json")
        annotation_path = os.path.join(output_dir, f"annotation_{podcast_id}_{safe_title}.json")

        if not os.path.exists(audio_path):
            print(f"  Skipping {podcast_id}: audio not found")
            continue

        if os.path.exists(annotation_path):
            print(f"  Skipping {podcast_id}: annotation exists")
            continue

        print(f"\n[{i+1}] Creating annotation for: {episode.get('episode_title', '')[:50]}")

        # Run detection
        candidates = run_initial_detection(audio_path, transcript_path)

        # Create template
        create_annotation_template(audio_path, candidates, annotation_path)


def compile_ground_truth(annotations_dir: str, output_file: str):
    """Compile all annotations into a single ground truth file."""
    all_ground_truth = []

    for filename in os.listdir(annotations_dir):
        if not filename.startswith("annotation_") or not filename.endswith(".json"):
            continue

        filepath = os.path.join(annotations_dir, filename)

        try:
            gt = process_annotations(filepath)
            all_ground_truth.append(gt)
            print(f"  Processed: {filename} - {len(gt['ads'])} ads")
        except Exception as e:
            print(f"  Error processing {filename}: {e}")

    with open(output_file, "w") as f:
        json.dump({
            "total_files": len(all_ground_truth),
            "total_ads": sum(len(gt["ads"]) for gt in all_ground_truth),
            "ground_truth": all_ground_truth,
        }, f, indent=2)

    print(f"\nCompiled {len(all_ground_truth)} files to: {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ground truth annotation tool")
    subparsers = parser.add_subparsers(dest="command")

    # Create single annotation
    create_parser = subparsers.add_parser("create", help="Create annotation template")
    create_parser.add_argument("audio_file", help="Audio file path")
    create_parser.add_argument("--transcript", help="Transcript JSON path")
    create_parser.add_argument("--output", default="annotation.json", help="Output file")

    # Batch create
    batch_parser = subparsers.add_parser("batch", help="Batch create annotations")
    batch_parser.add_argument("samples_file", help="podcast_samples.json file")
    batch_parser.add_argument("--audio-dir", required=True, help="Directory with audio files")
    batch_parser.add_argument("--transcript-dir", required=True, help="Directory with transcripts")
    batch_parser.add_argument("--output-dir", default="annotations", help="Output directory")

    # Compile
    compile_parser = subparsers.add_parser("compile", help="Compile annotations to ground truth")
    compile_parser.add_argument("annotations_dir", help="Directory with annotation files")
    compile_parser.add_argument("--output", default="ground_truth.json", help="Output file")

    args = parser.parse_args()

    if args.command == "create":
        candidates = run_initial_detection(args.audio_file, args.transcript)
        create_annotation_template(args.audio_file, candidates, args.output)

    elif args.command == "batch":
        batch_create_annotations(
            args.samples_file,
            args.audio_dir,
            args.transcript_dir,
            args.output_dir,
        )

    elif args.command == "compile":
        compile_ground_truth(args.annotations_dir, args.output)

    else:
        parser.print_help()
