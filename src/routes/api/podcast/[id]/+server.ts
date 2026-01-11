import type { RequestHandler } from './$types';
import type { Podcast } from '$lib/types';
import { fetchEpisodes } from '$lib/services/rss';
import { success, notFound, serverError } from '$lib/services/api';

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
      return notFound('Podcast not found');
    }

    const lookupData = await lookupResponse.json();

    if (!lookupData.results || lookupData.results.length === 0) {
      return notFound('Podcast not found');
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

    // Fetch and parse RSS feed for episodes using shared service
    const episodes = await fetchEpisodes(result.feedUrl, podcast);

    return success({ podcast, episodes });
  } catch (error) {
    console.error('Error fetching podcast:', error);
    return serverError('Failed to fetch podcast');
  }
};
