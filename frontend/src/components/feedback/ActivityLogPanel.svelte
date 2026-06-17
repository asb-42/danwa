<!-- DEBUG 2026-06-17: ActivityLogPanel — file is wrapped in {#if false} and not rendered. -->
{#if false}
<!--
  DEACTIVATED 2026-06-15: this component is no longer rendered in
  App.svelte. The activity-log strip at the bottom of the viewport
  was removed because it surfaced only low-value phantom events
  (e.g. 'Workspace view mounted'). feedbackStore.logActivity() is
  now a no-op (see feedback.svelte.js). This file is preserved on
  disk per user request, wrapped in {#if false} so Svelte parses
  it but no markup is rendered. Revive by removing the outer
  {#if false}/{#if false} guards once a more useful display
  destination is available (e.g. Header LLM monitor or ErrorPanel).
-->
<script>
  /**
   * ActivityLogPanel — Collapsible, timestamped activity log.
   *
   * Displays step-by-step workflow execution details sourced from
   * {@link feedbackStore.activityLog}. Fixed to the bottom of the
   * viewport so it never overlaps main content.
   *
   * **Keyboard shortcut:** `Ctrl+Shift+L` toggles the panel open/closed
   * (handled by the parent App component).
   *
   * **Features:**
   * - Filter entries by type (`llm`, `workflow`, `node`, `system`, `error`)
   *   via toggle buttons in the toolbar.
   * - Auto-scroll to newest entries (configurable via checkbox).
   * - Export full log + errors as JSON to clipboard (falls back to
   *   a new window if clipboard API is unavailable).
   * - Clear all entries.
   * - Shows entry count badge and active error count in the toggle bar.
   * - Displays truncated `requestId` when available for correlation.
   *
   * **No props** — all state is read reactively from `feedbackStore`.
   */
  import { feedbackStore } from '../../lib/stores/feedback.svelte.js';
  import { tStore } from '../../lib/i18n/index.js';

  let t = $derived($tStore);

  let isExpanded = $state(false);
  let filterType = $state('all');
  let autoScroll = $state(true);

  let logContainer = $state(null);

  const typeIcons = {
    llm: '🤖',
    workflow: '⚙️',
    node: '🔵',
    system: '🔧',
    error: '❌',
  };

  const levelColors = {
    info: 'text-zinc-400',
    warn: 'text-amber-400',
    error: 'text-red-400',
  };

  let filteredLog = $derived(
    filterType === 'all'
      ? feedbackStore.activityLog
      : feedbackStore.activityLog.filter(e => e.type === filterType)
  );

  // Auto-scroll when new entries arrive
  $effect(() => {
    const _len = filteredLog.length;
    if (autoScroll && logContainer && isExpanded) {
      requestAnimationFrame(() => {
        logContainer.scrollTop = logContainer.scrollHeight;
      });
    }
  });

  function formatTime(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  async function handleExport() {
    const json = feedbackStore.exportLog();
    try {
      await navigator.clipboard.writeText(json);
    } catch {
      // Fallback: open in new window
      const w = window.open('', '_blank');
      w.document.write(`<pre>${json}</pre>`);
    }
  }

  function handleClear() {
    feedbackStore.activityLog = [];
  }

  // Get unique types from log for filter buttons
  let availableTypes = $derived(
    [...new Set(feedbackStore.activityLog.map(e => e.type))]
  );
</script>

<div class="fixed bottom-0 left-0 right-0 z-40">
  <!-- Toggle bar -->
  <button
    class="w-full flex items-center justify-between px-4 py-1.5 bg-zinc-900/90 border-t border-zinc-700
           text-xs text-zinc-400 hover:text-zinc-300 transition-colors backdrop-blur-sm"
    onclick={() => isExpanded = !isExpanded}
    aria-expanded={isExpanded}
    aria-label="Toggle activity log"
  >
    <div class="flex items-center gap-2">
      <span class="text-sm">{isExpanded ? '▼' : '▲'}</span>
      <span class="font-medium">Activity Log</span>
      {#if feedbackStore.activityLog.length > 0}
        <span class="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-mono">
          {feedbackStore.activityLog.length}
        </span>
      {/if}
      {#if feedbackStore.activeErrors.length > 0}
        <span class="px-1.5 py-0.5 rounded bg-red-900/50 text-[10px] font-mono text-red-400">
          {feedbackStore.activeErrors.length} error{feedbackStore.activeErrors.length > 1 ? 's' : ''}
        </span>
      {/if}
    </div>
    {#if feedbackStore.requestId}
      <span class="text-[10px] font-mono text-zinc-600">
        req:{feedbackStore.requestId.slice(0, 8)}
      </span>
    {/if}
  </button>

  <!-- Expanded panel -->
  {#if isExpanded}
    <div class="bg-zinc-900/95 border-t border-zinc-700 backdrop-blur-sm" style="max-height: 35vh;">
      <!-- Toolbar -->
      <div class="flex items-center gap-2 px-4 py-2 border-b border-zinc-800">
        <!-- Filter buttons -->
        <div class="flex items-center gap-1">
          <button
            class="px-2 py-0.5 rounded text-[11px] {filterType === 'all' ? 'bg-zinc-700 text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'}"
            onclick={() => filterType = 'all'}
          >All</button>
          {#each availableTypes as type}
            <button
              class="px-2 py-0.5 rounded text-[11px] {filterType === type ? 'bg-zinc-700 text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'}"
              onclick={() => filterType = type}
            >{typeIcons[type] || '•'} {type}</button>
          {/each}
        </div>

        <div class="flex-1"></div>

        <!-- Auto-scroll toggle -->
        <label class="flex items-center gap-1 text-[11px] text-zinc-500 cursor-pointer">
          <input type="checkbox" bind:checked={autoScroll} class="w-3 h-3" />
          Auto-scroll
        </label>

        <!-- Export -->
        <button
          class="px-2 py-0.5 rounded text-[11px] text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
          onclick={handleExport}
          title="Export log to clipboard"
        >📋 Export</button>

        <!-- Clear -->
        <button
          class="px-2 py-0.5 rounded text-[11px] text-zinc-500 hover:text-red-400 hover:bg-zinc-800"
          onclick={handleClear}
          title="Clear activity log"
        >🗑 Clear</button>
      </div>

      <!-- Log entries -->
      <div
        bind:this={logContainer}
        class="overflow-y-auto font-mono text-[11px]"
        style="max-height: calc(35vh - 40px);"
      >
        {#if filteredLog.length === 0}
          <div class="px-4 py-6 text-center text-zinc-600">
            No activity yet
          </div>
        {:else}
          {#each filteredLog as entry (entry.id)}
            <div class="flex items-start gap-2 px-4 py-1 border-b border-zinc-800/50 hover:bg-zinc-800/30 {levelColors[entry.level] || 'text-zinc-400'}">
              <span class="flex-shrink-0 w-16 text-zinc-600">{formatTime(entry.timestamp)}</span>
              <span class="flex-shrink-0">{typeIcons[entry.type] || '•'}</span>
              <span class="flex-shrink-0 w-20 truncate text-zinc-500">{entry.source}</span>
              <span class="flex-1 break-all">{entry.message}</span>
            </div>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</div>
{/if}
