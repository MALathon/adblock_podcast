/**
 * Background Worker for Episode Processing
 *
 * Polls the queue and sends episodes to the FastAPI backend for ad removal.
 * Supports parallel processing of multiple episodes simultaneously.
 */

import { getNextBatchFromQueue, removeFromQueue, getQueueStatus } from '$lib/db/queue';
import { setProcessingStatus, getEpisode } from '$lib/db/episodes';
import { getSubscription } from '$lib/db/subscriptions';
import { existsSync, mkdirSync } from 'fs';
import { writeFile } from 'fs/promises';
import { join } from 'path';
import { BACKEND_URL, PROCESSED_DIR, WORKER_CONFIG } from '$lib/utils/config';

const { pollInterval: POLL_INTERVAL, maxConcurrent: MAX_CONCURRENT, statusCheckInterval } =
  WORKER_CONFIG;

let isRunning = false;
let activeJobs = new Map<string, string>(); // episodeId -> jobId

/**
 * Clear all active job tracking (for reset)
 */
export function clearActiveJobs(): void {
  activeJobs.clear();
  console.log('[Worker] Cleared active jobs tracking');
}

/**
 * Ensure processed directory exists
 */
function ensureProcessedDir(): void {
  if (!existsSync(PROCESSED_DIR)) {
    mkdirSync(PROCESSED_DIR, { recursive: true });
  }
}

/**
 * Process a single episode (runs in parallel with others)
 */
async function processEpisode(episodeId: string): Promise<boolean> {
  const episode = getEpisode(episodeId);
  if (!episode) {
    console.error(`[Worker] Episode not found: ${episodeId}`);
    return false;
  }

  const subscription = getSubscription(episode.podcastId);
  if (!subscription) {
    console.error(`[Worker] Subscription not found for episode: ${episodeId}`);
    return false;
  }

  console.log(`[Worker] Starting: ${episode.title}`);

  try {
    // Update status to processing
    setProcessingStatus(episodeId, 'processing');

    // Send to backend for processing
    const response = await fetch(`${BACKEND_URL}/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        episode_id: episodeId,
        audio_url: episode.audioUrl,
        title: episode.title,
        podcast_title: subscription.title
      })
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const result = await response.json();
    const jobId = result.job_id;
    activeJobs.set(episodeId, jobId);

    // Poll for completion
    let attempts = 0;
    const maxAttempts = 180; // 15 minutes max (5s * 180)

    while (attempts < maxAttempts) {
      await new Promise((resolve) => setTimeout(resolve, statusCheckInterval));
      attempts++;

      try {
        const statusResponse = await fetch(`${BACKEND_URL}/status/${jobId}`);
        if (!statusResponse.ok) continue;

        const status = await statusResponse.json();

        if (status.status === 'complete') {
          // Download processed audio from backend
          const audioResponse = await fetch(`${BACKEND_URL}/audio/${jobId}`);
          if (!audioResponse.ok) {
            throw new Error('Failed to download processed audio');
          }

          // Save to local processed directory
          ensureProcessedDir();
          const processedPath = join(PROCESSED_DIR, `${episodeId}.mp3`);
          const audioBuffer = await audioResponse.arrayBuffer();
          await writeFile(processedPath, Buffer.from(audioBuffer));

          // Update database
          setProcessingStatus(episodeId, 'ready', {
            processedPath,
            processedDuration: status.duration || null
          });

          console.log(`[Worker] Completed: ${episode.title}`);
          activeJobs.delete(episodeId);
          return true;
        } else if (status.status === 'error') {
          throw new Error(status.error || 'Processing failed');
        }

        // Still processing, continue polling
        if (attempts % 6 === 0) { // Log every 30 seconds
          console.log(`[Worker] ${episode.title}: ${status.status} (${status.progress}%)`);
        }
      } catch (pollError) {
        console.error(`[Worker] Poll error for ${episodeId}:`, pollError);
      }
    }

    throw new Error('Processing timed out');

  } catch (error) {
    console.error(`[Worker] Error processing ${episodeId}:`, error);
    setProcessingStatus(episodeId, 'error', {
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    activeJobs.delete(episodeId);
    return false;
  }
}

/**
 * Main worker loop - processes multiple episodes in parallel
 */
async function workerLoop(): Promise<void> {
  // Calculate how many new jobs we can start
  const currentActive = activeJobs.size;
  const slotsAvailable = MAX_CONCURRENT - currentActive;

  if (slotsAvailable <= 0) {
    console.log(`[Worker] All ${MAX_CONCURRENT} slots active, waiting...`);
    return;
  }

  // Get batch of episodes to process
  const queueItems = getNextBatchFromQueue(slotsAvailable);

  if (queueItems.length === 0) {
    if (currentActive === 0) {
      console.log('[Worker] Queue empty, waiting...');
    }
    return;
  }

  console.log(`[Worker] Starting ${queueItems.length} new job(s) (${currentActive} active)`);

  // Start processing each episode in parallel (don't await)
  for (const item of queueItems) {
    // Skip if already processing
    if (activeJobs.has(item.episodeId)) continue;

    // Mark as active immediately to prevent double-processing
    activeJobs.set(item.episodeId, 'starting');

    // Process in background
    processEpisode(item.episodeId).then(success => {
      if (success) {
        removeFromQueue(item.episodeId);
      }
    }).catch(err => {
      console.error(`[Worker] Unexpected error for ${item.episodeId}:`, err);
      activeJobs.delete(item.episodeId);
    });
  }
}

/**
 * Start the background worker
 */
export function startWorker(): void {
  if (isRunning) {
    console.log('[Worker] Already running');
    return;
  }

  console.log('[Worker] Starting parallel background processor');
  console.log(`[Worker] Backend URL: ${BACKEND_URL}`);
  console.log(`[Worker] Max concurrent: ${MAX_CONCURRENT}`);
  console.log(`[Worker] Poll interval: ${POLL_INTERVAL}ms`);

  isRunning = true;
  ensureProcessedDir();

  // Initial queue check
  const status = getQueueStatus();
  console.log(`[Worker] Queue status: ${status.total} items`);

  // Start polling loop
  const poll = async () => {
    if (!isRunning) return;

    try {
      await workerLoop();
    } catch (error) {
      console.error('[Worker] Loop error:', error);
    }

    if (isRunning) {
      setTimeout(poll, POLL_INTERVAL);
    }
  };

  // Start after initial delay
  setTimeout(poll, 3000);
}

/**
 * Stop the background worker
 */
export function stopWorker(): void {
  console.log('[Worker] Stopping background processor');
  isRunning = false;
}

/**
 * Get worker status
 */
export function getWorkerStatus(): {
  running: boolean;
  activeJobs: number;
  maxConcurrent: number;
  queueStatus: { total: number; processing: number };
} {
  return {
    running: isRunning,
    activeJobs: activeJobs.size,
    maxConcurrent: MAX_CONCURRENT,
    queueStatus: getQueueStatus()
  };
}
