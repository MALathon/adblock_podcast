/**
 * RSS Feed parsing service
 *
 * Handles fetching and parsing podcast RSS feeds.
 */

import type { Podcast, Episode } from '$lib/types';
import { extractXmlValue, extractXmlAttribute, cleanHtml, parseDuration } from '$lib/utils/xml';
import { API_CONFIG } from '$lib/utils/config';

/**
 * Fetch and parse episodes from an RSS feed
 */
export async function fetchEpisodes(feedUrl: string, podcast: Podcast): Promise<Episode[]> {
  const response = await fetch(feedUrl, {
    headers: { 'User-Agent': API_CONFIG.userAgent }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch feed: ${response.status}`);
  }

  const xml = await response.text();
  return parseRssFeed(xml, podcast);
}

/**
 * Parse RSS feed XML into Episode objects
 */
export function parseRssFeed(xml: string, podcast: Podcast): Episode[] {
  const episodes: Episode[] = [];
  const itemRegex = /<item>([\s\S]*?)<\/item>/g;
  let itemMatch;
  let index = 0;

  while ((itemMatch = itemRegex.exec(xml)) !== null) {
    const itemContent = itemMatch[1];

    const title = extractXmlValue(itemContent, 'title');
    const description =
      extractXmlValue(itemContent, 'description') ||
      extractXmlValue(itemContent, 'itunes:summary');
    const pubDate = extractXmlValue(itemContent, 'pubDate');
    const duration = parseDuration(extractXmlValue(itemContent, 'itunes:duration'));

    const audioUrl = extractXmlAttribute(itemContent, 'enclosure', 'url');
    const artworkUrl =
      extractXmlAttribute(itemContent, 'itunes:image', 'href') || podcast.artworkUrl;
    const guid = extractXmlValue(itemContent, 'guid') || `${podcast.id}-${index}`;

    if (audioUrl) {
      episodes.push({
        id: guid,
        title: cleanHtml(title),
        description: cleanHtml(description),
        pubDate,
        duration,
        audioUrl,
        artworkUrl,
        podcastId: podcast.id,
        podcastTitle: podcast.title
      });
    }

    index++;
  }

  return episodes;
}

/**
 * Extract podcast metadata from RSS feed
 */
export function parsePodcastMetadata(xml: string): Partial<Podcast> {
  const channelMatch = xml.match(/<channel>([\s\S]*?)<\/channel>/);
  if (!channelMatch) return {};

  const channel = channelMatch[1];

  return {
    title: cleanHtml(extractXmlValue(channel, 'title')),
    description: cleanHtml(
      extractXmlValue(channel, 'description') ||
        extractXmlValue(channel, 'itunes:summary')
    ),
    artist:
      extractXmlValue(channel, 'itunes:author') ||
      extractXmlValue(channel, 'managingEditor'),
    artworkUrl: extractXmlAttribute(channel, 'itunes:image', 'href'),
    genre: extractXmlAttribute(channel, 'itunes:category', 'text')
  };
}
