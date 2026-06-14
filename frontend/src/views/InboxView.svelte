<!--
  Case-Space Inbox — second primary view of the new Case-Space UI.

  Surfaces the items returned by GET /api/v1/inbox and gives the user
  a tabbed UI with a bulk-action bar.  Implements Phase 2.7 of
  plans/2026-06-14_case-space-impl-todos.md.

  Tabs: All / Untagged / Recently Completed / Stale Running.
  Each tab filters the displayed list by item kind.  Selection is
  tab-scoped (switching tabs clears the selection).

  Bulk actions appear in a sticky bar at the bottom whenever one or
  more items are selected.  The bar offers Move-to-Case, Add-tag,
  and Archive.  Each action triggers a backend call and a re-fetch
  of the Inbox; the last result is shown in a toast.

  @see plans/2026-06-14_case-space-workspace.md (Phase 2)
-->
<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import {
    inboxStore,
    load,
    setActiveTab,
    toggleSelected,
    toggleSelectAll,
    clearSelection,
    moveSelectedTo,
    tagSelected,
    archiveSelected,
    reset,
  } from '../lib/stores/inboxStore.svelte.js';
  import { searchCases } from '../lib/api/workspace.js';

  let { navigate = () => {}, initialTenantId = null } = $props();

  // Reactive read
  let t = $derived($tStore);
  let summary = $derived(inboxStore.summary);
  let loading = $derived(inboxStore.loading);
  let error = $derived(inboxStore.error);
  let filteredItems = $derived(inboxStore.filteredItems);
  let selectedIds = $derived(inboxStore.selectedIds);
  let activeTab = $derived(inboxStore.activeTab);
  let bulkInFlight = $derived(inboxStore.bulkInFlight);
  let lastBulkResult = $derived(inboxStore.lastBulkResult);
  let inboxDisabled = $derived(inboxStore.inboxDisabled);

  // Local UI state
  let moveTargetInput = $state('');
  let moveTargetSearchResults = $state([]);
  let tagInput = $state('');
  let toastMessage = $state(null);
  let toastTimer = null;

  onMount(() => {
    const tid = initialTenantId || $currentTenant?.id;
    if (tid) {
      load(tid);
    }
    return () => {
      if (toastTimer) clearTimeout(toastTimer);
    };
  });

  // Reload when the tenant changes
  $effect(() => {
    const tid = $currentTenant?.id;
    if (tid) {
      load(tid);
    }
  });

  // ─── Tab helpers ────────────────────────────────────────────────
  const TABS = [
    { id: '', label: 'All' },
    { id: 'untagged', label: 'Untagged' },
    { id: 'recently_completed', label: 'Recently completed' },
    { id: 'stale_running', label: 'Stale running' },
  ];

  function selectTab(id) {
    setActiveTab(id);
  }

  // ─── Move-to-case search ────────────────────────────────────────
  let moveSearchTimer = null;
  async function onMoveTargetInput(e) {
    moveTargetInput = e.target.value;
    if (moveSearchTimer) clearTimeout(moveSearchTimer);
    const q = moveTargetInput.trim();
    if (!q) {
      moveTargetSearchResults = [];
      return;
    }
    moveSearchTimer = setTimeout(async () => {
      try {
        moveTargetSearchResults = await searchCases(q, 5);
      } catch {
        moveTargetSearchResults = [];
      }
    }, 200);
  }

  async function doMove() {
    const target = (moveTargetInput || '').trim();
    if (!target) return;
    const res = await moveSelectedTo(target);
    if (res) {
      showToast(formatResult('Moved', res));
      moveTargetInput = '';
      moveTargetSearchResults = [];
    }
  }

  // ─── Tag input ─────────────────────────────────────────────────
  let tagTimer = null;
  async function onTagInput(e) {
    tagInput = e.target.value;
    if (tagTimer) clearTimeout(tagTimer);
    tagTimer = setTimeout(async () => {
      const tags = (tagInput || '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      if (tags.length === 0) return;
      const res = await tagSelected(tags);
      if (res) {
        showToast(formatResult('Tagged', res));
        tagInput = '';
      }
    }, 800); // longer debounce: tag input is multi-tag
  }

  // ─── Archive ───────────────────────────────────────────────────
  async function doArchive() {
    const count = selectedIds.size;
    const res = await archiveSelected();
    if (res) {
      showToast(formatResult('Archived', res));
    }
  }

  // ─── Toast helper ──────────────────────────────────────────────
  function formatResult(action, res) {
    const ok = res.succeeded?.length ?? 0;
    const failed = res.failed?.length ?? 0;
    if (failed === 0) return `${action}: ${ok} item(s) ✓`;
    return `${action}: ${ok} ok, ${failed} failed`;
  }

  function showToast(msg) {
    toastMessage = msg;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastMessage = null;
    }, 4000);
  }

  // ─── Derived: visible ids for select-all toggle ───────────────
  let visibleIds = $derived(filteredItems.map((it) => it.id));
  let allSelected = $derived(
    visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id))
  );
  function onToggleSelectAll() {
    toggleSelectAll();
  }
  function onRowCheck(itemId) {
    toggleSelected(itemId);
  }
