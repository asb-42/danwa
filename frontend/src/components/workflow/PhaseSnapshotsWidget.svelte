<script>
  /**
   * PhaseSnapshotsWidget — compact side-rail summary of a workflow's
   * phase-snapshot history.
   *
   * Used by `InputComposerView` (right rail next to the live execution
   * display) and the `MvpDebateView` activity sidebar (G2).  Shows the
   * *most-recent* snapshot plus the total count, with a "View all
   * phases →" button that opens the full `PhasesTab` in a modal.
   *
   * Backed by the shared `phaseSnapshotsStore`, so concurrent mounts
   * of the same session reuse a single fetch.
   *
   * Props:
   *   - sessionId  (required)  string|null
   *   - expanded   (optional)  boolean — render the full PhasesTab
   *                             inline instead of a button (used in
   *                             contexts where there is enough room
   *                             and the modal is undesirable)
   *
   * @see plans/phase5-workflow-observability-ux.md  (P5.4)
   */
  import { phaseSnapshots } from '../../lib/stores/phaseSnapshotsStore.svelte.js';
  import PhasesTab from './PhasesTab.svelte';

  /** @type {{ sessionId: string|null|undefined, expanded?: boolean }} */
  let { sessionId = null, expanded = false } = $props();

  // ─── Reactive view of the store ───────────────────────────────────
  let entry = $state(phaseSnapshots.entry(sessionId));
  $effect(() => {
    if (!sessionId) {
      entry = phaseSnapshots.entry(null);
      return;
    }
    entry = phaseSnapshots.entry(sessionId);
    const unsub = phaseSnapshots.subscribe((changed) => {
      if (changed === sessionId || changed === '*') {
        entry = phaseSnapshots.entry(sessionId);
      }
    });
    return unsub;
  });

  // Kick off the load (no-op if already in-flight / loaded).
  $effect(() => {
    if (sessionId) {
      phaseSnapshots.load(sessionId);
    }
  });

  // ─── Modal state ──────────────────────────────────────────────────
  let modalOpen = $state(false);

  // ─── Bridge to feedback store (A5) ────────────────────────────────
  // Emit one `phase_snapshot` log entry per session, the first time
  // the list loads successfully.  This is intentionally idempotent:
  // re-mounts / re-fetches don't spam the activity log.
  import { feedbackStore } from '../../lib/stores/feedback.svelte.js';

  /** @type {Set<string>} — sessions we've already bridged */
  const _bridged = new Set();
  $effect(() => {
    if (!sessionId) return;
    if (_bridged.has(sessionId)) return;
    if (entry.list.length === 0) return;
    _bridged.add(sessionId);
    try {
      feedbackStore.logActivity(
        'phase_snapshot',
        'workflow.phaseSnapshots',
        `Loaded ${entry.list.length} phase snapshot${entry.list.length === 1 ? '' : 's'} for session ${sessionId}`,
        { sessionId, count: entry.list.length },
        'info',
      );
    } catch {
      /* feedback store is best-effort */
    }
  });

  // ─── Formatters ───────────────────────────────────────────────────
  const latest = $derived(entry.list[entry.list.length - 1] || null);

  function formatTimestamp(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString(undefined, {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch {
      return iso;
    }
  }
</script>

<div class="phase-snapshots-widget" data-testid="phase-snapshots-widget">
  <header class="psw-header">
    <span class="psw-title">Phases</span>
    <span class="psw-count" aria-label="Snapshot count">
      {entry.list.length}
    </span>
  </header>

  {#if !sessionId}
    <p class="psw-empty" data-testid="psw-empty">No active session.</p>
  {:else if entry.loading && entry.list.length === 0}
    <p class="psw-empty" aria-busy="true">Loading…</p>
  {:else if entry.list.length === 0}
    <p class="psw-empty">No phase snapshots yet.</p>
  {:else}
    <div class="psw-latest" data-testid="psw-latest">
      <span class="psw-latest-label">Latest</span>
      <span class="psw-latest-node" title={latest.node_id}>
        {latest.node_id}
      </span>
      <span class="psw-latest-time">
        {formatTimestamp(latest.created_at)}
      </span>
    </div>

    {#if expanded}
      <div class="psw-expanded">
        <PhasesTab {sessionId} />
      </div>
    {:else}
      <button
        type="button"
        class="psw-view-all"
        data-testid="psw-view-all"
        aria-haspopup="dialog"
        onclick={() => (modalOpen = true)}
      >
        View all phases →
      </button>
    {/if}
  {/if}
</div>

{#if modalOpen && sessionId}
  <div
    class="psw-modal-backdrop"
    role="presentation"
    onclick={() => (modalOpen = false)}
  >
    <div
      class="psw-modal"
      role="dialog"
      aria-modal="true"
      aria-label="All phase snapshots"
      data-testid="psw-modal"
      onclick={(e) => e.stopPropagation()}
    >
      <div class="psw-modal-header">
        <h3 class="psw-modal-title">Phase snapshots</h3>
        <button
          type="button"
          class="psw-modal-close"
          aria-label="Close"
          onclick={() => (modalOpen = false)}
        >×</button>
      </div>
      <div class="psw-modal-body">
        <PhasesTab {sessionId} />
      </div>
    </div>
  </div>
{/if}

<style>
  .phase-snapshots-widget {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 10px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    font-size: 13px;
  }
  :global(.dark) .phase-snapshots-widget {
    background: #111827;
    border-color: #374151;
  }
  .psw-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .psw-title {
    font-weight: 600;
    color: #111827;
  }
  :global(.dark) .psw-title { color: #f3f4f6; }
  .psw-count {
    background: #e0e7ff;
    color: #3730a3;
    border-radius: 9999px;
    padding: 0 8px;
    font-size: 11px;
    min-width: 18px;
    text-align: center;
  }
  :global(.dark) .psw-count {
    background: #312e81;
    color: #c7d2fe;
  }
  .psw-empty {
    margin: 0;
    color: #6b7280;
    font-style: italic;
  }
  .psw-latest {
    display: flex;
    align-items: baseline;
    gap: 6px;
    flex-wrap: wrap;
  }
  .psw-latest-label {
    color: #6b7280;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .psw-latest-node {
    font-family: ui-monospace, SFMono-Regular, monospace;
    color: #111827;
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  :global(.dark) .psw-latest-node { color: #f3f4f6; }
  .psw-latest-time {
    color: #9ca3af;
    font-size: 11px;
  }
  .psw-view-all {
    background: none;
    border: none;
    color: #2563eb;
    cursor: pointer;
    font: inherit;
    text-align: left;
    padding: 4px 0;
  }
  .psw-view-all:hover { text-decoration: underline; }
  .psw-view-all:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
  }
  :global(.dark) .psw-view-all { color: #60a5fa; }
  .psw-expanded {
    margin-top: 4px;
  }
  .psw-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .psw-modal {
    background: #ffffff;
    color: #111827;
    border-radius: 8px;
    width: min(720px, 92vw);
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  }
  :global(.dark) .psw-modal {
    background: #0b1220;
    color: #f3f4f6;
  }
  .psw-modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-bottom: 1px solid #e5e7eb;
  }
  :global(.dark) .psw-modal-header { border-bottom-color: #374151; }
  .psw-modal-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }
  .psw-modal-close {
    background: none;
    border: none;
    font-size: 20px;
    line-height: 1;
    color: #6b7280;
    cursor: pointer;
    padding: 0 4px;
  }
  .psw-modal-close:hover { color: #111827; }
  :global(.dark) .psw-modal-close:hover { color: #f3f4f6; }
  .psw-modal-body {
    padding: 12px 14px;
    overflow: auto;
  }
</style>
