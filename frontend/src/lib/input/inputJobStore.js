/**
 * Input Job Tracker — Svelte 5 runes-based polling store.
 */

import { getInputJobStatus } from './inputApi.js';

export function createInputJobTracker(jobId) {
  let status = $state('queued');
  let processedInput = $state(null);
  let error = $state(null);
  let loading = $state(true);
  let intervalId = null;

  const terminalStatuses = new Set(['completed', 'failed']);

  async function poll() {
    try {
      const data = await getInputJobStatus(jobId);
      status = data.status;
      processedInput = data.processed_input;
      error = data.error_message || null;
      loading = false;
      if (terminalStatuses.has(data.status)) stop();
    } catch (err) {
      error = err.message;
      loading = false;
      stop();
    }
  }

  function stop() {
    if (intervalId !== null) { clearInterval(intervalId); intervalId = null; }
  }

  poll();
  intervalId = setInterval(poll, 2000);

  return {
    get status() { return status; },
    get processedInput() { return processedInput; },
    get error() { return error; },
    get loading() { return loading; },
    stop,
  };
}
