/**
 * Single subscription API
 * GET    /api/subscriptions/[podcastId] - Get subscription details
 * DELETE /api/subscriptions/[podcastId] - Unsubscribe
 */
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getSubscription, unsubscribe } from '$lib/db/subscriptions';
import { getEpisodesForPodcast } from '$lib/db/episodes';

export const GET: RequestHandler = async ({ params }) => {
  const { podcastId } = params;
  const subscription = getSubscription(podcastId);

  if (!subscription) {
    return json({ error: 'Not found' }, { status: 404 });
  }

  const episodes = getEpisodesForPodcast(podcastId);

  return json({
    subscription,
    episodes
  });
};

export const DELETE: RequestHandler = async ({ params }) => {
  const { podcastId } = params;
  const deleted = unsubscribe(podcastId);

  if (!deleted) {
    return json({ error: 'Not found' }, { status: 404 });
  }

  return json({ success: true });
};
