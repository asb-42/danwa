<script>
  /**
   * PhasesTab — Timeline view of a workflow session's phase snapshots.
   *
   * Each row shows: node id, round, decision marker, and a button
   * to expand the full captured state JSON.  Designed to slot into
   * the existing ExecutionPanel as a third tab.
   *
   * @see plans/phase5-workflow-observability-ux.md  (P5.3, A3)
   *
   * Props:
   *   - sessionId  (required)  string
   *
   * Uses the shared `phaseSnapshotsStore` so multiple components
   * mounting the same session share a single in-flight fetch.
   */
  import { onMount } from 'svelte';
  import { phaseSnapshots } from '../../lib/stores/phaseSnapshotsStore.svelte.js';

  /** @type {{ sessionId: string|null|undefined }} */
  let { sessionId = null } = $props();

  // ─── Reactive view of the store ───────────────────────────────────
  // The store is a plain JS singleton (see phaseSnapshotsStore.svelte.js);
  // we subscribe to changes and re-assign local mirrors so Svelte's
  // reactivity can pick up the new object references.
  let entry = $state(phaseSnapshots.entry(sessionId));
  let _tick = $state(0);
  $effect(() => {
    if (!sessionId) {
      entry = { list: [], detail: {}, loading: false, error: null, loadedAt: 0 };
      return;
    }
    // Initial sync + subscribe to future changes.
    entry = phaseSnapshots.entry(sessionId);
    const unsub = phaseSnapshots.subscribe((changed) => {
      if (changed === sessionId || changed === '*') {
        entry = phaseSnapshots.entry(sessionId);
        _tick++;
      }
    });
    return unsub;
  });

  $effect(() => {
    if (sessionId) {
      phaseSnapshots.load(sessionId);
    }
  });

  // ─── Expand / collapse state for individual rows ──────────────────
  let expandedNodeId = $state(null);
  let expandedDetail = $state(null);
  let expandingError = $state(null);

  async function toggleExpand(nodeId) {
    if (expandedNodeId === nodeId) {
      expandedNodeId = null;
      expandedDetail = null;
      expandingError = null;
      return;
    }
    expandedNodeId = nodeId;
    expandedDetail = null;
    expandingError = null;
    try {
      const detail = await phaseSnapshots.loadDetail(sessionId, nodeId);
      if (detail === undefined) {
        expandingError = 'Phase list not loaded yet';
        return;
      }
      if (detail === null) {
        expandingError = 'Snapshot not found on backend';
        return;
      }
      expandedDetail = detail;
      // Refresh entry mirror so the newly-cached detail is in sync
      entry = phaseSnapshots.entry(sessionId);
    } catch (err) {
      expandingError = err?.message || 'Failed to load state';
    }
  }

  // ─── Formatters ───────────────────────────────────────────────────
  function formatBytes(n) {
    if (typeof n !== 'number' || n <= 0) return '0 B';
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(2)} MB`;
  }

  function formatTimestamp(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  }

  function formatJson(obj) {
    try {
      return JSON.stringify(obj, null, 2);
    } catch {
      return '[unserialisable state]';
    }
  }
</script>

<div class="phases-tab" data-testid="phases-tab">
  {#if !sessionId}
    <p class="phases-empty">No active session.</p>
  {:else if entry.loading && entry.list.length === 0}
    <p class="phases-empty" aria-busy="true">Loading phases…</p>
  {:else if entry.error && entry.list.length === 0}
    <p class="phases-error" role="alert">Failed to load phases: {entry.error.message}</p>
  {:else if entry.list.length === 0}
    <p class="phases-empty">No phase snapshots yet — they appear as gates and nodes complete.</p>
  {:else}
    <ol class="phases-list" aria-label="Phase snapshots in execution order">
      {#each entry.list as snap (snap.node_id)}
        <li class="phase-row" data-testid="phase-row" data-node-id={snap.node_id}>
          <button
            class="phase-header"
            type="button"
            aria-expanded={expandedNodeId === snap.node_id}
            aria-controls={`phase-detail-${snap.node_id}`}
            onclick={() => toggleExpand(snap.node_id)}
          >
            <span class="phase-bullet" aria-hidden="true">●</span>
            <span class="phase-node-id">{snap.node_id}</span>
            {#if snap.round !== null && snap.round !== undefined}
              <span class="phase-round">R{snap.round}</span>
            {/if}
            <span class="phase-size" title="Captured state size">
              {formatBytes(snap.state_size)}
            </span>
            <span class="phase-time">{formatTimestamp(snap.created_at)}</span>
          </button>

          {#if expandedNodeId === snap.node_id}
            <div
              id={`phase-detail-${snap.node_id}`}
              class="phase-detail"
              data-testid="phase-detail"
            >
              {#if expandedDetail}
                <pre class="phase-state">{formatJson(expandedDetail.state)}</pre>
              {:else if expandingError}
                <p class="phase-error" role="alert">{expandingError}</p>
              {:else}
                <p class="phase-loading">Loading state…</p>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</div>

<style>
  .phases-tab {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 13px;
  }
  .phases-empty,
  .phases-error,
  .phase-loading,
  .phase-error {
    margin: 0;
    color: #6b7280;
    font-style: italic;
    padding: 4px 0;
  }
  .phases-error,
  .phase-error {
    color: #b91c1c;
    font-style: normal;
  }
  .phases-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .phase-row {
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #f9fafb;
    overflow: hidden;
  }
  :global(.dark) .phase-row {
    background: #111827;
    border-color: #374151;
  }
  .phase-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 10px;
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }
  .phase-header:hover { background: #f3f4f6; }
  :global(.dark) .phase-header:hover { background: #1f2937; }
  .phase-header:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: -2px;
  }
  .phase-bullet {
    color: #2563eb;
    font-size: 10px;
    flex: 0 0 auto;
  }
  .phase-node-id {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 12px;
    color: #111827;
    flex: 1 1 auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.dark) .phase-node-id { color: #f3f4f6; }
  .phase-round {
    background: #e0e7ff;
    color: #3730a3;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 9999px;
    flex: 0 0 auto;
  }
  :global(.dark) .phase-round {
    background: #312e81;
    color: #c7d2fe;
  }
  .phase-size {
    color: #6b7280;
    font-size: 11px;
    flex: 0 0 auto;
  }
  .phase-time {
    color: #9ca3af;
    font-size: 11px;
    flex: 0 0 auto;
  }
  .phase-detail {
    border-top: 1px solid #e5e7eb;
    padding: 8px 10px;
    background: #ffffff;
    max-height: 300px;
    overflow: auto;
  }
  :global(.dark) .phase-detail {
    background: #0b1220;
    border-top-color: #374151;
  }
  .phase-state {
    margin: 0;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 11px;
    line-height: 1.4;
    white-space: pre-wrap;
    word-break: break-word;
  }
</style>
