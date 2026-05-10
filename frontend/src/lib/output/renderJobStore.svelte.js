/**
 * Render Job Tracker — Svelte 5 runes-based polling store.
 *
 * Tracks active render jobs by polling the status endpoint
 * every 2 seconds until the job reaches a terminal state
 * (completed or failed).
 */

import { getRenderJobStatus } from './composerApi.js';

/**
 * Create a reactive render job tracker.
 *
 * Usage:
 *   const tracker = createRenderJobTracker('job-123');
 *   // tracker.status, tracker.outputFiles, tracker.error, tracker.loading
 *   // are reactive Svelte 5 runes
 *
 * @param {string} jobId
 * @returns {{ status: string, outputFiles: string[], error: string|null, loading: boolean, stop: () => void }}
 */
export function createRenderJobTracker(jobId) {
  let status = $state('queued');
  let outputFiles = $state([]);
  let error = $state(null);
  let loading = $state(true);
  let intervalId = null;

  const terminalStatuses = new Set(['completed', 'failed']);

  async function poll() {
    try {
      const data = await getRenderJobStatus(jobId);
      status = data.status;
      outputFiles = data.output_files || [];
      error = data.error_message || null;
      loading = false;

      if (terminalStatuses.has(data.status)) {
        stop();
      }
    } catch (err) {
      error = err.message;
      loading = false;
      stop();
    }
  }

  function stop() {
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  // Initial poll
  poll();

  // Start polling every 2 seconds
  intervalId = setInterval(poll, 2000);

  return {
    jobId,
    get status() { return status; },
    get outputFiles() { return outputFiles; },
    get error() { return error; },
    get loading() { return loading; },
    stop,
  };
}
