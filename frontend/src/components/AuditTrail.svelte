<script>
  // Placeholder — will render detailed audit trail in Sprint 4
  export let events = [];
</script>

<div class="space-y-2">
  {#if events.length === 0}
    <div class="flex items-center justify-center h-24 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400 text-sm">No audit events yet</p>
    </div>
  {:else}
    {#each events as event}
      <div class="flex items-start space-x-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
        <span class="text-xs text-gray-500 font-mono whitespace-nowrap">
          {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : '—'}
        </span>
        <span class="px-1.5 py-0.5 text-xs font-medium rounded bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          {event.agent || 'system'}
        </span>
        <span class="text-sm text-gray-700 dark:text-gray-300">{event.action || '—'}</span>
      </div>
    {/each}
  {/if}
</div>
