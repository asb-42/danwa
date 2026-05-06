<script>
  /**
   * InteractionTimeline — Displays the history of HITL interactions
   * (injects, queries, responses) in a chronological timeline.
   */

  import { hitlInteractions, hitlStatus } from '../../lib/stores/hitl.svelte.js';

  let { debateId = '' } = $props();

  let interactions = $derived($hitlInteractions);
  let status = $derived($hitlStatus);
  let isExpanded = $state(false);
  let filterType = $state('all');

  const typeConfig = {
    inject: { icon: '💉', label: 'Inject', color: '#89b4fa' },
    query: { icon: '❓', label: 'Query', color: '#f9e2af' },
    response: { icon: '💬', label: 'Response', color: '#a6e3a1' },
  };

  let filteredInteractions = $derived(
    filterType === 'all'
      ? interactions
      : interactions.filter((i) => i.type === filterType)
  );

  let totalCount = $derived(interactions.length);
  let typeCounts = $derived({
    inject: interactions.filter((i) => i.type === 'inject').length,
    query: interactions.filter((i) => i.type === 'query').length,
    response: interactions.filter((i) => i.type === 'response').length,
  });

  function formatTime(timestamp) {
    if (!timestamp) return '';
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return timestamp;
    }
  }

  function truncate(text, maxLen = 150) {
    if (!text || text.length <= maxLen) return text;
    return text.slice(0, maxLen) + '...';
  }

  function toggleExpanded() {
    isExpanded = !isExpanded;
  }
</script>

{#if status.hitl_enabled && totalCount > 0}
  <div class="interaction-timeline" class:expanded={isExpanded}>
    <button class="timeline-header" onclick={toggleExpanded} aria-expanded={isExpanded}>
      <span class="header-icon">📋</span>
      <span class="header-title">Interactions</span>
      <span class="header-count">{totalCount}</span>
      <span class="header-chevron" class:rotated={isExpanded}>▼</span>
    </button>

    {#if isExpanded}
      <div class="timeline-body">
        <!-- Filter tabs -->
        <div class="filter-tabs">
          <button
            class="filter-tab"
            class:active={filterType === 'all'}
            onclick={() => { filterType = 'all'; }}
          >
            All ({totalCount})
          </button>
          {#each Object.entries(typeConfig) as [type, config]}
            {#if typeCounts[type] > 0}
              <button
                class="filter-tab"
                class:active={filterType === type}
                onclick={() => { filterType = type; }}
              >
                {config.icon} {config.label} ({typeCounts[type]})
              </button>
            {/if}
          {/each}
        </div>

        <!-- Timeline entries -->
        <div class="timeline-entries">
          {#if filteredInteractions.length === 0}
            <div class="empty-state">No interactions to display</div>
          {:else}
            {#each filteredInteractions as interaction (interaction.interaction_id)}
              {@const config = typeConfig[interaction.type] || typeConfig.inject}
              <div class="timeline-entry" style="--accent: {config.color}">
                <div class="entry-marker">
                  <span class="marker-icon">{config.icon}</span>
                </div>
                <div class="entry-content">
                  <div class="entry-header">
                    <span class="entry-type" style="color: {config.color}">{config.label}</span>
                    <span class="entry-direction">
                      {interaction.source} → {interaction.target}
                    </span>
                    <span class="entry-time">{formatTime(interaction.timestamp)}</span>
                  </div>
                  <div class="entry-text">{truncate(interaction.content)}</div>
                  <div class="entry-meta">
                    <span class="meta-item">Round {interaction.round}</span>
                    <span class="meta-item status-{interaction.status}">{interaction.status}</span>
                    {#if interaction.metadata?.priority && interaction.metadata.priority !== 'normal'}
                      <span class="meta-item priority-{interaction.metadata.priority}">
                        {interaction.metadata.priority}
                      </span>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .interaction-timeline {
    background: var(--color-surface, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 8px;
    overflow: hidden;
  }

  .timeline-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 10px 14px;
    background: none;
    border: none;
    color: var(--color-text, #cdd6f4);
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    transition: background 0.15s;
  }

  .timeline-header:hover {
    background: var(--color-surface-hover, #252536);
  }

  .header-icon {
    font-size: 1.1rem;
  }

  .header-title {
    flex: 1;
    text-align: left;
  }

  .header-count {
    background: var(--color-primary, #89b4fa);
    color: var(--color-bg, #1e1e2e);
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .header-chevron {
    font-size: 0.75rem;
    transition: transform 0.2s;
  }

  .header-chevron.rotated {
    transform: rotate(180deg);
  }

  .timeline-body {
    padding: 0 14px 14px;
  }

  .filter-tabs {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .filter-tab {
    padding: 4px 10px;
    background: var(--color-input-bg, #181825);
    border: 1px solid var(--color-border, #313244);
    border-radius: 4px;
    color: var(--color-text-muted, #a6adc8);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .filter-tab:hover {
    border-color: var(--color-primary, #89b4fa);
  }

  .filter-tab.active {
    background: rgba(137, 180, 250, 0.15);
    border-color: var(--color-primary, #89b4fa);
    color: var(--color-primary, #89b4fa);
  }

  .timeline-entries {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 400px;
    overflow-y: auto;
  }

  .empty-state {
    padding: 20px;
    text-align: center;
    color: var(--color-text-muted, #a6adc8);
    font-size: 0.85rem;
  }

  .timeline-entry {
    display: flex;
    gap: 10px;
    padding: 10px;
    background: var(--color-input-bg, #181825);
    border-radius: 6px;
    border-left: 3px solid var(--accent, #89b4fa);
  }

  .entry-marker {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(137, 180, 250, 0.1);
    border-radius: 50%;
  }

  .marker-icon {
    font-size: 0.9rem;
  }

  .entry-content {
    flex: 1;
    min-width: 0;
  }

  .entry-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }

  .entry-type {
    font-weight: 600;
    font-size: 0.8rem;
  }

  .entry-direction {
    font-size: 0.75rem;
    color: var(--color-text-muted, #a6adc8);
  }

  .entry-time {
    font-size: 0.7rem;
    color: var(--color-text-muted, #a6adc8);
    margin-left: auto;
  }

  .entry-text {
    font-size: 0.85rem;
    color: var(--color-text, #cdd6f4);
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .entry-meta {
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }

  .meta-item {
    font-size: 0.7rem;
    color: var(--color-text-muted, #a6adc8);
    padding: 1px 6px;
    background: rgba(166, 173, 200, 0.1);
    border-radius: 3px;
  }

  .meta-item.status-consumed {
    color: #a6e3a1;
    background: rgba(166, 227, 161, 0.1);
  }

  .meta-item.status-delivered {
    color: #89b4fa;
    background: rgba(137, 180, 250, 0.1);
  }

  .meta-item.status-pending {
    color: #f9e2af;
    background: rgba(249, 226, 175, 0.1);
  }

  .meta-item.priority-high {
    color: #fab387;
    background: rgba(250, 179, 135, 0.1);
  }

  .meta-item.priority-urgent {
    color: #f38ba8;
    background: rgba(243, 139, 168, 0.1);
  }
</style>
