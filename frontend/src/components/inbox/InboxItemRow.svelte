<!--
  InboxItemRow — single row in the Case-Space Inbox list.

  Extracted from InboxView.svelte (commit f6a6a81) so the same row
  can be reused on the Dashboard's recent-activity card, the
  WorkspaceView's recent-events card, and the AuditView in a
  later phase.  Items are read-only; the parent owns selection
  state and passes a boolean + change handler.

  @see plans/2026-06-14_case-space-workspace.md (Phase 2.8)
-->
<script>
  import { tStore } from '../lib/i18n/index.js';

  let { item, selected = false, onCheck = () => {} } = $props();

  let t = $derived($tStore);

  function handleCheck() {
    onCheck(item.id);
  }
</script>

<li class="item" data-kind={item.kind}>
  <label class="item-check">
    <input
      type="checkbox"
      checked={selected}
      onchange={handleCheck}
      aria-label={t?.caseSpace?.inbox?.selectItem ?? 'Select item'}
    />
  </label>
  <div class="item-body">
    <div class="item-title">
      <span class="kind-badge" data-kind={item.kind}>{item.kind}</span>
      <strong>{item.title}</strong>
    </div>
    <p class="item-message">{item.message}</p>
    <p class="item-meta">
      <span>Case: {item.case_id}</span>
      {#if item.tags?.length}
        <span>·</span>
        <span>Tags: {item.tags.join(', ')}</span>
      {/if}
      {#if item.age_hours != null}
        <span>·</span>
        <span>{item.age_hours} h old</span>
      {/if}
    </p>
  </div>
</li>

<style>
  .item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    margin-bottom: 0.5rem;
    background: var(--color-bg-elevated, #fff);
  }
  .item-check { padding-top: 0.25rem; }
  .item-body { flex: 1; }
  .item-title { display: flex; align-items: center; gap: 0.5rem; }
  .item-title strong { font-size: 1rem; }
  .item-message {
    margin: 0.25rem 0 0;
    color: var(--color-text, #222);
  }
  .item-meta {
    margin: 0.25rem 0 0;
    color: var(--color-text-muted, #666);
    font-size: 0.85rem;
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .kind-badge {
    font-size: 0.7rem;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    background: var(--color-bg-muted, #eee);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .kind-badge[data-kind="recently_completed"] { background: #dbeafe; color: #1e40af; }
  .kind-badge[data-kind="untagged"]           { background: #fef3c7; color: #92400e; }
  .kind-badge[data-kind="stale_running"]      { background: #fee2e2; color: #991b1b; }
</style>
