#!/usr/bin/env python3
"""
Fetch diverse podcast samples from iTunes API for benchmarking.

Gets episodes across all major categories for comprehensive testing.
"""

import json
import os
import random
import requests
import time
import feedparser
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


# iTunes podcast categories
CATEGORIES = [
    "Arts",
    "Business",
    "Comedy",
    "Education",
    "Fiction",
    "Health & Fitness",
    "History",
    "Kids & Family",
    "Leisure",
    "Music",
    "News",
    "Religion & Spirituality",
    "Science",
    "Society & Culture",
    "Sports",
    "Technology",
    "True Crime",
    "TV & Film",
]

# Popular search terms per category to find diverse content
SEARCH_TERMS = {
    "Arts": ["art history", "design", "photography", "creative"],
    "Business": ["entrepreneur", "investing", "marketing", "startup"],
    "Comedy": ["funny", "standup", "humor", "jokes"],
    "Education": ["learning", "teaching", "knowledge", "courses"],
    "Fiction": ["storytelling", "drama", "audio fiction", "narrative"],
    "Health & Fitness": ["wellness", "fitness", "mental health", "nutrition"],
    "History": ["historical", "ancient", "world war", "civilization"],
    "Kids & Family": ["children", "parenting", "family stories", "kids"],
    "Leisure": ["hobbies", "games", "crafts", "travel"],
    "Music": ["music history", "songs", "musicians", "albums"],
    "News": ["daily news", "politics", "current events", "journalism"],
    "Religion & Spirituality": ["faith", "spirituality", "meditation", "religious"],
    "Science": ["scientific", "research", "discovery", "physics"],
    "Society & Culture": ["culture", "social", "relationships", "documentary"],
    "Sports": ["football", "basketball", "soccer", "athletics"],
    "Technology": ["tech news", "programming", "gadgets", "AI"],
    "True Crime": ["crime", "murder", "investigation", "mystery"],
    "TV & Film": ["movies", "television", "film review", "cinema"],
}


@dataclass
class PodcastEpisode:
    podcast_name: str
    podcast_id: str
    episode_title: str
    episode_url: str
    duration_seconds: int
    category: str
    feed_url: str


def search_itunes(term: str, limit: int = 10) -> list[dict]:
    """Search iTunes for podcasts."""
    url = "https://itunes.apple.com/search"
    params = {
        "term": term,
        "media": "podcast",
        "entity": "podcast",
        "limit": limit,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"  Error searching '{term}': {e}")
        return []


def get_podcast_episodes(feed_url: str, max_episodes: int = 5) -> list[dict]:
    """Get episodes from podcast RSS feed."""
    try:
        feed = feedparser.parse(feed_url)
        episodes = []

        for entry in feed.entries[:max_episodes]:
            # Find audio enclosure
            audio_url = None
            duration = 0

            for enclosure in entry.get("enclosures", []):
                if "audio" in enclosure.get("type", ""):
                    audio_url = enclosure.get("href")
                    break

            # Try to get duration
            if hasattr(entry, "itunes_duration"):
                dur = entry.itunes_duration
                if isinstance(dur, str):
                    parts = dur.split(":")
                    if len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    else:
                        try:
                            duration = int(dur)
                        except:
                            pass
                else:
                    duration = int(dur) if dur else 0

            if audio_url:
                episodes.append({
                    "title": entry.get("title", "Unknown"),
                    "url": audio_url,
                    "duration": duration,
                })

        return episodes
    except Exception as e:
        print(f"  Error parsing feed: {e}")
        return []


