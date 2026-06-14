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

  let { item, selected = false, onCheck = () => {} } = $props();

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
</script>

<li class="flex items-start gap-3 px-4 py-3 mb-2 rounded-md border
           border-gray-200 dark:border-gray-700
           bg-white dark:bg-gray-800">
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
