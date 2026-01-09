#!/usr/bin/env python3
"""Read cached transcript and show key sections for ground truth review"""
import json

with open("/tmp/transcript_cache.json") as f:
    transcript = json.load(f)

print(f"Total segments: {len(transcript)}")
print(f"Duration: {transcript[-1]['end']/60:.1f} min")

def show_section(title, start_sec, end_sec):
    print(f"\n{'='*60}")
    print(title)
    print('='*60)
    for seg in transcript:
        if start_sec <= seg['start'] <= end_sec:
            mins = int(seg['start'] // 60)
            secs = int(seg['start'] % 60)
            print(f"[{mins:02d}:{secs:02d}] {seg['text']}")

# Key sections to review
show_section("PRE-ROLL (0:00 - 2:00)", 0, 120)
show_section("AROUND 23-24 MIN (potential mid-roll)", 1380, 1500)
show_section("AROUND 30-35 MIN (potential mid-roll)", 1800, 2100)
show_section("AROUND 77-82 MIN (potential mid-roll)", 4620, 4920)
