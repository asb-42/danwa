<!--
  Case-Space Workspace — primary view of the new Case-Space UI.

  This view is the entry point for the Case-Space redesign described in
  plans/2026-06-14_case-space-workspace.md (Phase 1).  It shows the
  currently active case with three cards:
    - This Case: debates, documents, tags of the active case
    - Suggested Next Steps: contextual hints (empty-state nudges in P1)
    - Recent Activity: list of recent audit-style events (P1: empty)

  The view is intentionally minimal in P1 — it is the integration point
  that proves the backend → store → view chain works.  Richer
  sub-components (debate list, document uploader, etc.) are added in
  later phases; see plans/2026-06-14_case-space-impl-todos.md.

  @see plans/2026-06-14_case-space-workspace.md
  @see plans/2026-06-14_case-space-impl-todos.md (Phase 1.7)
-->
<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { feedbackStore } from '../lib/stores/feedback.svelte.js';
  import {
    workspaceStore,
    setActiveCase,
    loadSummary,
    reset,
    restoreLastWorkspace,
    persistActiveCase,
  } from '../lib/stores/workspaceStore.svelte.js';
  import NewDebateForm from '../components/case-space/NewDebateForm.svelte';
  import InspectorGraphTab from '../components/case-space/InspectorGraphTab.svelte';

  let { navigate = () => {}, initialCaseId = null } = $props();

  // ─── Phase 3.7 — New-debate disambiguation modal ─────────────
  // The modal is opened from the "Start a debate" button in the
  // "This Case" card.  It captures the case context (existing vs.
  // new) and the initial topic, then defers to the existing
  // DebateCreatePanel for advanced parameters.
  // Phase 5.4 — the Workspace summary now offers two views:
  //   - 'summary' : the 3 cards (This Case, Suggested, Recent)
  //   - 'graph'   : 1-hop graph around the active case
  let activeTab = $state('summary');
  let showNewDebateForm = $state(false);
  function openNewDebate() {
    showNewDebateForm = true;
  }

  /**
   * Handle a click on a Suggested Next Steps action button.
   * Two well-known step kinds from the backend are special-cased
   * (no_documents -> document uploader, no_debates -> open the
   * new-debate modal locally).  Other steps honour
   * step.action_target as a full relative app-route and pass
   * the sub-path through to navigate().
   */
  function openDocumentUploader() {
    // Phase 3.8 TODO: dedicated "upload" route.  For now we
    // route the user to the document management view which
    // already exposes a DocumentUploader.
    if (typeof navigate === 'function') {
      navigate('documents');
    } else if (typeof window !== 'undefined') {
      window.location.hash = '#/documents';
    }
  }

  function handleSuggestionAction(step) {
    if (!step) return;
    if (step.kind === 'no_documents') {
      openDocumentUploader();
      return;
    }
    if (step.kind === 'no_debates') {
      openNewDebate();
      return;
    }
    const target = (step.action_target || '').replace(/^\//, '');
    if (!target) return;
    const parts = target.split('/').filter(Boolean);
    const route = parts[0] || 'workspace';
    const sub = parts.slice(1).join('/');
    if (typeof navigate === 'function') {
      navigate(route, sub ? { sub } : undefined);
    } else if (typeof window !== 'undefined') {
      window.location.hash = '#/' + target;
    }
  }
  function closeNewDebate() {
    showNewDebateForm = false;
  }
  function handleNewDebateCreated(debate, caseCtx) {
    showNewDebateForm = false;
    const caseId = caseCtx?.id || debate?.case_id || workspaceStore.activeCaseId;
    const debateId = debate?.debate_id || debate?.id;
    if (navigate && caseId) {
      // Refresh summary so the new debate count shows up
      loadSummary();
      // Hand the user off to the debate view; if the parent does
      // not provide a debate view route, we fall back to the
      // case-scoped input composer.
      if (debateId) {
        navigate('debate', { caseId, debateId });
      } else {
        navigate('input', { caseId });
      }
    }
  }

  // ─── URL state sync (Phase 1.9) ──────────────────────────────────
  // The active case id is mirrored to ?case=… in the URL so the
  // workspace supports deep-linking and the browser back/forward
  // buttons.  We use the History API to avoid triggering a router
  // navigation in apps that have their own router.

  const URL_PARAM = 'case';

  function readCaseFromUrl() {
    if (typeof window === 'undefined') return null;
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get(URL_PARAM) || null;
    } catch {
      return null;
    }
  }

  function writeCaseToUrl(id) {
    if (typeof window === 'undefined') return;
    try {
      const url = new URL(window.location.href);
      if (id) {
        url.searchParams.set(URL_PARAM, id);
      } else {
        url.searchParams.delete(URL_PARAM);
      }
      // Use replaceState so the user's back/forward history isn't
      // cluttered when they switch cases by typing in the input.
      window.history.replaceState(null, '', url.toString());
    } catch {
      // best-effort; do not crash the view on URL issues
    }
  }

  function handlePopState() {
    // User clicked browser back/forward → re-sync the active case
    const id = readCaseFromUrl();
    if (id && id !== workspaceStore.activeCaseId) {
      setActiveCase(id);
    } else if (!id && workspaceStore.activeCaseId) {
      reset();
    }
  }


  // Read Svelte 5 runes proxy as plain JS
  let t = $derived($tStore);
  let summary = $derived(workspaceStore.summary);
  let loading = $derived(workspaceStore.loading);
  let error = $derived(workspaceStore.error);
  let activeCaseId = $derived(workspaceStore.activeCaseId);
  let caseSpaceDisabled = $derived(workspaceStore.caseSpaceDisabled);

  onMount(() => {
    // Phase 6.2 / C5 telemetry: log that the user entered the
    // Workspace view.  This is one of the four case-space
    // events called out in plans/2026-06-14_case-space-workspace.md
    // §6.2 (workspace_view, inbox_open, graph_view, bulk_action_used).
    feedbackStore.logActivity(
      'case-space',
      'workspace-view',
      'Workspace view mounted',
      { hasInitialCaseId: Boolean(initialCaseId) }
    );
    // URL > prop precedence: the explicit URL query param wins over
    // any prop passed in, because deep links should be sticky.
    const fromUrl = readCaseFromUrl();
    if (fromUrl) {
      setActiveCase(fromUrl);
    } else if (initialCaseId) {
      setActiveCase(initialCaseId);
      writeCaseToUrl(initialCaseId);
    } else {
      // Last fallback: restore the user's last opened case from
      // the backend (Phase 1.3 + 1.10).  The async restore
      // happens in parallel with the URL-state setup; the load
      // triggered by the $effect below will pick up whichever id
      // ends up in the store at that point.
      restoreLastWorkspace();
    }
    if (workspaceStore.activeCaseId) {
      loadSummary();
    }
    window.addEventListener('popstate', handlePopState);
    return () => {
      // On unmount: do NOT reset() — other views may still want the
      // cached summary when the user navigates back.  But we MUST
      // remove the popstate listener to avoid leaks.
      window.removeEventListener('popstate', handlePopState);
    };
  });

  // Mirror active case → URL AND persist to backend whenever it
  // changes via internal flow (form submit, CaseSelector, restore,
  // reset).  Two side effects share the same trigger so the
  // URL-state and the backend setting stay in lockstep.
  $effect(() => {
    const id = workspaceStore.activeCaseId;
    writeCaseToUrl(id);
    // Best-effort persistence; the store's persistActiveCase handles
    // the network call and logs errors silently so the user isn't
    // interrupted.
    if (id !== null) {
      persistActiveCase();
    }
  });

  // Re-fetch when the active case id changes (e.g. user typed in
  // the CaseSelector).  setActiveCase nulls the summary, so this
  // effect fires whenever the id transitions.
  $effect(() => {
    if (activeCaseId) {
      loadSummary();
    }
  });

  // ─── Case-Liste für den Empty-State ────────────────────────
  // Anstatt den User nach einer case-id zu fragen (was dem
  // Konzept widerspricht — siehe plans/2026-06-14_case-space-
  // workspace.md §4.2), zeigen wir die existierenden Cases des
  // aktuellen Tenants als klickbare Liste an.  Wer keinen Case
  // hat, sieht den Welcome-Hinweis.
  let availableCases = $state([]);
  let availableCasesLoading = $state(false);
  let availableCasesLoaded = $state(false);

  $effect(() => {
    const tid = $currentTenant?.id;
    if (!tid || activeCaseId) return;
    if (availableCasesLoaded || availableCasesLoading) return;
    availableCasesLoading = true;
    import('../lib/api/case.js').then(({ getCases }) =>
      getCases(tid)
        .then((list) => {
          availableCases = Array.isArray(list) ? list : [];
          availableCasesLoaded = true;
        })
        .catch(() => {
          availableCases = [];
          availableCasesLoaded = true;
        })
        .finally(() => {
          availableCasesLoading = false;
        })
    );
  });

  function pickCaseFromList(c) {
    if (!c) return;
    setActiveCase(c.id);
  }
