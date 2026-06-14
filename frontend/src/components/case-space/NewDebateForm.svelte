<!--
  NewDebateForm — modal-style disambiguating form for starting a new debate.

  Phase 3.7 of plans/2026-06-14_case-space-impl-todos.md.  Implements the
  disambiguation described in §7.2 of plans/2026-06-14_case-space-workspace.md:

  - 3.7.1  Default = the active case from the workspace store, if any.
           Otherwise show a typeahead combobox (200 ms debounce) using
           the existing searchCases() helper.
  - 3.7.2  Inline creation of a new case (name + tags) is offered as
           the "Or create a new case" alternative when the user does
           not find a matching case.
  - 3.7.3  Top-3 tag suggestions of the active case are exposed as
           quick-buttons above the TagPicker.  Suggestions are
           recomputed whenever the active case id changes and hide
           as soon as the user picks tags manually (or the form
           resets).

  The form is intentionally *minimal*: it captures the case context
  (existing vs. new) and the initial debate topic.  The rich
  create-debate parameters (RAG, A2A, workflow selection, max rounds,
  consensus threshold, …) stay in the existing DebateCreatePanel
  inside the active case view — this form is the *entry point* that
  ensures the user never starts a debate without a case home.

  On successful submission the form calls `onCreated(debate, case)` so
  the parent can navigate to the new debate (e.g. into DebateView).

  @see plans/2026-06-14_case-space-workspace.md (§7.2)
  @see plans/2026-06-14_case-space-impl-todos.md (Phase 3.7)
