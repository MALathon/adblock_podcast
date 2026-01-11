/**
 * Processing queue API
 * GET    /api/queue - Get queue status
 * POST   /api/queue - Add episode to queue
 * DELETE /api/queue - Reset processing episodes and fix dates
 */
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getQueueStatus, addToQueue, addAllEpisodesToQueue } from '$lib/db/queue';
import { resetProcessingEpisodes, convertDatesToISO } from '$lib/db/episodes';
import { clearActiveJobs } from '$lib/worker/processor';

export const GET: RequestHandler = async () => {
  const status = getQueueStatus();
  return json(status);
};

export const POST: RequestHandler = async ({ request }) => {
  const body = await request.json();
  const { episodeId, podcastId, priority = 0, retry = false } = body;

  if (podcastId) {
    // Queue all episodes for a podcast
    const queued = addAllEpisodesToQueue(podcastId, priority);
    return json({ queued, podcastId });
  }

  if (episodeId) {
    // Queue single episode (with optional retry for failed episodes)
    addToQueue(episodeId, priority, retry);
    return json({ queued: 1, episodeId, retry });
  }

  return json({ error: 'episodeId or podcastId required' }, { status: 400 });
};

export const DELETE: RequestHandler = async () => {
  // Clear in-memory job tracking
  clearActiveJobs();

  // Reset all processing episodes back to queued
  const resetCount = resetProcessingEpisodes();

  // Convert RFC 2822 dates to ISO 8601 for proper sorting
  const convertedCount = convertDatesToISO();

  console.log(`[Queue] Reset ${resetCount} processing episodes, converted ${convertedCount} dates to ISO`);

  return json({
    reset: resetCount,
    datesConverted: convertedCount,
    message: 'Processing episodes reset to queued, dates converted to ISO format'
  });
};