</script>

<section
  class="max-w-6xl mx-auto p-6
         text-gray-900 dark:text-gray-100"
  aria-label="Case-Space Workspace"
>
  <header class="mb-6">
    <h1 class="text-2xl font-bold text-gray-100">
      {t?.caseSpace?.workspace?.title ?? 'Workspace'}
    </h1>
    <p class="text-sm text-gray-400">
      {t?.caseSpace?.workspace?.subtitle ??
        'Focus on a single case. Everything you need in one place.'}
    </p>
  </header>

  {#if caseSpaceDisabled}
    <div
          class="banner p-4 rounded-md border
                 bg-yellow-50 dark:bg-yellow-900/20
                 border-yellow-200 dark:border-yellow-700
                 text-yellow-900 dark:text-yellow-100"
          role="status"
        >
      <strong>{t?.caseSpace?.workspace?.flagOffTitle ?? 'Case-Space is not enabled'}</strong>
      <p>
        {t?.caseSpace?.workspace?.flagOffBody ??
          'Set DANWA_ENABLE_CASE_SPACE=true on the backend to use the new view. The legacy Cases list is still available.'}
      </p>
      {#if navigate}
        <button class="btn" onclick={() => navigate('cases')}>
          {t?.caseSpace?.workspace?.goToLegacy ?? 'Open legacy Cases view'}
        </button>
      {/if}
    </div>
  {/if}

  {#if !activeCaseId}
    <div
      class="p-5 border rounded-lg max-w-2xl
             bg-white dark:bg-gray-800
             border-gray-200 dark:border-gray-700
             text-gray-900 dark:text-gray-100"
      data-testid="case-picker"
    >
      <h2 class="text-lg font-semibold mb-1">
        {t?.caseSpace?.workspace?.pickCaseTitle ??
          'Pick a case to focus your workspace'}
      </h2>
      <p class="text-sm mb-4 text-gray-600 dark:text-gray-400">
        {t?.caseSpace?.workspace?.pickCaseHint ??
          'Every debate and document lives in a case. Choose one to continue.'}
      </p>

      {#if availableCasesLoading}
        <p class="text-sm text-gray-500 dark:text-gray-400" role="status">
          {t?.caseSpace?.workspace?.loadingCases ?? 'Loading cases…'}
        </p>
      {:else if availableCases.length === 0}
        <div
          class="p-6 border border-dashed rounded-md text-center
                 bg-gray-50 dark:bg-gray-700/40
                 border-gray-300 dark:border-gray-600
                 text-gray-700 dark:text-gray-200"
          data-testid="case-picker-empty"
        >
          <p class="mb-3">
            {t?.caseSpace?.workspace?.noCases ??
              'No cases in this tenant yet.'}
          </p>
          <div class="flex gap-2 justify-center flex-wrap">
            <button
              type="button"
              class="inline-flex items-center px-4 py-2 rounded-md
                     bg-blue-600 hover:bg-blue-700 text-white font-medium
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="create-first-case"
              onclick={() => {
                // Inline-Erstellung eines Cases direkt aus dem
                // Workspace (deckt Konzept §4.2 "Der Case ist die
                // Heimat" ab — der User muss nicht erst zur
                // Cases-View navigieren).
                const title = window.prompt(
                  t?.caseSpace?.workspace?.promptCaseTitle ??
                    'Title for the new case:'
                );
                if (!title || !title.trim()) return;
                import('../lib/api/case.js').then(({ createCase }) => {
                  const tid = $currentTenant?.id;
                  if (!tid) return;
                  createCase(tid, { title: title.trim(), description: '', tags: [] })
                    .then((c) => {
                      availableCases = [c, ...availableCases];
                      setActiveCase(c.id);
                    })
                    .catch((err) => {
                      window.alert(
                        (t?.caseSpace?.workspace?.createFailed ??
                          'Could not create case:') +
                          ' ' +
                          (err?.message || String(err))
                      );
                    });
                });
              }}
            >
              {t?.caseSpace?.workspace?.createFirstCase ?? '+ Create your first case'}
            </button>
            {#if navigate}
              <button
                class="inline-flex items-center px-4 py-2 rounded-md
                       bg-gray-100 dark:bg-gray-700
                       text-gray-700 dark:text-gray-200
                       hover:bg-gray-200 dark:hover:bg-gray-600
                       focus:outline-none focus:ring-2 focus:ring-blue-500"
                onclick={() => navigate('cases')}
              >
                {t?.caseSpace?.workspace?.openCasesView ?? 'Open Cases view'}
              </button>
            {/if}
          </div>
        </div>
      {:else}
        <ul class="grid grid-cols-1 sm:grid-cols-2 gap-2 list-none p-0" role="list">
          {#each availableCases as c (c.id)}
            <li>
              <button
                type="button"
                class="flex flex-col items-start gap-1 w-full text-left p-3
                       border rounded-md
                       border-gray-200 dark:border-gray-700
                       bg-white dark:bg-gray-700/40
                       hover:border-blue-500
                       text-gray-900 dark:text-gray-100
                       focus:outline-none focus:ring-2 focus:ring-blue-500"
                data-testid="case-list-item"
                onclick={() => pickCaseFromList(c)}
              >
                <span class="font-semibold">{c.title}</span>
                {#if c.description}
                  <span class="text-xs text-gray-500 dark:text-gray-400">
                    {c.description}
                  </span>
                {/if}
                <span class="text-[0.7rem] font-mono text-gray-400 dark:text-gray-500"
                      aria-hidden="true">{c.id}</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {:else}
    {#if loading}
      <p class="loading" role="status">
        {t?.caseSpace?.workspace?.loading ?? 'Loading workspace…'}
      </p>
    {:else if error}
      <div
          class="banner p-4 rounded-md border
                 bg-red-50 dark:bg-red-900/20
                 border-red-200 dark:border-red-700
                 text-red-900 dark:text-red-100"
          role="alert"
        >
        <strong>{t?.caseSpace?.workspace?.errorTitle ?? 'Could not load workspace'}</strong>
        <p>{String(error?.message ?? error)}</p>
        <button class="btn" onclick={() => loadSummary()}>
          {t?.caseSpace?.workspace?.retry ?? 'Retry'}
        </button>
      </div>
    {:else if summary}
      {#if activeTab === 'summary'}
        <div role="tablist" aria-label="Workspace view" class="flex gap-2 mb-4">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'summary'}
            class="px-3 py-1.5 rounded-md text-sm font-medium {activeTab === 'summary' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600'}" onclick={() => (activeTab = 'summary')}
            data-testid="workspace-tab-summary"
          >
            Summary
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'graph'}
            class="px-3 py-1.5 rounded-md text-sm font-medium {activeTab === 'graph' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600'}" onclick={() => {
              activeTab = 'graph';
              // Phase 6.2 / C5 telemetry: graph_view event.
              feedbackStore.logActivity('case-space', 'graph-view', 'Workspace graph tab activated', { entityType: 'case' });
            }}
            data-testid="workspace-tab-graph"
          >
            Graph
          </button>
        </div>
              <article class="workspace-grid">
        <section
          class="card p-5 border rounded-lg
                 bg-white dark:bg-gray-800
                 border-gray-200 dark:border-gray-700
                 text-gray-900 dark:text-gray-100"
          aria-labelledby="card-this-case"
        >
          <h2 id="card-this-case" class="text-xl font-semibold mb-2 flex items-center gap-2 flex-wrap">
            <span>{summary.title}</span>
            <span
              class="text-xs font-medium px-2 py-0.5 rounded
                     bg-gray-100 dark:bg-gray-700
                     text-gray-700 dark:text-gray-200"
              data-status={summary.status}
            >
              {summary.status}
            </span>
          </h2>
          {#if summary.description}
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
              {summary.description}
            </p>
          {/if}
          {#if summary.tags?.length}
            <ul class="flex flex-wrap gap-1 mb-3 list-none p-0" aria-label="Tags">
              {#each summary.tags as tag}
                <li class="text-xs px-2 py-0.5 rounded
                           bg-gray-100 dark:bg-gray-700
                           text-gray-700 dark:text-gray-200">{tag}</li>
              {/each}
            </ul>
          {/if}
          <dl class="grid grid-cols-3 gap-4 mb-4">
            <div>
              <dt class="text-xs uppercase tracking-wide
                         text-gray-500 dark:text-gray-400">
                {t?.caseSpace?.workspace?.debates ?? 'Debates'}
              </dt>
              <dd class="text-2xl font-semibold
                         text-gray-900 dark:text-white">
                {summary.debate_count}
              </dd>
            </div>
            <div>
              <dt class="text-xs uppercase tracking-wide
                         text-gray-500 dark:text-gray-400">
                {t?.caseSpace?.workspace?.documents ?? 'Documents'}
              </dt>
              <dd class="text-2xl font-semibold
                         text-gray-900 dark:text-white">
                {summary.document_count}
              </dd>
            </div>
            <div>
              <dt class="text-xs uppercase tracking-wide
                         text-gray-500 dark:text-gray-400">
                {t?.caseSpace?.workspace?.members ?? 'Members'}
              </dt>
              <dd class="text-2xl font-semibold
                         text-gray-900 dark:text-white">
                {summary.members?.length ?? 0}
              </dd>
            </div>
          </dl>
          <div class="case-actions">
            <button
              type="button"
              class="inline-flex items-center px-4 py-2 rounded-md
                     bg-blue-600 hover:bg-blue-700
                     text-white font-medium
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="open-new-debate"
              onclick={openNewDebate}
            >
              {t?.caseSpace?.workspace?.startDebate ?? 'Start a debate'}
            </button>
          </div>
        </section>

        <section
          class="card p-5 border rounded-lg
                 bg-white dark:bg-gray-800
                 border-gray-200 dark:border-gray-700
                 text-gray-900 dark:text-gray-100"
          aria-labelledby="card-suggestions"
        >
          <h2 id="card-suggestions" class="text-xl font-semibold mb-3">
            {t?.caseSpace?.workspace?.suggestedNextSteps ?? 'Suggested next steps'}
          </h2>
          {#if summary.suggested_next_steps?.length}
            <ul class="space-y-2 list-none p-0">
              {#each summary.suggested_next_steps as step}
                <li class="flex items-start gap-3 p-3 rounded
                           border
                           border-gray-200 dark:border-gray-700
                           bg-gray-50 dark:bg-gray-700/40"
                    data-severity={step.severity}>
                  <span class="flex-1 text-sm
                               text-gray-800 dark:text-gray-200">
                    {step.message}
                  </span>
                  {#if step.action_label}
                    <button
                      type="button"
                      class="text-xs font-medium px-3 py-1 rounded
                             bg-blue-100 dark:bg-blue-900/40
                             text-blue-800 dark:text-blue-200
                             hover:bg-blue-200 dark:hover:bg-blue-900/60
                             focus:outline-none focus:ring-2 focus:ring-blue-500"
                      onclick={() => handleSuggestionAction(step)}
                    >
                      {step.action_label}
                    </button>
                  {/if}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="text-sm italic
                     text-gray-500 dark:text-gray-400">
              {t?.caseSpace?.workspace?.allClear ??
                'Nothing to suggest right now. The case is in good shape.'}
            </p>
          {/if}
        </section>

        <section
          class="card p-5 border rounded-lg
                 bg-white dark:bg-gray-800
                 border-gray-200 dark:border-gray-700
                 text-gray-900 dark:text-gray-100"
          aria-labelledby="card-recent"
        >
          <h2 id="card-recent" class="text-xl font-semibold mb-3">
            {t?.caseSpace?.workspace?.recentActivity ?? 'Recent activity'}
          </h2>
          {#if summary.recent_events?.length}
            <!-- Phase 3.6: Inspector columns.  We add a phase badge
                 and a round column inline so the user can see
                 context without opening AuditView.  Click on a
                 row to drill into the full audit for that debate. -->
            <div class="overflow-x-auto">
              <table class="w-full text-sm" data-testid="recent-audit-table">
                <thead>
                  <tr class="text-xs uppercase tracking-wider
                             text-gray-500 dark:text-gray-400">
                    <th class="text-left font-medium py-1">Event</th>
                    <th class="text-left font-medium py-1">Phase</th>
                    <th class="text-left font-medium py-1">Round</th>
                    <th class="text-left font-medium py-1">Subject</th>
                    <th class="text-left font-medium py-1">When</th>
                  </tr>
                </thead>
                <tbody>
                  {#each summary.recent_events as ev}
                    <tr
                      class="border-t border-gray-200 dark:border-gray-700
                             hover:bg-gray-50 dark:hover:bg-gray-700/30
                             cursor-pointer"
                      data-testid="recent-audit-row"
                      onclick={() => {
                        if (ev.debate_id && typeof navigate === 'function') {
                          navigate('audit', { debateId: ev.debate_id });
                        }
                      }}
                    >
                      <td class="py-1.5">
                        <span class="text-xs font-mono px-2 py-0.5 rounded
                                     bg-gray-100 dark:bg-gray-700
                                     text-gray-700 dark:text-gray-200">
                          {ev.event_type}
                        </span>
                      </td>
                      <td class="py-1.5">
                        {#if ev.phase}
                          <span class="text-xs px-1.5 py-0.5 rounded
                                       bg-indigo-50 dark:bg-indigo-900/30
                                       text-indigo-700 dark:text-indigo-200">
                            {ev.phase}
                          </span>
                        {:else}
                          <span class="text-xs text-gray-400">—</span>
                        {/if}
                      </td>
                      <td class="py-1.5 text-xs font-mono
                                 text-gray-500 dark:text-gray-400">
                        {ev.round ?? '—'}
                      </td>
                      <td class="py-1.5 truncate max-w-[180px]
                                 text-gray-800 dark:text-gray-200">
                        {ev.subject ?? ev.id}
                      </td>
                      <td class="py-1.5 text-xs font-mono
                                 text-gray-500 dark:text-gray-400">
                        {ev.created_at}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
            <a
              class="inline-block mt-2 text-sm
                     text-blue-600 dark:text-blue-400
                     hover:underline
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="show-full-audit"
              onclick={(e) => {
                e.preventDefault();
                const lastDebate = summary.recent_events.find((x) => x.debate_id);
                if (typeof navigate === 'function') {
                  navigate('audit', lastDebate?.debate_id ? { debateId: lastDebate.debate_id } : undefined);
                } else if (typeof window !== 'undefined') {
                  window.location.hash = '#/audit';
                }
              }}
              role="button"
              tabindex="0"
            >
              {t?.caseSpace?.workspace?.showFullAudit ??
                'Show full audit →'}
            </a>
          {:else}
            <p class="text-sm italic
                     text-gray-500 dark:text-gray-400">
              {t?.caseSpace?.workspace?.noRecent ??
                'No recent activity yet. Run a debate or upload a document to see events here.'}
            </p>
          {/if}
        </section>
      </article>
      {:else if activeTab === 'graph'}
        <div class="max-w-3xl">
          <InspectorGraphTab entityType="case" entityId={activeCaseId} hops={1} />
        </div>
      {/if}

      <footer class="flex items-center justify-between mt-4 text-xs text-gray-500 dark:text-gray-400">
        <small>
          {t?.caseSpace?.workspace?.generatedAt ?? 'Generated at'}:
          <time class="font-mono ml-1">{summary.generated_at}</time>
        </small>
        <button
          class="text-blue-600 dark:text-blue-400 hover:underline
                 focus:outline-none focus:ring-2 focus:ring-blue-500"
          onclick={() => reset()}
        >
          {t?.caseSpace?.workspace?.clearActive ?? 'Switch case'}
        </button>
      </footer>
    {/if}
  {/if}

  {#if showNewDebateForm}
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4
             bg-black/50"
      role="presentation"
      onclick={closeNewDebate}
      onkeydown={(e) => {
        if (e.key === 'Escape') closeNewDebate();
      }}
    >
      <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
      <div
        class="modal w-full max-w-2xl max-h-[90vh] overflow-auto
               rounded-lg shadow-xl
               bg-white dark:bg-gray-800
               text-gray-900 dark:text-gray-100"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-debate-modal-title"
        tabindex="-1"
        onclick={(e) => e.stopPropagation()}
      >
        <NewDebateForm
          onCreated={handleNewDebateCreated}
          onCancel={closeNewDebate}
        />
      </div>
    </div>
  {/if}
</section>

<style>
  /* Layout-only CSS: every visual property (colours, borders,
     background) is now inline Tailwind on each element, paired
     with its dark: variant, so the workspace honours whichever
     theme the rest of the app is running. */
  .workspace-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    grid-template-areas:
      'this-case suggestions'
      'this-case recent';
    gap: 1rem;
  }
  @media (max-width: 768px) {
    .workspace-grid {
      grid-template-columns: 1fr;
      grid-template-areas:
        'this-case'
        'suggestions'
        'recent';
    }
  }
  .this-case { grid-area: this-case; }
  .suggestions { grid-area: suggestions; }
  .recent { grid-area: recent; }
  .case-actions {
    margin-top: 0.75rem;
    display: flex;
    gap: 0.5rem;
  }
</style>
