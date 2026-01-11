/**
 * Subscriptions API
 * GET  /api/subscriptions - List all subscriptions
 * POST /api/subscriptions - Subscribe to a podcast
 */
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getAllSubscriptions, subscribe, isSubscribed } from '$lib/db/subscriptions';
import { upsertEpisodes } from '$lib/db/episodes';
import type { Podcast, Episode } from '$lib/types';

export const GET: RequestHandler = async () => {
  const subscriptions = getAllSubscriptions();
  return json(subscriptions);
};

export const POST: RequestHandler = async ({ request }) => {
  const podcast: Podcast = await request.json();

  if (!podcast.id || !podcast.feedUrl) {
    return json({ error: 'Invalid podcast data' }, { status: 400 });
  }

  if (isSubscribed(podcast.id)) {
    return json({ error: 'Already subscribed' }, { status: 409 });
  }

  // Subscribe to podcast
  const subscription = subscribe(podcast);

  // Fetch and store episodes (but don't auto-queue - let user select)
  try {
    const episodes = await fetchEpisodes(podcast.feedUrl, podcast);
    if (episodes.length > 0) {
      upsertEpisodes(episodes);
      console.log(`[Subscription] Stored ${episodes.length} episodes`);
    }
  } catch (error) {
    console.error('[Subscription] Failed to fetch episodes:', error);
  }

  return json(subscription, { status: 201 });
};

// Fetch episodes from RSS feed
async function fetchEpisodes(feedUrl: string, podcast: Podcast): Promise<Episode[]> {
  const response = await fetch(feedUrl, {
    headers: { 'User-Agent': 'AdBlockPodcast/1.0' }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch feed: ${response.status}`);
  }

  const xml = await response.text();
  return parseRssFeed(xml, podcast);
}

function parseRssFeed(xml: string, podcast: Podcast): Episode[] {
  const episodes: Episode[] = [];
  const itemRegex = /<item>([\s\S]*?)<\/item>/g;
  let itemMatch;
  let index = 0;

  while ((itemMatch = itemRegex.exec(xml)) !== null) {
    const itemContent = itemMatch[1];

    const title = extractXmlValue(itemContent, 'title');
    const description = extractXmlValue(itemContent, 'description') ||
                       extractXmlValue(itemContent, 'itunes:summary');
    const pubDate = extractXmlValue(itemContent, 'pubDate');
    const duration = parseDuration(extractXmlValue(itemContent, 'itunes:duration'));

    const enclosureMatch = itemContent.match(/<enclosure[^>]*url="([^"]*)"[^>]*>/);
    const audioUrl = enclosureMatch ? enclosureMatch[1] : '';

    const imageMatch = itemContent.match(/<itunes:image[^>]*href="([^"]*)"[^>]*\/?>/);
    const artworkUrl = imageMatch ? imageMatch[1] : podcast.artworkUrl;

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

function extractXmlValue(xml: string, tag: string): string {
  const cdataRegex = new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`, 'i');
  const cdataMatch = xml.match(cdataRegex);
  if (cdataMatch) return cdataMatch[1].trim();

  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const match = xml.match(regex);
  return match ? match[1].trim() : '';
}

function cleanHtml(text: string): string {
  if (!text) return '';
  return text
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function parseDuration(duration: string): number {
  if (!duration) return 0;
  if (/^\d+$/.test(duration)) return parseInt(duration, 10);

  const parts = duration.split(':').map(p => parseInt(p, 10));
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}
