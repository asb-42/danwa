<script>
  /**
   * TimelinePanel — Shows round history as a horizontal timeline.
   * Allows switching between current view and historical round views.
   */

  import { roundSnapshots, viewMode, graphNodes, graphEdges } from '../../../lib/workflow/store.js';
  import { i18n } from '../../../lib/i18n/index.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let snapshots = $derived($roundSnapshots);
  let currentView = $derived($viewMode);
  let selectedRound = $state(null);

  function selectRound(snapshot) {
    selectedRound = snapshot.round;
    // Load snapshot into graph for viewing
    graphNodes.set(new Map(snapshot.nodes.map(n => [n.id, n])));
    graphEdges.set(new Map(snapshot.edges.map(e => [e.id, e])));
  }

  function returnToCurrent() {
    selectedRound = null;
    viewMode.set('current');
  }
</script>

<div class="timeline-panel">
  <div class="panel-header">
    <h3 class="panel-title">📅 {t('workflow.timeline')}</h3>
    {#if selectedRound != null}
      <button class="back-btn" onclick={returnToCurrent}>
        {t('workflow.backToLive')}
      </button>
    {/if}
  </div>

  <div class="timeline-body">
    {#if snapshots.length === 0}
      <p class="empty-text">{t('workflow.noRounds')}</p>
    {:else}
      <div class="timeline-track">
        {#each snapshots as snapshot, i}
          <button
            class="timeline-item"
            class:selected={selectedRound === snapshot.round}
            onclick={() => selectRound(snapshot)}
          >
            <div class="timeline-dot"></div>
            <span class="timeline-label">R{snapshot.round}</span>
            {#if i < snapshots.length - 1}
              <div class="timeline-line"></div>
            {/if}
          </button>
        {/each}
      </div>

      {#if selectedRound != null}
        {@const snap = snapshots.find(s => s.round === selectedRound)}
        {#if snap}
          <div class="round-detail">
            <p class="round-title">{snap.title}</p>
            <p class="round-meta">
              {t('workflow.nodeEdgeCount', { nodes: snap.nodes.length, edges: snap.edges.length })}
            </p>
            {#if snap.executionPath?.length > 0}
              <div class="execution-path">
                {#each snap.executionPath as step}
                  <span class="path-step">{step}</span>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      {/if}
    {/if}
  </div>
</div>

<style>
  .timeline-panel {
    width: 240px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    margin-left: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  :global(.dark) .timeline-panel {
    background: #1f2937;
    border-color: #374151;
  }
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
  }
  :global(.dark) .panel-header { border-color: #374151; }
  .panel-title {
    font-size: 14px;
    font-weight: 600;
    color: #111827;
    margin: 0;
  }
  :global(.dark) .panel-title { color: #f3f4f6; }
  .back-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: #3b82f6;
    font-size: 12px;
    font-weight: 500;
  }
  .back-btn:hover { text-decoration: underline; }
  .timeline-body {
    padding: 12px 16px;
    overflow-y: auto;
    max-height: 400px;
  }
  .empty-text {
    color: #9ca3af;
    font-size: 12px;
    text-align: center;
    margin: 0;
  }
  .timeline-track {
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .timeline-item {
    display: flex;
    align-items: center;
    gap: 8px;
    background: none;
    border: none;
    cursor: pointer;
    padding: 8px 4px;
    position: relative;
  }
  .timeline-item:hover { background: #f3f4f6; border-radius: 6px; }
  :global(.dark) .timeline-item:hover { background: #374151; }
  .timeline-item.selected { background: #eff6ff; border-radius: 6px; }
  :global(.dark) .timeline-item.selected { background: #1e3a5f; }
  .timeline-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #d1d5db;
    flex-shrink: 0;
  }
  .timeline-item.selected .timeline-dot { background: #3b82f6; }
  .timeline-label {
    font-size: 12px;
    font-weight: 600;
    color: #374151;
  }
  :global(.dark) .timeline-label { color: #e5e7eb; }
  .timeline-line {
    position: absolute;
    left: 8px;
    top: 100%;
    width: 2px;
    height: 8px;
    background: #d1d5db;
  }
  .round-detail {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #e5e7eb;
  }
  :global(.dark) .round-detail { border-color: #374151; }
  .round-title {
    font-size: 13px;
    font-weight: 600;
    color: #111827;
    margin: 0 0 4px 0;
  }
  :global(.dark) .round-title { color: #f3f4f6; }
  .round-meta {
    font-size: 11px;
    color: #9ca3af;
    margin: 0 0 8px 0;
  }
  .execution-path {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .path-step {
    font-size: 10px;
    color: #6b7280;
    font-family: monospace;
  }
</style>
