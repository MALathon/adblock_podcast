/**
 * RSS Feed Generator
 * GET /feed/[podcastId].xml - Generate RSS feed for podcast app subscription
 */
import type { RequestHandler } from './$types';
import { getSubscription } from '$lib/db/subscriptions';
import { getEpisodesForPodcast } from '$lib/db/episodes';
import { statSync, existsSync } from 'fs';
import { escapeXml } from '$lib/utils/xml';
import { formatTime } from '$lib/utils/format';
import { xmlResponse } from '$lib/services/api';
import { API_CONFIG } from '$lib/utils/config';

export const GET: RequestHandler = async ({ params, request }) => {
  const { podcastId } = params;

  const subscription = getSubscription(podcastId);
  if (!subscription) {
    return new Response('Podcast not found', { status: 404 });
  }

  const episodes = getEpisodesForPodcast(podcastId);

  // Get base URL from request
  const host = request.headers.get('host') || 'localhost:5173';
  const protocol = 'http'; // Local network, no SSL
  const baseUrl = `${protocol}://${host}`;

  const rss = generateRssFeed(subscription, episodes, baseUrl);
  return xmlResponse(rss, API_CONFIG.feedCacheSeconds);
};

function generateRssFeed(
  subscription: { podcastId: string; title: string; artist: string; artworkUrl: string; description?: string },
  episodes: Array<{
    id: string;
    title: string;
    description?: string;
    pubDate: string;
    duration?: number;
    processingStatus?: string;
    processedPath?: string;
  }>,
  baseUrl: string
): string {
  const feedUrl = `${baseUrl}/feed/${subscription.podcastId}.xml`;
  const podcastUrl = `${baseUrl}/podcast/${subscription.podcastId}`;
  const lastBuildDate = new Date().toUTCString();

  const readyEpisodes = episodes.filter(ep => ep.processingStatus === 'ready');

  const items = readyEpisodes
    .map((ep, index) => {
      const audioUrl = `${baseUrl}/api/audio/${encodeURIComponent(ep.id)}`;
      const pubDate = ep.pubDate ? new Date(ep.pubDate).toUTCString() : new Date().toUTCString();
      const duration = ep.duration ? formatTime(ep.duration) : '';

      // Get actual file size for enclosure
      let fileSize = 0;
      if (ep.processedPath && existsSync(ep.processedPath)) {
        try {
          fileSize = statSync(ep.processedPath).size;
        } catch {
          // Ignore errors, use 0
        }
      }

      // Extract episode number from title (e.g., "Ep. 1 - Title" or "Episode 42")
      const epMatch = ep.title.match(/(?:Ep\.?|Episode)\s*(\d+)/i);
      const episodeNum = epMatch ? parseInt(epMatch[1], 10) : readyEpisodes.length - index;

      return `
    <item>
      <title><![CDATA[${escapeXml(ep.title)}]]></title>
      <description><![CDATA[${escapeXml(ep.description || '')}]]></description>
      <enclosure url="${audioUrl}" type="audio/mpeg" length="${fileSize}"/>
      <guid isPermaLink="false">${escapeXml(ep.id)}</guid>
      <pubDate>${pubDate}</pubDate>
      ${duration ? `<itunes:duration>${duration}</itunes:duration>` : ''}
      <itunes:episode>${episodeNum}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
    </item>`;
    })
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title><![CDATA[${escapeXml(subscription.title)} (Ad-Free)]]></title>
    <link>${podcastUrl}</link>
    <description><![CDATA[${escapeXml(subscription.description || subscription.title)}]]></description>
    <language>en-us</language>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
    <atom:link href="${feedUrl}" rel="self" type="application/rss+xml"/>
    <itunes:author>${escapeXml(subscription.artist)}</itunes:author>
    <itunes:image href="${subscription.artworkUrl}"/>
    <itunes:type>episodic</itunes:type>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="Comedy"/>
    ${items}
  </channel>
</rss>`;
}

