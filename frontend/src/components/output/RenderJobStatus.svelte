<script>
  /**
   * Render Job Status — shows job progress, elapsed time, and download buttons.
   *
   * @type {{ tracker: object }}
   */
  import { onDestroy } from 'svelte';

  let { tracker } = $props();

  const statusColors = {
    queued: 'text-gray-500',
    running: 'text-blue-500',
    completed: 'text-green-500',
    failed: 'text-red-500',
  };

  const statusLabels = {
    queued: 'In Warteschlange',
    running: 'Wird ausgeführt…',
    completed: 'Abgeschlossen',
    failed: 'Fehlgeschlagen',
  };

  const statusIcons = {
    queued: '⏳',
    running: '🔄',
    completed: '✅',
    failed: '❌',
  };

  // Elapsed time counter
  let elapsed = $state(0);
  let elapsedInterval = null;

  function startElapsedCounter() {
    elapsed = 0;
    elapsedInterval = setInterval(() => { elapsed += 1; }, 1000);
  }

  function stopElapsedCounter() {
    if (elapsedInterval) {
      clearInterval(elapsedInterval);
      elapsedInterval = null;
    }
  }

  // Start counter when tracker is running
  $effect(() => {
    if (tracker.status === 'running' || tracker.status === 'queued') {
      startElapsedCounter();
    } else {
      stopElapsedCounter();
    }
  });

  onDestroy(() => {
    stopElapsedCounter();
  });

  function formatElapsed(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  }
</script>

<div class="render-job-status p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
  <!-- Status row -->
  <div class="flex items-center gap-3 mb-3">
    {#if tracker.loading}
      <span class="animate-spin text-lg">🔄</span>
      <span class="text-sm text-gray-500">Status wird geladen…</span>
    {:else}
      <span class="text-lg">{statusIcons[tracker.status] || '❓'}</span>
      <span class="text-sm font-medium {statusColors[tracker.status] || 'text-gray-500'}">
        {statusLabels[tracker.status] || tracker.status}
      </span>
      {#if (tracker.status === 'running' || tracker.status === 'queued') && elapsed > 0}
        <span class="text-xs text-gray-400 ml-auto">{formatElapsed(elapsed)}</span>
      {/if}
    {/if}
  </div>

  <!-- Progress steps -->
  {#if tracker.status === 'running'}
    <div class="mb-3 space-y-1">
      <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span class="text-green-500">✓</span> Artefakt geladen
      </div>
      <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span class="animate-spin">⏳</span> Ausgabe wird generiert…
      </div>
    </div>
  {/if}

  <!-- Error -->
  {#if tracker.error}
    <div class="mt-2 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
      <p class="text-sm font-medium text-red-700 dark:text-red-300 mb-1">Fehler:</p>
      <p class="text-xs text-red-600 dark:text-red-400 font-mono break-all">{tracker.error}</p>
    </div>
  {/if}

  <!-- Completed: download links -->
  {#if tracker.status === 'completed' && tracker.outputFiles.length > 0}
    <div class="mt-3 space-y-2">
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">Download:</p>
      {#each tracker.outputFiles as file, i}
        <a
          href="/api/v1/render-jobs/{tracker.jobId}/download?file_index={i}"
          download
          class="inline-flex items-center gap-2 px-4 py-2 rounded bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition-colors"
        >
          📥 {file.split('/').pop()}
        </a>
      {/each}
    </div>
  {/if}

  <!-- Queued info -->
  {#if tracker.status === 'queued'}
    <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
      Auf Verarbeitung warten…
    </p>
  {/if}
</div>