def fetch_diverse_podcasts(
    episodes_per_category: int = 6,
    min_duration: int = 1200,  # 20 minutes minimum
    max_duration: int = 7200,  # 2 hours maximum
    output_file: str = "podcast_samples.json",
) -> list[PodcastEpisode]:
    """
    Fetch diverse podcast episodes across all categories.

    Args:
        episodes_per_category: Target episodes per category
        min_duration: Minimum episode duration in seconds
        max_duration: Maximum episode duration in seconds
        output_file: Where to save results

    Returns:
        List of PodcastEpisode objects
    """
    all_episodes = []

    print(f"Fetching podcasts across {len(CATEGORIES)} categories...")
    print(f"Target: {episodes_per_category} episodes per category = {len(CATEGORIES) * episodes_per_category} total")
    print(f"Duration filter: {min_duration//60}-{max_duration//60} minutes")
    print("=" * 60)

    for category in CATEGORIES:
        print(f"\n[{category}]")
        category_episodes = []
        search_terms = SEARCH_TERMS.get(category, [category.lower()])

        for term in search_terms:
            if len(category_episodes) >= episodes_per_category:
                break

            print(f"  Searching: '{term}'...")
            podcasts = search_itunes(f"{term} podcast", limit=5)

            for podcast in podcasts:
                if len(category_episodes) >= episodes_per_category:
                    break

                feed_url = podcast.get("feedUrl")
                if not feed_url:
                    continue

                podcast_name = podcast.get("collectionName", "Unknown")
                podcast_id = str(podcast.get("collectionId", ""))

                # Get episodes
                episodes = get_podcast_episodes(feed_url, max_episodes=3)

                for ep in episodes:
                    if len(category_episodes) >= episodes_per_category:
                        break

                    duration = ep.get("duration", 0)

                    # Filter by duration
                    if duration < min_duration or duration > max_duration:
                        continue

                    episode = PodcastEpisode(
                        podcast_name=podcast_name,
                        podcast_id=podcast_id,
                        episode_title=ep["title"],
                        episode_url=ep["url"],
                        duration_seconds=duration,
                        category=category,
                        feed_url=feed_url,
                    )

                    category_episodes.append(episode)
                    print(f"    + {podcast_name}: {ep['title'][:40]}... ({duration//60}m)")

            time.sleep(0.5)  # Rate limiting

        all_episodes.extend(category_episodes)
        print(f"  Found {len(category_episodes)} episodes for {category}")

    # Shuffle for randomness
    random.shuffle(all_episodes)

    # Save to file
    output_data = {
        "metadata": {
            "total_episodes": len(all_episodes),
            "categories": len(CATEGORIES),
            "episodes_per_category": episodes_per_category,
            "min_duration": min_duration,
            "max_duration": max_duration,
        },
        "episodes": [
            {
                "podcast_name": ep.podcast_name,
                "podcast_id": ep.podcast_id,
                "episode_title": ep.episode_title,
                "episode_url": ep.episode_url,
                "duration_seconds": ep.duration_seconds,
                "category": ep.category,
                "feed_url": ep.feed_url,
            }
            for ep in all_episodes
        ]
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total episodes: {len(all_episodes)}")
    print(f"Saved to: {output_file}")

    # Category breakdown
    by_category = {}
    for ep in all_episodes:
        by_category[ep.category] = by_category.get(ep.category, 0) + 1

    print(f"\nBy category:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat}: {count}")

    return all_episodes


def download_episode(episode: dict, output_dir: str = "/tmp/podcast_samples") -> Optional[str]:
    """Download a podcast episode."""
    os.makedirs(output_dir, exist_ok=True)

    # Create filename
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in episode["episode_title"])
    filename = f"{episode['podcast_id']}_{safe_name[:50]}.mp3"
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        print(f"  Already downloaded: {filename}")
        return filepath

    try:
        print(f"  Downloading: {episode['episode_title'][:50]}...")
        response = requests.get(episode["episode_url"], stream=True, timeout=60)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  Saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"  Error downloading: {e}")
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch diverse podcast samples")
    parser.add_argument("--episodes-per-category", type=int, default=6)
    parser.add_argument("--output", type=str, default="podcast_samples.json")
    parser.add_argument("--download", action="store_true", help="Also download audio files")
    parser.add_argument("--download-limit", type=int, default=10, help="Max episodes to download")

    args = parser.parse_args()

    episodes = fetch_diverse_podcasts(
        episodes_per_category=args.episodes_per_category,
        output_file=args.output,
    )

    if args.download and episodes:
        print(f"\n{'='*60}")
        print(f"DOWNLOADING SAMPLES")
        print(f"{'='*60}")

        # Load from file to get dict format
        with open(args.output) as f:
            data = json.load(f)

        downloaded = 0
        for ep in data["episodes"][:args.download_limit]:
            result = download_episode(ep)
            if result:
                downloaded += 1

        print(f"\nDownloaded {downloaded} episodes")
