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
  import {
    workspaceStore,
    setActiveCase,
    loadSummary,
    reset,
    restoreLastWorkspace,
    persistActiveCase,
  } from '../lib/stores/workspaceStore.svelte.js';
  import NewDebateForm from '../components/case-space/NewDebateForm.svelte';

  let { navigate = () => {}, initialCaseId = null } = $props();

  // ─── Phase 3.7 — New-debate disambiguation modal ─────────────
  // The modal is opened from the "Start a debate" button in the
  // "This Case" card.  It captures the case context (existing vs.
  // new) and the initial topic, then defers to the existing
  // DebateCreatePanel for advanced parameters.
  let showNewDebateForm = $state(false);
  function openNewDebate() {
    showNewDebateForm = true;
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

<section class="workspace-view" aria-label="Case-Space Workspace">
  <header class="workspace-header">
    <h1>{t?.caseSpace?.workspace?.title ?? 'Workspace'}</h1>
    <p class="subtitle">
      {t?.caseSpace?.workspace?.subtitle ??
        'Focus on a single case. Everything you need in one place.'}
    </p>
  </header>

  {#if caseSpaceDisabled}
    <div class="banner banner-warning" role="status">
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
    <div class="case-picker" data-testid="case-picker">
      <h2 class="case-picker-title">
        {t?.caseSpace?.workspace?.pickCaseTitle ??
          'Pick a case to focus your workspace'}
      </h2>
      <p class="case-picker-hint">
        {t?.caseSpace?.workspace?.pickCaseHint ??
          'Every debate and document lives in a case. Choose one to continue.'}
      </p>

      {#if availableCasesLoading}
        <p class="loading" role="status">
          {t?.caseSpace?.workspace?.loadingCases ?? 'Loading cases…'}
        </p>
      {:else if availableCases.length === 0}
        <div class="empty-state" data-testid="case-picker-empty">
          <p>
            {t?.caseSpace?.workspace?.noCases ??
              'No cases in this tenant yet.'}
          </p>
          <div class="empty-state-actions">
            <button
              type="button"
              class="btn btn-primary"
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
              <button class="btn" onclick={() => navigate('cases')}>
                {t?.caseSpace?.workspace?.openCasesView ?? 'Open Cases view'}
              </button>
            {/if}
          </div>
        </div>
      {:else}
        <ul class="case-list" role="list">
          {#each availableCases as c (c.id)}
            <li>
              <button
                type="button"
                class="case-list-item"
                data-testid="case-list-item"
                onclick={() => pickCaseFromList(c)}
              >
                <span class="case-list-title">{c.title}</span>
                {#if c.description}
                  <span class="case-list-desc">{c.description}</span>
                {/if}
                <span class="case-list-id" aria-hidden="true">{c.id}</span>
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
      <div class="banner banner-error" role="alert">
        <strong>{t?.caseSpace?.workspace?.errorTitle ?? 'Could not load workspace'}</strong>
        <p>{String(error?.message ?? error)}</p>
        <button class="btn" onclick={() => loadSummary()}>
          {t?.caseSpace?.workspace?.retry ?? 'Retry'}
        </button>
      </div>
    {:else if summary}
      <article class="workspace-grid">
        <section class="card this-case" aria-labelledby="card-this-case">
          <h2 id="card-this-case">
            {summary.title}
            <span class="status" data-status={summary.status}>
              {summary.status}
            </span>
          </h2>
          {#if summary.description}
            <p class="description">{summary.description}</p>
          {/if}
          {#if summary.tags?.length}
            <ul class="tags" aria-label="Tags">
              {#each summary.tags as tag}
                <li class="tag">{tag}</li>
              {/each}
            </ul>
          {/if}
          <dl class="counts">
            <div>
              <dt>{t?.caseSpace?.workspace?.debates ?? 'Debates'}</dt>
              <dd>{summary.debate_count}</dd>
            </div>
            <div>
              <dt>{t?.caseSpace?.workspace?.documents ?? 'Documents'}</dt>
              <dd>{summary.document_count}</dd>
            </div>
            <div>
              <dt>{t?.caseSpace?.workspace?.members ?? 'Members'}</dt>
              <dd>{summary.members?.length ?? 0}</dd>
            </div>
          </dl>
          <div class="case-actions">
            <button
              type="button"
              class="btn btn-primary"
              data-testid="open-new-debate"
              onclick={openNewDebate}
            >
              {t?.caseSpace?.workspace?.startDebate ?? 'Start a debate'}
            </button>
          </div>
        </section>

        <section class="card suggestions" aria-labelledby="card-suggestions">
          <h2 id="card-suggestions">
            {t?.caseSpace?.workspace?.suggestedNextSteps ?? 'Suggested next steps'}
          </h2>
          {#if summary.suggested_next_steps?.length}
            <ul>
              {#each summary.suggested_next_steps as step}
                <li class="step" data-severity={step.severity}>
                  <span class="step-message">{step.message}</span>
                  {#if step.action_label}
                    <span class="step-action">{step.action_label}</span>
                  {/if}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="empty">
              {t?.caseSpace?.workspace?.allClear ??
                'Nothing to suggest right now. The case is in good shape.'}
            </p>
          {/if}
        </section>

        <section class="card recent" aria-labelledby="card-recent">
          <h2 id="card-recent">
            {t?.caseSpace?.workspace?.recentActivity ?? 'Recent activity'}
          </h2>
          {#if summary.recent_events?.length}
            <ul>
              {#each summary.recent_events as ev}
                <li>
                  <span class="event-type">{ev.event_type}</span>
                  <span class="event-subject">{ev.subject ?? ev.id}</span>
                  <time>{ev.created_at}</time>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="empty">
              {t?.caseSpace?.workspace?.noRecent ??
                'No recent activity yet. Run a debate or upload a document to see events here.'}
            </p>
          {/if}
        </section>
      </article>

      <footer class="workspace-footer">
        <small>
          {t?.caseSpace?.workspace?.generatedAt ?? 'Generated at'}:
          <time>{summary.generated_at}</time>
        </small>
        <button class="btn btn-link" onclick={() => reset()}>
          {t?.caseSpace?.workspace?.clearActive ?? 'Switch case'}
        </button>
      </footer>
    {/if}
  {/if}

  {#if showNewDebateForm}
    <div
      class="modal-backdrop"
      role="presentation"
      onclick={closeNewDebate}
      onkeydown={(e) => {
        if (e.key === 'Escape') closeNewDebate();
      }}
    >
      <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
      <div
        class="modal"
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
  .workspace-view {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem;
  }
  .workspace-header h1 {
    margin: 0 0 0.25rem;
    font-size: 1.75rem;
    color: #f3f4f6; /* readable on dark page background */
  }
  .workspace-header .subtitle {
    margin: 0 0 1.5rem;
    color: #9ca3af;
  }
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
  .card {
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 8px;
    padding: 1rem 1.25rem;
  }
  .card h2 {
    margin: 0 0 0.5rem;
    font-size: 1.15rem;
    color: #111827;
  }
  .status {
    margin-left: 0.5rem;
    font-size: 0.75rem;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    background: var(--color-bg-muted, #eee);
  }
  .description {
    color: var(--color-text-muted, #666);
    margin: 0 0 0.75rem;
  }
  .tags {
    list-style: none;
    padding: 0;
    margin: 0 0 0.75rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }
  .tag {
    background: var(--color-bg-muted, #eee);
    padding: 0.1rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }
  .counts {
    display: flex;
    gap: 1.5rem;
    margin: 0;
  }
  .counts dt { font-size: 0.8rem; color: var(--color-text-muted, #666); }
  .counts dd { margin: 0; font-size: 1.4rem; font-weight: 600; }
  .empty {
    color: #4b5563;
    font-style: italic;
    margin: 0.5rem 0 0;
  }
  .banner {
    padding: 1rem 1.25rem;
    border-radius: 6px;
    margin: 0 0 1rem;
    color: var(--color-text, #111);
  }
  .banner strong { color: inherit; }
  .banner p { margin: 0.25rem 0 0; color: inherit; }
  .banner-warning { background: #fff3cd; border: 1px solid #ffeaa7; color: #5c4400; }
  .banner-error   { background: #fde8e8; border: 1px solid #f5c6cb; color: #7a1212; }
  .case-picker {
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 8px;
    padding: 1.25rem;
    max-width: 720px;
  }
  .case-picker-title {
    margin: 0 0 0.25rem;
    font-size: 1.1rem;
  }
  .case-picker-hint {
    margin: 0 0 1rem;
    color: #4b5563;
    font-size: 0.9rem;
  }
  .case-picker-title {
    margin: 0 0 0.25rem;
    font-size: 1.1rem;
    color: #111827;
  }
  .empty-state {
    background: #f9fafb;
    border: 1px dashed #d1d5db;
    border-radius: 6px;
    padding: 1.5rem;
    text-align: center;
    color: #1f2937;
  }
  .empty-state-actions {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    margin-top: 1rem;
    flex-wrap: wrap;
  }
  .case-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.5rem;
  }
  .case-list-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.15rem;
    width: 100%;
    text-align: left;
    background: var(--color-bg, #fff);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    padding: 0.7rem 0.9rem;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }
  .case-list-item:hover {
    background: var(--color-bg-muted, #f3f4f6);
    border-color: var(--color-primary, #3b82f6);
  }
  .case-list-title {
    font-weight: 600;
    color: #111827;
  }
  .case-list-desc {
    color: #4b5563;
    font-size: 0.85rem;
  }
  .case-list-id {
    font-family: var(--font-mono, monospace);
    font-size: 0.7rem;
    color: var(--color-text-muted, #9ca3af);
  }
  .btn {
    padding: 0.4rem 0.85rem;
    border: 1px solid var(--color-border, #ddd);
    background: var(--color-bg-elevated, #fff);
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-primary { background: var(--color-primary, #3b82f6); color: white; border-color: transparent; }
  .btn-link { background: transparent; border: none; color: var(--color-primary, #3b82f6); }
  .workspace-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 1rem;
    color: var(--color-text-muted, #666);
  }
  .case-actions {
    margin-top: 0.75rem;
    display: flex;
    gap: 0.5rem;
  }
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 1rem;
  }
  .modal {
    max-height: 90vh;
    overflow: auto;
    border-radius: 8px;
    background: transparent;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
  }
</style>
