import { describe, it, expect } from 'vitest';
import { parseRssFeed, parsePodcastMetadata } from '$lib/services/rss';
import type { Podcast } from '$lib/types';

const mockPodcast: Podcast = {
  id: 'podcast-123',
  title: 'Test Podcast',
  feedUrl: 'https://example.com/feed.xml',
  artist: 'Test Artist',
  artworkUrl: 'https://example.com/art.jpg'
};

const sampleRssFeed = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Test Podcast</title>
    <itunes:summary>A test podcast for unit testing</itunes:summary>
    <itunes:author>Test Author</itunes:author>
    <itunes:image href="https://example.com/artwork.jpg"/>
    <itunes:category text="Technology"/>

    <item>
      <title>Episode 1: Introduction</title>
      <description><![CDATA[<p>This is the first episode</p>]]></description>
      <pubDate>Mon, 15 Jan 2024 12:00:00 GMT</pubDate>
      <itunes:duration>1:30:00</itunes:duration>
      <enclosure url="https://example.com/ep1.mp3" type="audio/mpeg" length="54000000"/>
      <guid>ep1-guid</guid>
    </item>

    <item>
      <title>Episode 2: Deep Dive</title>
      <description>Episode with plain text description</description>
      <pubDate>Mon, 22 Jan 2024 12:00:00 GMT</pubDate>
      <itunes:duration>45:30</itunes:duration>
      <enclosure url="https://example.com/ep2.mp3" type="audio/mpeg" length="27000000"/>
      <guid>ep2-guid</guid>
      <itunes:image href="https://example.com/ep2-art.jpg"/>
    </item>

    <item>
      <title>Episode 3: No Audio</title>
      <description>This episode has no enclosure</description>
      <pubDate>Mon, 29 Jan 2024 12:00:00 GMT</pubDate>
      <guid>ep3-guid</guid>
    </item>
  </channel>
