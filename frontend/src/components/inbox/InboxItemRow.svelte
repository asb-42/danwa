<!--
  InboxItemRow — single row in the Case-Space Inbox list.

  Extracted from InboxView.svelte (commit f6a6a81) so the same row
  can be reused on the Dashboard's recent-activity card, the
  WorkspaceView's recent-events card, and the AuditView in a
  later phase.  Items are read-only; the parent owns selection
  state and passes a boolean + change handler.

  Converted to the project's standard Tailwind dark: pattern in
  commit a0ad6495-style: every text/background class is paired
  with its dark: variant so the row honours whichever theme
  the rest of the app is running.  Hard-coded hex tokens are
  reserved for the small colour-coded kind badges only.

  @see plans/2026-06-14_case-space-workspace.md (Phase 2.8)
-->
<script>
  import { tStore } from '../../lib/i18n/index.js';

  // Phase 2.8 visual revision (2026-06-15): rows now expose inline
  // action buttons.  The optional checkbox + onCheck props stay for
  // bulk-select use cases (e.g. "Archive 5 selected items"), but
  // the row does not require them.  Every row is interactive
  // out of the box.
  let {
    item,
    selected = false,
    onCheck = () => {},
    onOpen = () => {},
    onTag = () => {},
    onMove = () => {},
    onArchive = () => {},
  } = $props();

  let t = $derived($tStore);

  // Kinds can be comma-joined when the same debate matches
  // multiple inbox kinds in the "All" tab.  Render each as
  // its own badge so the colour coding stays clear.
  let kindBadges = $derived(
    (item?.kind || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  );

  function handleCheck() {
    onCheck(item.id);
  }
  function handleOpen()  { onOpen(item); }
  function handleTag()   { onTag(item); }
  function handleMove()  { onMove(item); }
  function handleArchive() { onArchive(item); }
</script>

<li class="flex items-start gap-3 px-4 py-3 mb-2 rounded-md border
           border-gray-200 dark:border-gray-700
           bg-white dark:bg-gray-800">
  {#if onCheck !== undefined}
    <label class="pt-1">
      <input
        type="checkbox"
        checked={selected}
        onchange={handleCheck}
        aria-label={t?.caseSpace?.inbox?.selectItem ?? 'Select item'}
        class="rounded border-gray-300 dark:border-gray-600
               text-blue-600 focus:ring-blue-500"
      />
    </label>
  {/if}
  <div class="flex-1 min-w-0">
    <div class="flex items-center gap-2 flex-wrap">
      {#each kindBadges as k (k)}
        <span
          class="text-xs font-semibold px-1.5 py-0.5 rounded
                 uppercase tracking-wider kind-badge"
          data-kind={k}
        >
          {k.replace(/_/g, ' ')}
        </span>
      {/each}
      <strong class="text-base text-gray-900 dark:text-white truncate">
        {item.title}
      </strong>
    </div>
    {#if item.message}
      <p class="mt-1 text-sm text-gray-700 dark:text-gray-300">
        {item.message}
      </p>
    {/if}
    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400 flex gap-1.5 flex-wrap">
      <span>Case: {item.case_id}</span>
      {#if item.tags?.length}
        <span aria-hidden="true">·</span>
        <span>Tags: {item.tags.join(', ')}</span>
      {/if}
      {#if item.age_hours != null}
        <span aria-hidden="true">·</span>
        <span>{item.age_hours} h old</span>
      {/if}
    </p>

    <!-- Inline action buttons (Phase 2.8 visual revision).
         These match the button style used by AuditTable / CaseList
         so the Inbox row is no longer the only place that lacks
         direct per-row actions. -->
    <div class="mt-2 flex flex-wrap gap-2">
      <button
        type="button"
        class="text-xs px-2 py-1 rounded
               border border-gray-300 dark:border-gray-600
               bg-white dark:bg-gray-700
               text-gray-800 dark:text-gray-100
               hover:bg-gray-100 dark:hover:bg-gray-600
               focus:outline-none focus:ring-2 focus:ring-blue-500"
        data-testid="inbox-row-open"
        onclick={handleOpen}
        title={t?.caseSpace?.inbox?.open ?? 'Open this debate in its main view'}
      >
        {t?.caseSpace?.inbox?.open ?? 'Open'}
      </button>
      <button
        type="button"
        class="text-xs px-2 py-1 rounded
               border border-gray-300 dark:border-gray-600
               bg-white dark:bg-gray-700
               text-gray-800 dark:text-gray-100
               hover:bg-gray-100 dark:hover:bg-gray-600
               focus:outline-none focus:ring-2 focus:ring-blue-500"
        data-testid="inbox-row-tag"
        onclick={handleTag}
        title={t?.caseSpace?.inbox?.tag ?? 'Add tags to this item'}
      >
        {t?.caseSpace?.inbox?.tag ?? 'Tag'}
      </button>
      <button
        type="button"
        class="text-xs px-2 py-1 rounded
               border border-gray-300 dark:border-gray-600
               bg-white dark:bg-gray-700
               text-gray-800 dark:text-gray-100
               hover:bg-gray-100 dark:hover:bg-gray-600
               focus:outline-none focus:ring-2 focus:ring-blue-500"
        data-testid="inbox-row-move"
        onclick={handleMove}
        title={t?.caseSpace?.inbox?.move ?? 'Move this item to another case'}
      >
        {t?.caseSpace?.inbox?.move ?? 'Move'}
      </button>
      <button
        type="button"
        class="text-xs px-2 py-1 rounded
               border border-amber-300 dark:border-amber-600
               bg-amber-50 dark:bg-amber-900/30
               text-amber-800 dark:text-amber-200
               hover:bg-amber-100 dark:hover:bg-amber-900/50
               focus:outline-none focus:ring-2 focus:ring-amber-500"
        data-testid="inbox-row-delete"
        onclick={handleArchive}
        title={t?.caseSpace?.inbox?.delete ?? 'Delete this item from the Inbox'}
      >
        {t?.caseSpace?.inbox?.delete ?? 'Delete'}
      </button>
    </div>
  </div>
</li>

<style>
  /* The kind badges are colour-coded (status semantics), so
     they keep their own dark-mode counterpart baked into the
     same hex so they stay recognisable in both themes. */
  .kind-badge[data-kind="recently_completed"] {
    background: #dbeafe;
    color: #1e40af;
  }
  :global(.dark) .kind-badge[data-kind="recently_completed"] {
    background: #1e3a8a;
    color: #dbeafe;
  }
  .kind-badge[data-kind="untagged"] {
    background: #fef3c7;
    color: #92400e;
  }
  :global(.dark) .kind-badge[data-kind="untagged"] {
    background: #78350f;
    color: #fef3c7;
  }
  .kind-badge[data-kind="stale_running"] {
    background: #fee2e2;
    color: #991b1b;
  }
  :global(.dark) .kind-badge[data-kind="stale_running"] {
    background: #7f1d1d;
    color: #fee2e2;
  }
</style>
