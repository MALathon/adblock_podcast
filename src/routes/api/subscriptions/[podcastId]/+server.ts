/**
 * Single subscription API
 * GET    /api/subscriptions/[podcastId] - Get subscription details
 * DELETE /api/subscriptions/[podcastId] - Unsubscribe
 */
import type { RequestHandler } from './$types';
import { getSubscription, unsubscribe } from '$lib/db/subscriptions';
import { getEpisodesForPodcast } from '$lib/db/episodes';
import { success, notFound } from '$lib/services/api';

export const GET: RequestHandler = async ({ params }) => {
  const { podcastId } = params;
  const subscription = getSubscription(podcastId);

  if (!subscription) {
    return notFound('Subscription not found');
  }

  const episodes = getEpisodesForPodcast(podcastId);

  return success({ subscription, episodes });
};

export const DELETE: RequestHandler = async ({ params }) => {
  const { podcastId } = params;
  const deleted = unsubscribe(podcastId);

  if (!deleted) {
    return notFound('Subscription not found');
  }

  return success({ success: true });
};