</rss>`;

describe('parseRssFeed', () => {
  it('parses episodes from RSS feed', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes).toHaveLength(2); // ep3 has no audio, so excluded
  });

  it('extracts episode titles', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].title).toBe('Episode 1: Introduction');
    expect(episodes[1].title).toBe('Episode 2: Deep Dive');
  });

  it('strips HTML from CDATA descriptions', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].description).toBe('This is the first episode');
  });

  it('extracts plain text descriptions', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[1].description).toBe('Episode with plain text description');
  });

  it('parses duration in HH:MM:SS format', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].duration).toBe(5400); // 1:30:00 = 5400 seconds
  });

  it('parses duration in MM:SS format', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[1].duration).toBe(2730); // 45:30 = 2730 seconds
  });

  it('extracts audio URL from enclosure', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].audioUrl).toBe('https://example.com/ep1.mp3');
    expect(episodes[1].audioUrl).toBe('https://example.com/ep2.mp3');
  });

  it('extracts episode GUID', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].id).toBe('ep1-guid');
    expect(episodes[1].id).toBe('ep2-guid');
  });

  it('extracts publication date', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].pubDate).toContain('15 Jan 2024');
  });

  it('uses episode artwork when available', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[1].artworkUrl).toBe('https://example.com/ep2-art.jpg');
  });

  it('falls back to podcast artwork', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].artworkUrl).toBe(mockPodcast.artworkUrl);
  });

  it('sets podcast reference', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    expect(episodes[0].podcastId).toBe('podcast-123');
    expect(episodes[0].podcastTitle).toBe('Test Podcast');
  });

  it('skips items without audio enclosure', () => {
    const episodes = parseRssFeed(sampleRssFeed, mockPodcast);
    const ep3 = episodes.find(e => e.id === 'ep3-guid');
    expect(ep3).toBeUndefined();
  });

  it('handles empty feed', () => {
    const emptyFeed = '<rss><channel></channel></rss>';
    const episodes = parseRssFeed(emptyFeed, mockPodcast);
    expect(episodes).toHaveLength(0);
  });

  it('generates fallback GUID from podcast ID and index', () => {
    const feedWithoutGuid = `<rss><channel>
      <item>
        <title>No GUID Episode</title>
        <enclosure url="https://example.com/no-guid.mp3" type="audio/mpeg"/>
      </item>
    </channel></rss>`;
    const episodes = parseRssFeed(feedWithoutGuid, mockPodcast);
    expect(episodes[0].id).toBe('podcast-123-0');
  });
});

describe('parsePodcastMetadata', () => {
  it('extracts podcast title', () => {
    const metadata = parsePodcastMetadata(sampleRssFeed);
    expect(metadata.title).toBe('Test Podcast');
  });

  it('extracts podcast description from channel', () => {
    // Create a feed with channel-level description before items
    const feedWithChannelDesc = `<rss><channel>
      <title>Channel Test</title>
      <description>Channel level description</description>
      <item><enclosure url="http://a.mp3"/></item>
    </channel></rss>`;
    const metadata = parsePodcastMetadata(feedWithChannelDesc);
    expect(metadata.description).toBe('Channel level description');
  });

  it('extracts iTunes author', () => {
    const metadata = parsePodcastMetadata(sampleRssFeed);
    expect(metadata.artist).toBe('Test Author');
  });

  it('extracts iTunes image', () => {
    const metadata = parsePodcastMetadata(sampleRssFeed);
    expect(metadata.artworkUrl).toBe('https://example.com/artwork.jpg');
  });

  it('extracts iTunes category', () => {
    const metadata = parsePodcastMetadata(sampleRssFeed);
    expect(metadata.genre).toBe('Technology');
  });

  it('returns empty object for invalid RSS', () => {
    const metadata = parsePodcastMetadata('not xml');
    expect(metadata).toEqual({});
  });

  it('handles RSS without channel', () => {
    const metadata = parsePodcastMetadata('<rss></rss>');
    expect(metadata).toEqual({});
  });

  it('uses itunes:summary as fallback for description', () => {
    const feedWithSummary = `<rss><channel>
      <title>Summary Test</title>
      <itunes:summary>iTunes summary text</itunes:summary>
    </channel></rss>`;
    const metadata = parsePodcastMetadata(feedWithSummary);
    expect(metadata.description).toBe('iTunes summary text');
  });

  it('uses managingEditor as fallback for artist', () => {
    const feedWithEditor = `<rss><channel>
      <title>Editor Test</title>
      <managingEditor>editor@example.com</managingEditor>
    </channel></rss>`;
    const metadata = parsePodcastMetadata(feedWithEditor);
    expect(metadata.artist).toBe('editor@example.com');
  });
});

describe('RSS parsing edge cases', () => {
  it('handles encoded entities in content', () => {
    const feedWithEntities = `<rss><channel>
      <item>
        <title>Tom &amp; Jerry's Show</title>
        <enclosure url="https://example.com/audio.mp3" type="audio/mpeg"/>
      </item>
    </channel></rss>`;
    const episodes = parseRssFeed(feedWithEntities, mockPodcast);
    expect(episodes[0].title).toBe("Tom & Jerry's Show");
  });

  it('handles duration as pure seconds', () => {
    const feedWithSecondsDuration = `<rss><channel>
      <item>
        <title>Seconds Duration</title>
        <itunes:duration>3600</itunes:duration>
        <enclosure url="https://example.com/audio.mp3" type="audio/mpeg"/>
      </item>
    </channel></rss>`;
    const episodes = parseRssFeed(feedWithSecondsDuration, mockPodcast);
    expect(episodes[0].duration).toBe(3600);
  });

  it('handles very long feeds', () => {
    let longFeed = '<rss><channel>';
    for (let i = 0; i < 100; i++) {
      longFeed += `<item>
        <title>Episode ${i}</title>
        <enclosure url="https://example.com/ep${i}.mp3" type="audio/mpeg"/>
        <guid>guid-${i}</guid>
      </item>`;
    }
    longFeed += '</channel></rss>';
    const episodes = parseRssFeed(longFeed, mockPodcast);
    expect(episodes).toHaveLength(100);
  });
});
