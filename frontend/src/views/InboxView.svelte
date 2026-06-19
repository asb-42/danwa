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
  import { feedbackStore } from '../lib/stores/feedback.svelte.js';
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
    moveItem,
    tagItem,
    deleteItem,
    reset,
  } from '../lib/stores/inboxStore.svelte.js';
  import { searchCases } from '../lib/api/workspace.js';
  import InboxItemRow from '../components/inbox/InboxItemRow.svelte';
  import TagPicker from '../components/TagPicker.svelte';
  import ConfirmDialog from '../components/ConfirmDialog.svelte';

  let { navigate = () => {}, initialTenantId = null } = $props();

  // Reactive read
  let t = $derived($tStore);
  let summary = $derived(inboxStore.summary);
  let loading = $derived(inboxStore.loading);
  let error = $derived(inboxStore.error);
  let filteredItems = $derived(inboxStore.filteredItems);
  let selectedIds = $derived(inboxStore.selectedIds);
  let activeTab = $derived(inboxStore.activeTab);
  let lastBulkResult = $derived(inboxStore.lastBulkResult);
  let inboxDisabled = $derived(inboxStore.inboxDisabled);

  // Local UI state
  let moveTargetInput = $state('');
  let moveTargetSearchResults = $state([]);
  let toastMessage = $state(null);

  // ─── Phase 2.8 single-item modal state ──────────────────────
  // The Tag and Move buttons open a modal scoped to the chosen
  // item.  Archive opens a ConfirmDialog.  The bulk-* paths stay
  // for multi-select use cases (currently exposed via the row
  // checkbox + the future "select all matching" actions).
  let moveModalItem = $state(null);     // { id, case_id, title } or null
  let tagModalItem = $state(null);
  let pendingTagIds = $state([]);         // TagPicker value
  let archiveConfirmItem = $state(null);
  let singleInFlight = $state(false);

  function openItem(item) {
    if (!item) return;
    if (typeof window === 'undefined') return;
    // Decide route based on whether the debate is a "real" MVP
    // debate or a case-scoped one.  WorkspaceView's own
    // 'mvp-debate' vs 'debate' route distinction is mirrored
    // here so Open behaves consistently.
    const route = item.case_id?.startsWith('mvp-') ? 'mvp-debate' : 'debate';
    window.location.hash = `#/${route}/${item.id}`;
  }
  function openMoveModal(item) {
    if (!item) return;
    moveModalItem = { id: item.id, case_id: item.case_id, title: item.title };
    moveTargetInput = '';
    moveTargetSearchResults = [];
  }
  function closeMoveModal() {
    moveModalItem = null;
    moveTargetInput = '';
    moveTargetSearchResults = [];
  }
  async function confirmMoveModal() {
    const target = (moveTargetInput || '').trim();
    if (!target || !moveModalItem) return;
    singleInFlight = true;
    try {
      const res = await moveItem(moveModalItem.id, target);
      // Issue (2026-06-18): the modal closed silently before --
      // the user had no way to know whether the move succeeded.
      // Use the same toast helper the bulk path uses, so single-
      // item and bulk flows look identical from the user's POV.
      if (res) showToast(formatResult('Move', res));
    } catch (err) {
      showToast(`Move failed: ${err?.message ?? err}`);
    } finally {
      singleInFlight = false;
      closeMoveModal();
    }
  }
  function openTagModal(item) {
    if (!item) return;
    tagModalItem = { id: item.id, case_id: item.case_id, title: item.title };
    pendingTagIds = Array.isArray(item.tags) ? [...item.tags] : [];
  }
  function closeTagModal() {
    tagModalItem = null;
    pendingTagIds = [];
  }
  async function confirmTagModal() {
    if (!tagModalItem) return;
    const existing = tagModalItem.id && inboxStore.summary?.items
      ? (inboxStore.summary.items.find((it) => it.id === tagModalItem.id)?.tags || [])
      : [];
    const newOnes = pendingTagIds.filter((t) => !existing.includes(t));
    if (newOnes.length === 0) {
      closeTagModal();
      showToast('No new tags to add (all already on the item).');
      return;
    }
    singleInFlight = true;
    try {
      const res = await tagItem(tagModalItem.id, newOnes);
      if (res) showToast(formatResult('Tag', res));
    } catch (err) {
      showToast(`Tag failed: ${err?.message ?? err}`);
    } finally {
      singleInFlight = false;
      closeTagModal();
    }
  }
  function openArchiveConfirm(item) {
    if (!item) return;
    archiveConfirmItem = { id: item.id, case_id: item.case_id, title: item.title };
  }
  function closeArchiveConfirm() {
    archiveConfirmItem = null;
  }
  async function confirmArchiveItem() {
    if (!archiveConfirmItem) return;
    singleInFlight = true;
    try {
      const res = await deleteItem(archiveConfirmItem.id);
      if (res) showToast(formatResult('Delete', res));
    } catch (err) {
      showToast(`Delete failed: ${err?.message ?? err}`);
    } finally {
      singleInFlight = false;
      closeArchiveConfirm();
    }
  }
  let toastTimer = null;

  onMount(() => {
    const tid = initialTenantId || $currentTenant?.id;
    if (tid) {
      load(tid);
    }
    // Phase 6.2 / C5 telemetry: log the Inbox-open event.
    // Distinct from graph_view so we can later split "entered
    // workspace" from "went to inbox" in the success metrics.
    feedbackStore.logActivity(
      'case-space',
      'inbox-view',
      'Inbox view mounted',
      { tenantId: tid || null }
    );
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


  // ─── Tag input ─────────────────────────────────────────────────
  let tagTimer = null;

  // ─── Archive ───────────────────────────────────────────────────

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
            <InboxItemRow
              {item}
              selected={selectedIds.has(item.id)}
              onCheck={onRowCheck}
              onOpen={openItem}
              onTag={openTagModal}
              onMove={openMoveModal}
              onArchive={openArchiveConfirm}
            />
          {/each}
        </ul>
      {/if}
    {/if}

    <!-- Phase 2.8 visual-revision: per-row action buttons now
         provide the move/tag/archive UX.  The sticky bottom bar
         was a duplicate of the row buttons in a different style
         and the user found it confusingly unreadable (light
         text on white).  We keep the bulk-* state and APIs in
         the inboxStore for future "select all matching"
         actions, but the UI exposes only the row buttons.
         The selectedIds counter + clear survives in the row
         header so users can still deselect all. -->

    <!-- Toast -->
    {#if toastMessage}
      <div class="toast" role="status">
        {toastMessage}
      </div>
    {/if}

    <!-- Phase 2.8 single-item modals -->
    {#if moveModalItem}
      <div
        class="modal-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="inbox-move-title"
        data-testid="inbox-move-modal"
        onclick={(e) => e.stopPropagation()}
      >
        <div
          class="modal-card"
          onclick={(e) => e.stopPropagation()}
        >
          <h3 id="inbox-move-title" class="text-lg font-semibold mb-2">
            {t?.caseSpace?.inbox?.moveModalTitle ?? 'Move to case'}
          </h3>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
            {t?.caseSpace?.inbox?.moveModalBody ??
              `Move "${moveModalItem.title}" (current case: ${moveModalItem.case_id}) to:`}
          </p>
          <input
            type="text"
            class="modal-input w-full px-3 py-2 rounded border
                   border-gray-300 dark:border-gray-600
                   bg-white dark:bg-gray-700
                   text-gray-900 dark:text-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder={t?.caseSpace?.inbox?.moveModalPlaceholder ?? 'Target case id (typeahead)…'}
            value={moveTargetInput}
            oninput={onMoveTargetInput}
            list="inbox-move-suggestions"
            disabled={singleInFlight}
            data-testid="inbox-move-input"
          />
          <datalist id="inbox-move-suggestions">
            {#each moveTargetSearchResults as hit}
              <option value={hit.case_id}>{hit.title}</option>
            {/each}
          </datalist>
          <div class="modal-actions sticky bottom-0 -mx-5 -mb-5 mt-4 px-5 py-3 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2">
            <button
              type="button"
              class="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600
                     bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100
                     hover:bg-gray-100 dark:hover:bg-gray-600
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
              onclick={closeMoveModal}
              disabled={singleInFlight}
              data-testid="inbox-move-cancel"
            >
              {t?.common?.cancel ?? 'Cancel'}
            </button>
            <button
              type="button"
              class="px-3 py-1.5 rounded
                     bg-blue-600 text-white
                     hover:bg-blue-700
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     disabled:opacity-50"
              onclick={confirmMoveModal}
              disabled={singleInFlight || !moveTargetInput.trim()}
              data-testid="inbox-move-confirm"
            >
              {t?.caseSpace?.inbox?.move ?? 'Move'}
            </button>
          </div>
        </div>
      </div>
    {/if}

    {#if tagModalItem}
      <div
        class="modal-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="inbox-tag-title"
        data-testid="inbox-tag-modal"
        onclick={(e) => e.stopPropagation()}
      >
        <div
          class="modal-card"
          onclick={(e) => e.stopPropagation()}
        >
          <h3 id="inbox-tag-title" class="text-lg font-semibold mb-2">
            {t?.caseSpace?.inbox?.tagModalTitle ?? 'Add tags'}
          </h3>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
            {t?.caseSpace?.inbox?.tagModalBody ??
              `Add tags to "${tagModalItem.title}". Existing tags are preserved.`}
          </p>
          <TagPicker
            value={pendingTagIds}
            onchange={(v) => (pendingTagIds = v)}
          />
          <div class="mt-4 flex justify-end gap-2">
            <button
              type="button"
              class="px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600
                     bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100
                     hover:bg-gray-100 dark:hover:bg-gray-600
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
              onclick={closeTagModal}
              disabled={singleInFlight}
              data-testid="inbox-tag-cancel"
            >
              {t?.common?.cancel ?? 'Cancel'}
            </button>
            <button
              type="button"
              class="px-3 py-1.5 rounded
                     bg-blue-600 text-white
                     hover:bg-blue-700
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     disabled:opacity-50"
              onclick={confirmTagModal}
              disabled={singleInFlight}
              data-testid="inbox-tag-confirm"
            >
              {t?.caseSpace?.inbox?.tag ?? 'Tag'}
            </button>
          </div>
        </div>
      </div>
    {/if}

    {#if archiveConfirmItem}
      <ConfirmDialog
        open={Boolean(archiveConfirmItem)}
        title={t?.caseSpace?.inbox?.deleteTitle ?? 'Delete this item?'}
        message={
          (t?.caseSpace?.inbox?.deleteMessage ??
            'Remove this item from the Inbox. This is a real delete; you will not be able to recover the item later.')
        }
        detail={archiveConfirmItem.title}
        confirmLabel={t?.caseSpace?.inbox?.deleteConfirm ?? 'Delete'}
        cancelLabel={t?.common?.cancel ?? 'Cancel'}
        variant="warning"
        onConfirm={confirmArchiveItem}
        onCancel={closeArchiveConfirm}
      />
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
    color: #14532d;
  }
  .all-clear .icon {
    display: block;
    font-size: 2rem;
    color: #16a34a;
  }
  /* Dark-theme variant: the empty Inbox state was rendered as a
     bright green card on dark backgrounds because the background/
     border/text colours were hardcoded.  Override only inside the
     `.dark` scope (set by the app's theme switcher on <html> or
     <body>) so the rest of the app stays unaffected. */
  :global(.dark) .all-clear {
    background: #052e16;
    border-color: #14532d;
    color: #bbf7d0;
  }
  :global(.dark) .all-clear .icon {
    color: #4ade80;
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
    color: var(--color-text, #111);
  }
  .banner strong, .banner p { color: inherit; }
  .banner-warning { background: #fff3cd; border: 1px solid #ffeaa7; color: #5c4400; }
  .banner-error   { background: #fde8e8; border: 1px solid #f5c6cb; color: #7a1212; }
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
    /* z-index above .modal-overlay (1001) so toasts stay visible
       while a modal is open -- issue 2026-06-18. */
    z-index: 1100;
  }

  /* .modal-overlay / .modal-card are used by the Tag and Move modals
     below.  The class names mirror the convention used by
     TemplateInstantiateModal.svelte and AgentQueryModal.svelte, but
     those CSS rules are scoped to their own components and therefore
     do not apply here.  Define them via :global() so the Tag / Move
     modals are actually visible.

     Issue (2026-06-18): user reported that the Tag and Move buttons
     had 'no function' -- root cause was that the modal divs were
     rendered with no styling (transparent, not centred), so the
     user saw no UI change after clicking the buttons.  Open and
     Delete worked because Open navigates away and Delete uses
     ConfirmDialog (its own scoped styles).  */
  :global(.modal-overlay) {
    position: fixed;
    inset: 0;
    z-index: 1001;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
    padding: 20px;
  }
  :global(.modal-card) {
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    width: 100%;
    max-width: 560px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    padding: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  }
  /* The TagPicker's root div is the only direct child besides the
     sticky action bar; make it the flex-grow scrolling area so
     the action bar (sticky bottom-0) is always visible regardless
     of how many tags the picker contains.  Issue (2026-06-19):
     user reported the Cancel/'Add tags' buttons were not visible
     because the dropdown pushed them below the card's visible area. */
  :global(.modal-card > .tag-picker) {
    flex: 1 1 auto;
    min-height: 0;
    overflow: visible;
  }
  :global(.dark .modal-card) {
    background: #1e1e2e;
    color: #e2e8f0;
    border-color: #313244;
  }
</style>
