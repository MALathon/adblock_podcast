/**
 * Processing queue API
 * GET    /api/queue - Get queue status
 * POST   /api/queue - Add episode to queue
 * DELETE /api/queue - Reset processing episodes and fix dates
 */
import type { RequestHandler } from './$types';
import { getQueueStatus, addToQueue, addAllEpisodesToQueue } from '$lib/db/queue';
import { resetProcessingEpisodes, convertDatesToISO } from '$lib/db/episodes';
import { clearActiveJobs } from '$lib/worker/processor';
import { success, badRequest } from '$lib/services/api';

export const GET: RequestHandler = async () => {
  const status = getQueueStatus();
  return success(status);
};

export const POST: RequestHandler = async ({ request }) => {
  const body = await request.json();
  const { episodeId, podcastId, priority = 0, retry = false } = body;

  if (podcastId) {
    const queued = addAllEpisodesToQueue(podcastId, priority);
    return success({ queued, podcastId });
  }

  if (episodeId) {
    addToQueue(episodeId, priority, retry);
    return success({ queued: 1, episodeId, retry });
  }

  return badRequest('episodeId or podcastId required');
};

export const DELETE: RequestHandler = async () => {
  clearActiveJobs();
  const resetCount = resetProcessingEpisodes();
  const convertedCount = convertDatesToISO();

  console.log(`[Queue] Reset ${resetCount} processing episodes, converted ${convertedCount} dates to ISO`);

  return success({
    reset: resetCount,
    datesConverted: convertedCount,
    message: 'Processing episodes reset to queued, dates converted to ISO format'
  });
};
