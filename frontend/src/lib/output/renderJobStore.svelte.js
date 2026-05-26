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
  let progressCurrent = $state(0);
  let progressTotal = $state(0);
  let intervalId = null;

  const terminalStatuses = new Set(['completed', 'failed']);

  async function poll() {
    try {
      const data = await getRenderJobStatus(jobId);
      status = data.status;
      outputFiles = data.output_files || [];
      error = data.error_message || null;
      progressCurrent = data.progress_current || 0;
      progressTotal = data.progress_total || 0;
      loading = false;

      // Persist terminal status to localStorage
      if (terminalStatuses.has(data.status)) {
        stop();
        try {
          const saved = localStorage.getItem('danwa.activeRenderJob');
          if (saved) {
            const jobData = JSON.parse(saved);
            if (jobData && jobData.job_id === jobId) {
              jobData._terminal = true;
              jobData._finalStatus = data.status;
              localStorage.setItem('danwa.activeRenderJob', JSON.stringify(jobData));
            }
          }
        } catch { /* ignore */ }
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
    get progressCurrent() { return progressCurrent; },
    get progressTotal() { return progressTotal; },
    stop,
  };
}
