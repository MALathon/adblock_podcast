/**
 * Server Hooks
 *
 * Initializes the background worker on server startup.
 */

import { startWorker } from '$lib/worker/processor';

// Start background worker when server initializes
let workerStarted = false;

if (!workerStarted) {
  console.log('[Hooks] Initializing server...');
  startWorker();
  workerStarted = true;
}

export const handle = async ({ event, resolve }) => {
  return resolve(event);
};
