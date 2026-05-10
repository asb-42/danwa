<script>
  /**
   * Render Job Status — shows job progress and download buttons.
   *
   * @type {{ tracker: object }}
   */
  let { tracker } = $props();

  const statusColors = {
    queued: 'text-gray-500',
    running: 'text-blue-500',
    completed: 'text-green-500',
    failed: 'text-red-500',
  };

  const statusIcons = {
    queued: '⏳',
    running: '🔄',
    completed: '✅',
    failed: '❌',
  };
</script>

<div class="render-job-status p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
  <div class="flex items-center gap-2 mb-2">
    {#if tracker.loading}
      <span class="animate-spin">🔄</span>
      <span class="text-sm text-gray-500">Loading…</span>
    {:else}
      <span>{statusIcons[tracker.status] || '❓'}</span>
      <span class="text-sm font-medium {statusColors[tracker.status] || 'text-gray-500'}">
        {tracker.status}
      </span>
    {/if}
  </div>

  {#if tracker.error}
    <div class="mt-2 p-2 bg-red-50 dark:bg-red-900/20 rounded text-sm text-red-700 dark:text-red-300">
      {tracker.error}
    </div>
  {/if}

  {#if tracker.status === 'completed' && tracker.outputFiles.length > 0}
    <div class="mt-3 space-y-2">
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">Download:</p>
      {#each tracker.outputFiles as file, i}
        <a
          href="/api/v1/render-jobs/{tracker.jobId}/download?file_index={i}"
          download
          class="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 transition-colors"
        >
          📥 {file.split('/').pop()}
        </a>
      {/each}
    </div>
  {/if}
</div>
