/**
 * Processing queue API
 * GET    /api/queue - Get queue status
 * POST   /api/queue - Add episode to queue
 * DELETE /api/queue - Reset processing episodes and fix dates
 */
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getQueueStatus, addToQueue, addAllEpisodesToQueue } from '$lib/db/queue';
import { resetProcessingEpisodes, convertDatesToISO } from '$lib/db/episodes';
import { clearActiveJobs } from '$lib/worker/processor';
import { success, badRequest } from '$lib/services/api';
import {
  validateString,
  validateInteger,
  validateBoolean,
  isValidationError
} from '$lib/utils/validation';

export const GET: RequestHandler = async () => {
  const status = getQueueStatus();
  return success(status);
};

export const POST: RequestHandler = async ({ request }) => {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    throw error(400, 'Invalid JSON body');
  }

  if (typeof body !== 'object' || body === null) {
    throw error(400, 'Request body must be an object');
  }

  const requestBody = body as Record<string, unknown>;

  try {
    // Validate inputs
    const episodeId = validateString(requestBody.episodeId, 'episodeId', { maxLength: 500 });
    const podcastId = validateString(requestBody.podcastId, 'podcastId', { maxLength: 500 });
    const priority = validateInteger(requestBody.priority, 'priority', { min: -100, max: 100 }) ?? 0;
    const retry = validateBoolean(requestBody.retry, 'retry') ?? false;

    if (podcastId) {
      const queued = addAllEpisodesToQueue(podcastId, priority);
      return success({ queued, podcastId });
    }

    if (episodeId) {
      addToQueue(episodeId, priority, retry);
      return success({ queued: 1, episodeId, retry });
    }

    return badRequest('episodeId or podcastId required');
  } catch (e) {
    if (isValidationError(e)) {
      throw error(400, e.message);
    }
    throw e;
  }
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
