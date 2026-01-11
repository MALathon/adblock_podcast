import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import type { Episode, Podcast } from '$lib/types';

/**
 * Get podcast details and episodes from iTunes + RSS feed
 * GET /api/podcast/[id]
 */
export const GET: RequestHandler = async ({ params }) => {
  const { id } = params;

  try {
    // First, get podcast info from iTunes
    const lookupUrl = `https://itunes.apple.com/lookup?id=${id}`;
    const lookupResponse = await fetch(lookupUrl);

    if (!lookupResponse.ok) {
      return json({ error: 'Podcast not found' }, { status: 404 });
    }

    const lookupData = await lookupResponse.json();

    if (!lookupData.results || lookupData.results.length === 0) {
      return json({ error: 'Podcast not found' }, { status: 404 });
    }

    const result = lookupData.results[0];

    const podcast: Podcast = {
      id: result.collectionId.toString(),
      title: result.collectionName,
      artist: result.artistName,
      artworkUrl: result.artworkUrl600 || result.artworkUrl100,
      feedUrl: result.feedUrl,
      description: result.collectionViewUrl,
      genre: result.primaryGenreName
    };

    // Fetch and parse RSS feed for episodes
    const episodes = await fetchEpisodes(result.feedUrl, podcast);

    return json({ podcast, episodes });
  } catch (error) {
    console.error('Error fetching podcast:', error);
    return json({ error: 'Failed to fetch podcast' }, { status: 500 });
  }
};

async function fetchEpisodes(feedUrl: string, podcast: Podcast): Promise<Episode[]> {
  try {
    const response = await fetch(feedUrl, {
      headers: {
        'User-Agent': 'AdBlockPodcast/1.0'
      }
    });

    if (!response.ok) {
      console.error('RSS feed error:', response.status);
      return [];
    }

    const xml = await response.text();
    return parseRssFeed(xml, podcast);
  } catch (error) {
    console.error('Error fetching RSS feed:', error);
    return [];
  }
}

function parseRssFeed(xml: string, podcast: Podcast): Episode[] {
  const episodes: Episode[] = [];

  // Simple XML parsing without external dependencies
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

    // Get audio URL from enclosure
    const enclosureMatch = itemContent.match(/<enclosure[^>]*url="([^"]*)"[^>]*>/);
    const audioUrl = enclosureMatch ? enclosureMatch[1] : '';

    // Get episode artwork or fallback to podcast artwork
    const imageMatch = itemContent.match(/<itunes:image[^>]*href="([^"]*)"[^>]*\/?>/);
    const artworkUrl = imageMatch ? imageMatch[1] : podcast.artworkUrl;

    // Generate unique ID from title hash or use GUID
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
  // Try CDATA first
  const cdataRegex = new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`, 'i');
  const cdataMatch = xml.match(cdataRegex);
  if (cdataMatch) return cdataMatch[1].trim();

  // Try regular tag
  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const match = xml.match(regex);
  return match ? match[1].trim() : '';
}

function cleanHtml(text: string): string {
  if (!text) return '';
  // Remove HTML tags
  return text.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
}

function parseDuration(duration: string): number {
  if (!duration) return 0;

  // If it's already in seconds
  if (/^\d+$/.test(duration)) {
    return parseInt(duration, 10);
  }

  // Parse HH:MM:SS or MM:SS format
  const parts = duration.split(':').map(p => parseInt(p, 10));

  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }

  return 0;
}
