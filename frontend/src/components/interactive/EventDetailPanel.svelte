<script>
  /**
   * EventDetailPanel — resizable side panel showing full event details.
   *
   * Displays complete content (no truncation), actor info, metadata,
   * and action buttons when a node is selected in the debate tree.
   */
  import { tStore } from '../../lib/i18n/index.js';
  import { eventStore, forkModalStore } from '../../lib/interactive/stores';

  let t = $derived($tStore);

  let { spaceId = null } = $props();

  let panelWidth = $state(400);
  let resizing = $state(false);
  let resizeStartX = $state(0);
  let resizeStartW = $state(0);

  let selectedEvent = $derived.by(() => {
    const state = $eventStore;
    if (!state.selectedEventId) return null;
    return state.events.get(state.selectedEventId) || null;
  });

  function handleResizeStart(e) {
    resizing = true;
    resizeStartX = e.clientX;
    resizeStartW = panelWidth;
    e.preventDefault();
  }

  function handleResizeMove(e) {
    if (!resizing) return;
    const dx = resizeStartX - e.clientX;
    panelWidth = Math.max(300, Math.min(800, resizeStartW + dx));
  }

  function handleResizeEnd() {
    resizing = false;
  }

  function closePanel() {
    eventStore.setSelectedEvent(null);
  }

  function handleFork() {
    if (selectedEvent) {
      forkModalStore.open(selectedEvent);
    }
  }

  function formatTime(ts) {
    if (!ts) return '';
    return new Date(ts).toLocaleString();
  }

  function formatTokens(n) {
    if (!n) return '—';
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
  }
</script>

<svelte:window onmousemove={handleResizeMove} onmouseup={handleResizeEnd} />

{#if selectedEvent}
  <div
    class="event-detail-panel"
    style="width: {panelWidth}px;"
  >
    <!-- Resize handle -->
    <div
      class="resize-handle"
      onmousedown={handleResizeStart}
    ></div>

    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
      <h3 class="text-sm font-semibold text-gray-800 dark:text-white">
        {t('eventPanel.title')}
      </h3>
      <button
        class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-lg leading-none"
        onclick={closePanel}
        title={t('eventPanel.close')}
      >
        ✕
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <!-- Actor info -->
      <div class="space-y-2">
        <div class="flex items-center gap-2">
          <span class="text-xl">
            {selectedEvent.actor_type === 'user' ? '👤' :
             selectedEvent.actor_type === 'agent' ? '🤖' :
             selectedEvent.actor_type === 'a2a' ? '🔗' : '⚙️'}
          </span>
          <div>
            <div class="text-sm font-semibold text-gray-800 dark:text-gray-100">
              {selectedEvent.actor_id}
            </div>
            {#if selectedEvent.role}
              <div class="text-xs text-gray-500 dark:text-gray-400">
                {selectedEvent.role}
              </div>
            {/if}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('eventPanel.type')}:</span>
            <span class="ml-1 font-medium text-gray-800 dark:text-gray-100">{selectedEvent.event_type}</span>
          </div>
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('eventPanel.time')}:</span>
            <span class="ml-1 font-medium text-gray-800 dark:text-gray-100">{formatTime(selectedEvent.created_at)}</span>
          </div>
          {#if selectedEvent.tokens_output}
            <div>
              <span class="text-gray-500 dark:text-gray-400">{t('eventPanel.tokens')}:</span>
              <span class="ml-1 font-medium text-gray-800 dark:text-gray-100">{formatTokens(selectedEvent.tokens_output)}</span>
            </div>
          {/if}
          {#if selectedEvent.metadata_json?.model}
            <div>
              <span class="text-gray-500 dark:text-gray-400">{t('eventPanel.model')}:</span>
              <span class="ml-1 font-medium text-gray-800 dark:text-gray-100 font-mono">{selectedEvent.metadata_json.model}</span>
            </div>
          {/if}
        </div>
      </div>

      <!-- Full content -->
      <div>
        <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
          {t('eventPanel.fullContent')}
        </div>
        <div class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words leading-relaxed">
          {typeof selectedEvent.content === 'string'
            ? selectedEvent.content
            : JSON.stringify(selectedEvent.content, null, 2)}
        </div>
      </div>

      <!-- Metadata (if present) -->
      {#if selectedEvent.metadata_json && Object.keys(selectedEvent.metadata_json).length > 0}
        <div>
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Metadata</div>
          <pre class="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto font-mono">{JSON.stringify(selectedEvent.metadata_json, null, 2)}</pre>
        </div>
      {/if}
    </div>

    <!-- Footer actions -->
    <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex gap-2">
      <button
        class="flex-1 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        onclick={handleFork}
      >
        + Fork
      </button>
      <button
        class="px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        onclick={closePanel}
      >
        {t('eventPanel.close')}
      </button>
    </div>
  </div>
{/if}

<style>
  .event-detail-panel {
    position: relative;
    display: flex;
    flex-direction: column;
    height: 100%;
    background: white;
    border-left: 1px solid #e5e7eb;
    box-shadow: -4px 0 12px rgba(0, 0, 0, 0.05);
  }

  :global(.dark) .event-detail-panel {
    background: #111827;
    border-left-color: #374151;
    box-shadow: -4px 0 12px rgba(0, 0, 0, 0.3);
  }

  .resize-handle {
    position: absolute;
    left: -4px;
    top: 0;
    bottom: 0;
    width: 8px;
    cursor: col-resize;
    z-index: 10;
  }

  .resize-handle:hover {
    background: rgba(59, 130, 246, 0.3);
  }
</style>