-->
<script>
  import { onMount, untrack } from 'svelte';
  import { get } from 'svelte/store';
  import { tStore } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { addToast } from '../lib/stores.js';
  import { searchCases, getCase } from '../lib/api/workspace.js';
  import { createCase } from '../lib/api/case.js';
  import { createCaseDebate, startCaseDebate } from '../lib/api/case.js';
  import TagPicker from './TagPicker.svelte';

  let { onCreated = () => {}, onCancel = () => {} } = $props();

  let t = $derived($tStore);

  // ─── Mode: 'existing' (default) | 'new' ───────────────────────
  // Default = 'existing' when an active case is present, 'new' when
  // not.  The user can toggle at any time; the toggle only swaps the
  // case-context inputs.
  let mode = $state('existing');

  // ─── Active case (read from URL/store, NOT a prop) ─────────────
  // We deliberately reach into the URL via window.location to avoid a
  // circular import with workspaceStore.svelte.js.  The URL is the
  // single source of truth for the active case in the Case-Space UI.
  let activeCaseId = $state(null);

  // ─── Existing-case state ───────────────────────────────────────
  let selectedCaseId = $state(null);
  let caseSearchInput = $state('');
  let caseSearchResults = $state([]);
  let caseSearchLoading = $state(false);
  let caseSearchError = $state(null);
  let caseSearchTimer = null;

  // ─── New-case state ────────────────────────────────────────────
  let newCaseTitle = $state('');
  let newCaseTags = $state([]); // array of tag_ids (matches TagPicker value type)

  // ─── Debate topic ──────────────────────────────────────────────
  let topic = $state('');

  // ─── Tag suggestions for the new case (Top-3 from active case) ─
  let suggestedTags = $state([]); // [{ tag_id, name, color }]
  let suggestionsLoaded = $state(false);

  // ─── Submission state ──────────────────────────────────────────
  let submitting = $state(false);
  let submitError = $state(null);

  // ─── Lifecycle ─────────────────────────────────────────────────
  onMount(() => {
    const fromUrl = readCaseFromUrl();
    activeCaseId = fromUrl;
    if (fromUrl) {
      // Default = active case (3.7.1)
      mode = 'existing';
      selectedCaseId = fromUrl;
      loadActiveCaseTags(fromUrl);
    } else {
      // No active case → default to "new" so the user does not have
      // to click twice.  This is the "first-debate" path.
      mode = 'new';
    }
  });

  function readCaseFromUrl() {
    if (typeof window === 'undefined') return null;
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get('case') || null;
    } catch {
      return null;
    }
  }

  // ─── Active-case tag suggestions (3.7.3) ───────────────────────
  async function loadActiveCaseTags(caseId) {
    if (!caseId) {
      suggestedTags = [];
      return;
    }
    suggestionsLoaded = false;
    try {
      const tenant = get(currentTenant);
      if (!tenant?.id) {
        suggestedTags = [];
        return;
      }
      const c = await getCase(tenant.id, caseId);
      const tagIds = (c?.tags || c?.tag_ids || []).slice(0, 3);
      // TagPicker.svelte uses getTags() internally; here we look up
      // the lightweight tag list once and pick the matching objects.
      // The result is intentionally a minimal projection so the
      // component does not depend on the TagPicker internals.
      const { getTags } = await import('../lib/api/tag.js');
      const all = await getTags(tenant.id);
      const map = new Map(all.map((tag) => [tag.tag_id, tag]));
      suggestedTags = tagIds
        .map((id) => map.get(id))
        .filter(Boolean)
        .slice(0, 3);
    } catch {
      suggestedTags = [];
    } finally {
      suggestionsLoaded = true;
    }
  }

  function applySuggestion(tag) {
    if (!tag || newCaseTags.includes(tag.tag_id)) return;
    newCaseTags = [...newCaseTags, tag.tag_id];
  }

  // Hide suggestions the moment the user picks tags via the picker
  // OR starts typing a name.  The rationale: the user has expressed
  // intent; we should not keep pushing suggestions.
  let suggestionsDismissed = $state(false);
  $effect(() => {
    if (suggestionsDismissed) return;
    if (newCaseTags.length > 0 || newCaseTitle.trim().length > 0) {
      suggestionsDismissed = true;
    }
  });
  let visibleSuggestions = $derived(
    !suggestionsDismissed && suggestionsLoaded && suggestedTags.length > 0
  );

  // ─── Mode toggle ───────────────────────────────────────────────
  function setMode(next) {
    if (next === mode) return;
    mode = next;
    submitError = null;
  }

  // ─── Existing-case typeahead (3.7.1) ───────────────────────────
  async function onCaseSearchInput(event) {
    caseSearchInput = event.target.value;
    if (caseSearchTimer) clearTimeout(caseSearchTimer);
    const q = caseSearchInput.trim();
    if (!q) {
      caseSearchResults = [];
      caseSearchError = null;
      return;
    }
    caseSearchLoading = true;
    caseSearchTimer = setTimeout(async () => {
      try {
        caseSearchResults = await searchCases(q, 8);
        caseSearchError = null;
      } catch (err) {
        caseSearchError = err;
        caseSearchResults = [];
      } finally {
        caseSearchLoading = false;
      }
    }, 200);
  }

  function pickExistingCase(c) {
    selectedCaseId = c.id;
    caseSearchInput = c.title;
    caseSearchResults = [];
  }

  // ─── Submit ────────────────────────────────────────────────────
  async function handleSubmit(event) {
    event?.preventDefault();
    submitError = null;
    const text = (topic || '').trim();
    if (!text) {
      submitError = t?.caseSpace?.newDebate?.topicRequired ?? 'Please enter a topic.';
      return;
    }
    const tenant = get(currentTenant);
    const tenantId = tenant?.id;
    if (!tenantId) {
      submitError = t?.caseSpace?.newDebate?.noTenant ?? 'No tenant selected.';
      return;
    }

    submitting = true;
    try {
      let caseId;
      if (mode === 'new') {
        const title = newCaseTitle.trim();
        if (!title) {
          submitError = t?.caseSpace?.newDebate?.caseTitleRequired ?? 'Please give the new case a name.';
          submitting = false;
          return;
        }
        const created = await createCase(tenantId, {
          title,
          description: '',
          tags: newCaseTags,
        });
        caseId = created.id || created.case_id;
      } else {
        caseId = selectedCaseId || activeCaseId;
        if (!caseId) {
          submitError = t?.caseSpace?.newDebate?.caseRequired ?? 'Please pick a case.';
          submitting = false;
          return;
        }
      }

      const response = await createCaseDebate(tenantId, caseId, {
        case: { text },
        max_rounds: 3,
      });
      const debateId = response?.debate_id || response?.id;
      let started = null;
      if (debateId) {
        started = await startCaseDebate(tenantId, caseId, debateId);
      }
      addToast({
        type: 'success',
        message: t?.caseSpace?.newDebate?.created ?? 'Debate created.',
      });
      onCreated({ ...response, ...started }, { id: caseId });
      // Reset
      topic = '';
      newCaseTitle = '';
      newCaseTags = [];
      suggestionsDismissed = false;
    } catch (err) {
      submitError = err?.message || String(err);
    } finally {
      submitting = false;
    }
  }
</script>

