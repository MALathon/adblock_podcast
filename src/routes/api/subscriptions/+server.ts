/**
 * Subscriptions API
 * GET  /api/subscriptions - List all subscriptions
 * POST /api/subscriptions - Subscribe to a podcast
 */
import type { RequestHandler } from './$types';
import { getAllSubscriptions, subscribe, isSubscribed } from '$lib/db/subscriptions';
import { upsertEpisodes } from '$lib/db/episodes';
import { fetchEpisodes } from '$lib/services/rss';
import { success, created, badRequest, conflict } from '$lib/services/api';
import { validateString, validateUrl, isValidationError } from '$lib/utils/validation';
import type { Podcast } from '$lib/types';

export const GET: RequestHandler = async () => {
  const subscriptions = getAllSubscriptions();
  return success(subscriptions);
};

export const POST: RequestHandler = async ({ request }) => {
  try {
    const body = await request.json();

    // Validate inputs
    const id = validateString(body.id, 'id', { required: true });
    const feedUrl = validateUrl(body.feedUrl, 'feedUrl', { required: true });
    const title = validateString(body.title, 'title', { required: true });
    const artist = validateString(body.artist, 'artist');
    const artworkUrl = validateUrl(body.artworkUrl, 'artworkUrl');
    const description = validateString(body.description, 'description');
    const genre = validateString(body.genre, 'genre');

    const podcast: Podcast = {
      id,
      feedUrl,
      title,
      artist,
      artworkUrl,
      description,
      genre
    };

    if (isSubscribed(id)) {
      return conflict('Already subscribed');
    }

    // Subscribe to podcast
    const subscription = subscribe(podcast);

    // Fetch and store episodes (but don't auto-queue - let user select)
    try {
      const episodes = await fetchEpisodes(feedUrl, podcast);
      if (episodes.length > 0) {
        upsertEpisodes(episodes);
        console.log(`[Subscription] Stored ${episodes.length} episodes`);
      }
    } catch (error) {
      console.error('[Subscription] Failed to fetch episodes:', error);
    }

    return created(subscription);
  } catch (error) {
    if (isValidationError(error)) {
      return badRequest(error.message);
    }
    throw error;
  }
};