</script>

<section class="inbox-view" aria-label="Case-Space Inbox">
  <header class="inbox-header">
    <h1>{t?.caseSpace?.inbox?.title ?? 'Inbox'}</h1>
    <p class="subtitle">
      {t?.caseSpace?.inbox?.subtitle ??
        'Items that need your attention. Select multiple to act on them in bulk.'}
    </p>
  </header>

  {#if inboxDisabled}
    <div class="banner banner-warning" role="status">
      <strong>{t?.caseSpace?.inbox?.flagOffTitle ?? 'Inbox is not enabled'}</strong>
      <p>
        {t?.caseSpace?.inbox?.flagOffBody ??
          'Set DANWA_ENABLE_CASE_SPACE_INBOX=true on the backend to use the Inbox.'}
      </p>
      {#if navigate}
        <button class="btn" onclick={() => navigate('cases')}>
          {t?.caseSpace?.inbox?.goToLegacy ?? 'Open legacy Cases view'}
        </button>
      {/if}
    </div>
  {/if}

  {#if !inboxDisabled}
    <nav class="tabs" role="tablist" aria-label="Inbox filter">
      {#each TABS as tab}
        <button
          class="tab"
          class:active={activeTab === tab.id}
          role="tab"
          aria-selected={activeTab === tab.id}
          onclick={() => selectTab(tab.id)}
        >
          {tab.label}
          {#if tab.id && summary?.counts?.[tab.id]}
            <span class="badge">{summary.counts[tab.id]}</span>
          {:else if !tab.id && summary}
            <span class="badge">{summary.items.length}</span>
          {/if}
        </button>
      {/each}
    </nav>

    {#if loading}
      <p class="loading" role="status">
        {t?.caseSpace?.inbox?.loading ?? 'Loading inbox…'}
      </p>
    {:else if error}
      <div class="banner banner-error" role="alert">
        <strong>{t?.caseSpace?.inbox?.errorTitle ?? 'Could not load inbox'}</strong>
        <p>{String(error?.message ?? error)}</p>
        <button class="btn" onclick={() => load($currentTenant?.id)}>
          {t?.caseSpace?.inbox?.retry ?? 'Retry'}
        </button>
      </div>
    {:else if summary}
      {#if summary.is_all_clear}
        <div class="all-clear" role="status">
          <span class="icon" aria-hidden="true">✓</span>
          <strong>{t?.caseSpace?.inbox?.allClear ?? 'All clear.'}</strong>
          <p>
            {t?.caseSpace?.inbox?.allClearBody ??
              'No items need your attention right now.'}
          </p>
        </div>
      {:else}
        <div class="select-bar">
          <label>
            <input
              type="checkbox"
              checked={allSelected}
              onchange={onToggleSelectAll}
              aria-label="Select all visible items"
            />
            {t?.caseSpace?.inbox?.selectAll ?? 'Select all'}
          </label>
          <span class="count">
            {selectedIds.size} {t?.caseSpace?.inbox?.selected ?? 'selected'}
          </span>
          {#if selectedIds.size > 0}
            <button class="btn-link" onclick={() => clearSelection()}>
              {t?.caseSpace?.inbox?.clear ?? 'Clear'}
            </button>
          {/if}
        </div>

        <ul class="item-list">
          {#each filteredItems as item (item.id)}
            <li class="item" data-kind={item.kind}>
              <label class="item-check">
                <input
                  type="checkbox"
                  checked={selectedIds.has(item.id)}
                  onchange={() => onRowCheck(item.id)}
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
          {/each}
        </ul>
      {/if}
    {/if}

    <!-- Bulk action bar -->
    {#if selectedIds.size > 0}
      <div class="bulk-bar" role="region" aria-label="Bulk actions">
        <strong>
          {selectedIds.size}
          {t?.caseSpace?.inbox?.selectedItems ?? 'item(s) selected'}
        </strong>

        <div class="bulk-actions">
          <div class="action-group">
            <input
              type="text"
              class="action-input"
              placeholder={t?.caseSpace?.inbox?.movePlaceholder ?? 'Target case id (typeahead)…'}
              value={moveTargetInput}
              oninput={onMoveTargetInput}
              list="move-target-suggestions"
              disabled={bulkInFlight}
            />
            <datalist id="move-target-suggestions">
              {#each moveTargetSearchResults as hit}
                <option value={hit.case_id}>{hit.title}</option>
              {/each}
            </datalist>
            <button class="btn btn-primary" onclick={doMove} disabled={bulkInFlight || !moveTargetInput.trim()}>
              {t?.caseSpace?.inbox?.move ?? 'Move'}
            </button>
          </div>

          <div class="action-group">
            <input
              type="text"
              class="action-input"
              placeholder={t?.caseSpace?.inbox?.tagPlaceholder ?? 'Tags (comma-separated)…'}
              value={tagInput}
              oninput={onTagInput}
              disabled={bulkInFlight}
            />
          </div>

          <button class="btn btn-warning" onclick={doArchive} disabled={bulkInFlight}>
            {t?.caseSpace?.inbox?.archive ?? 'Archive'}
          </button>
        </div>
      </div>
    {/if}

    <!-- Toast -->
    {#if toastMessage}
      <div class="toast" role="status">
        {toastMessage}
      </div>
    {/if}
  {/if}
</section>

<style>
  .inbox-view {
    max-width: 1100px;
    margin: 0 auto;
    padding: 1.5rem;
  }
  .inbox-header h1 {
    margin: 0 0 0.25rem;
    font-size: 1.75rem;
  }
  .inbox-header .subtitle {
    margin: 0 0 1.5rem;
    color: var(--color-text-muted, #666);
  }
  .tabs {
    display: flex;
    gap: 0.25rem;
    border-bottom: 1px solid var(--color-border, #ddd);
    margin-bottom: 1rem;
  }
  .tab {
    background: transparent;
    border: none;
    padding: 0.6rem 1rem;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    color: var(--color-text-muted, #666);
  }
  .tab.active {
    border-bottom-color: var(--color-primary, #3b82f6);
    color: var(--color-text, #111);
  }
  .badge {
    display: inline-block;
    margin-left: 0.4rem;
    padding: 0.05rem 0.45rem;
    background: var(--color-bg-muted, #eee);
    border-radius: 999px;
    font-size: 0.75rem;
  }
  .all-clear {
    text-align: center;
    padding: 2rem;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
  }
  .all-clear .icon {
    display: block;
    font-size: 2rem;
    color: #16a34a;
  }
  .select-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.5rem;
    color: var(--color-text-muted, #666);
  }
  .item-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
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

  .bulk-bar {
    position: sticky;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-top: 1rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
  }
  .bulk-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; flex: 1; }
  .action-group { display: flex; gap: 0.25rem; align-items: center; }
  .action-input {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 4px;
    min-width: 220px;
  }
  .btn {
    padding: 0.4rem 0.85rem;
    border: 1px solid var(--color-border, #ddd);
    background: var(--color-bg-elevated, #fff);
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-primary { background: var(--color-primary, #3b82f6); color: white; border-color: transparent; }
  .btn-warning { background: #f59e0b; color: white; border-color: transparent; }
  .btn-link { background: transparent; border: none; color: var(--color-primary, #3b82f6); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .banner {
    padding: 1rem 1.25rem;
    border-radius: 6px;
    margin: 0 0 1rem;
  }
  .banner-warning { background: #fff3cd; border: 1px solid #ffeaa7; }
  .banner-error   { background: #fde8e8; border: 1px solid #f5c6cb; }
  .loading { color: var(--color-text-muted, #666); }
  .toast {
    position: fixed;
    bottom: 5.5rem;
    right: 1.5rem;
    background: #1f2937;
    color: white;
    padding: 0.6rem 1rem;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
</style>