<form
  class="new-debate-form"
  role="dialog"
  aria-labelledby="new-debate-title"
  onsubmit={handleSubmit}
>
  <h3 id="new-debate-title">
    {t?.caseSpace?.newDebate?.title ?? 'Start a new debate'}
  </h3>
  <p class="hint">
    {t?.caseSpace?.newDebate?.hint ??
      'Every debate lives in a case. Pick an existing case or create a new one on the fly.'}
  </p>

  <!-- ─── Mode toggle ─────────────────────────────────────────── -->
  <fieldset class="mode-toggle" aria-label="Case source">
    <legend class="sr-only">
      {t?.caseSpace?.newDebate?.modeLegend ?? 'Where should this debate live?'}
    </legend>
    <label class:active={mode === 'existing'}>
      <input
        type="radio"
        name="case-mode"
        value="existing"
        checked={mode === 'existing'}
        onchange={() => setMode('existing')}
      />
      <span>{t?.caseSpace?.newDebate?.existing ?? 'Existing case'}</span>
    </label>
    <label class:active={mode === 'new'}>
      <input
        type="radio"
        name="case-mode"
        value="new"
        checked={mode === 'new'}
        onchange={() => setMode('new')}
      />
      <span>{t?.caseSpace?.newDebate?.new ?? 'New case'}</span>
    </label>
  </fieldset>

  {#if mode === 'existing'}
    <!-- ─── Existing-case picker (3.7.1) ──────────────────────── -->
    <div class="field">
      <label for="new-debate-case">
        {t?.caseSpace?.newDebate?.caseLabel ?? 'Case'}
      </label>
      {#if activeCaseId && selectedCaseId === activeCaseId && !caseSearchInput}
        <!-- Fast path: the user has an active case, so the form is
             pre-filled and they can submit with one click (3.7.1). -->
        <div class="active-case-chip" data-testid="active-case-chip">
          <span class="active-case-label">
            {t?.caseSpace?.newDebate?.activeCase ?? 'Active case'}
          </span>
          <code class="active-case-id">{activeCaseId}</code>
          <button
            type="button"
            class="btn-link"
            onclick={() => {
              selectedCaseId = null;
              caseSearchInput = '';
            }}
          >
            {t?.caseSpace?.newDebate?.changeCase ?? 'Change…'}
          </button>
        </div>
      {:else}
        <input
          id="new-debate-case"
          type="text"
          autocomplete="off"
          value={caseSearchInput}
          oninput={onCaseSearchInput}
          placeholder={t?.caseSpace?.newDebate?.casePlaceholder ?? 'Search cases…'}
        />
        {#if caseSearchLoading}
          <small class="muted">
            {t?.caseSpace?.newDebate?.searching ?? 'Searching…'}
          </small>
        {:else if caseSearchResults.length > 0}
          <ul class="search-results" role="listbox">
            {#each caseSearchResults as c (c.id)}
              <li>
                <button
                  type="button"
                  class="result"
                  onclick={() => pickExistingCase(c)}
                >
                  <span class="result-title">{c.title}</span>
                  {#if c.tags?.length}
                    <span class="result-tags">
                      {#each c.tags.slice(0, 3) as tag}<span class="tag-dot">{tag}</span>{/each}
                    </span>
                  {/if}
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
    </div>
  {:else}
    <!-- ─── New-case inline creation (3.7.2) ───────────────────── -->
    <div class="field">
      <label for="new-debate-case-title">
        {t?.caseSpace?.newDebate?.newCaseTitle ?? 'New case name'}
      </label>
      <input
        id="new-debate-case-title"
        type="text"
        bind:value={newCaseTitle}
        placeholder={t?.caseSpace?.newDebate?.newCaseTitlePlaceholder ?? 'e.g. AI ethics research'}
      />
    </div>

    {#if visibleSuggestions}
      <div class="field">
        <span class="label-static">
          {t?.caseSpace?.newDebate?.suggestedTags ??
            `Suggested tags from the active case (${activeCaseId})`}
        </span>
        <div class="quick-tags" data-testid="suggested-tags">
          {#each suggestedTags as tag (tag.tag_id)}
            <button
              type="button"
              class="quick-tag"
              data-testid="suggested-tag"
              style="background-color: {tag.color || '#e5e7eb'}; color: {tag.color ? '#fff' : '#374151'}"
              onclick={() => applySuggestion(tag)}
            >
              + {tag.name}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <div class="field">
      <label>
        {t?.caseSpace?.newDebate?.newCaseTags ?? 'Tags'}
      </label>
      <TagPicker value={newCaseTags} onchange={(v) => (newCaseTags = v)} />
    </div>
  {/if}

  <!-- ─── Topic ──────────────────────────────────────────────── -->
  <div class="field">
    <label for="new-debate-topic">
      {t?.caseSpace?.newDebate?.topic ?? 'Topic / question'}
    </label>
    <textarea
      id="new-debate-topic"
      rows="3"
      bind:value={topic}
      placeholder={t?.caseSpace?.newDebate?.topicPlaceholder ?? 'What should the agents debate?'}
    ></textarea>
  </div>

  {#if submitError}
    <div class="banner banner-error" role="alert" data-testid="submit-error">
      {submitError}
    </div>
  {/if}

  <footer class="actions">
    <button
      type="button"
      class="btn"
      onclick={onCancel}
      disabled={submitting}
    >
      {t?.caseSpace?.newDebate?.cancel ?? 'Cancel'}
    </button>
    <button
      type="submit"
      class="btn btn-primary"
      disabled={submitting || !(topic || '').trim()}
      data-testid="submit-new-debate"
    >
      {#if submitting}
        {t?.caseSpace?.newDebate?.submitting ?? 'Starting…'}
      {:else}
        {t?.caseSpace?.newDebate?.submit ?? 'Start debate'}
      {/if}
    </button>
  </footer>
</form>

<style>
  .new-debate-form {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 8px;
    padding: 1.25rem;
    max-width: 560px;
    width: 100%;
  }
  .new-debate-form h3 {
    margin: 0;
    font-size: 1.2rem;
  }
  .hint {
    margin: 0;
    color: var(--color-text-muted, #666);
    font-size: 0.9rem;
  }
  .mode-toggle {
    display: flex;
    gap: 1rem;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    margin: 0;
  }
  .mode-toggle label {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    cursor: pointer;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
  }
  .mode-toggle label.active {
    background: var(--color-bg-muted, #f3f4f6);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .field label,
  .label-static {
    font-size: 0.85rem;
    color: var(--color-text-muted, #666);
  }
  .field input[type='text'],
  .field textarea {
    padding: 0.45rem 0.6rem;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 4px;
    font: inherit;
    background: var(--color-bg, #fff);
    color: var(--color-text, #111);
  }
  .field textarea {
    resize: vertical;
  }
  .muted {
    color: var(--color-text-muted, #666);
  }
  .active-case-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--color-bg-muted, #eef2ff);
    border: 1px solid var(--color-border, #c7d2fe);
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
  }
  .active-case-label {
    font-size: 0.75rem;
    color: var(--color-text-muted, #4f46e5);
  }
  .active-case-id {
    font-family: var(--font-mono, monospace);
    font-size: 0.85rem;
  }
  .btn-link {
    background: transparent;
    border: none;
    color: var(--color-primary, #3b82f6);
    cursor: pointer;
    font: inherit;
    padding: 0;
  }
  .search-results {
    list-style: none;
    padding: 0;
    margin: 0.25rem 0 0;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 4px;
    max-height: 12rem;
    overflow-y: auto;
  }
  .result {
    display: block;
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    padding: 0.45rem 0.6rem;
    cursor: pointer;
  }
  .result:hover {
    background: var(--color-bg-muted, #f3f4f6);
  }
  .result-title {
    font-weight: 500;
  }
  .result-tags {
    margin-left: 0.5rem;
    display: inline-flex;
    gap: 0.25rem;
  }
  .tag-dot {
    font-size: 0.7rem;
    background: var(--color-bg-muted, #e5e7eb);
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
  }
  .quick-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.25rem;
  }
  .quick-tag {
    border: none;
    border-radius: 999px;
    padding: 0.2rem 0.6rem;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .quick-tag:hover {
    opacity: 0.85;
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }
  .btn {
    padding: 0.45rem 0.85rem;
    border: 1px solid var(--color-border, #ddd);
    background: var(--color-bg-elevated, #fff);
    color: var(--color-text, #111);
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
  }
  .btn-primary {
    background: var(--color-primary, #3b82f6);
    color: #fff;
    border-color: transparent;
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .banner {
    padding: 0.6rem 0.8rem;
    border-radius: 4px;
    font-size: 0.9rem;
  }
  .banner-error {
    background: #fde8e8;
    border: 1px solid #f5c6cb;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
</style>
