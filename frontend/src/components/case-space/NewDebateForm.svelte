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
  import { tStore } from '../../lib/i18n/index.js';
  import { currentTenant } from '../../lib/stores/auth.svelte.js';
  import { addToast } from '../../lib/stores.js';
  import { searchCases } from '../../lib/api/workspace.js';
  import { createCase, getCase, createCaseDebate, startCaseDebate } from '../../lib/api/case.js';
  import TagPicker from '../TagPicker.svelte';

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
      const { getTags } = await import('../../lib/api/tag.js');
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

<div
  class="flex flex-col gap-3 p-5 border rounded-lg max-w-2xl w-full
         bg-white dark:bg-gray-800
         border-gray-200 dark:border-gray-700
         text-gray-900 dark:text-gray-100"
  role="dialog"
  aria-modal="true"
  aria-labelledby="new-debate-title"
  tabindex="-1"
>
  <h3 id="new-debate-title" class="m-0 text-lg font-semibold">
    {t?.caseSpace?.newDebate?.title ?? 'Start a new debate'}
  </h3>
  <p class="hint m-0 text-sm text-gray-600 dark:text-gray-400">
    {t?.caseSpace?.newDebate?.hint ??
      'Every debate lives in a case. Pick an existing case or create a new one on the fly.'}
  </p>

  <!-- Mode toggle -->
  <fieldset
    class="flex gap-4 p-2 border rounded-md
           border-gray-200 dark:border-gray-700"
  >
    <legend class="sr-only">
      {t?.caseSpace?.newDebate?.modeLegend ?? 'Where should this debate live?'}
    </legend>
    <label
      class="inline-flex items-center gap-1.5 cursor-pointer p-1 rounded
             {mode === 'existing' ? 'bg-gray-100 dark:bg-gray-700' : ''}"
    >
      <input
        type="radio"
        name="case-mode"
        value="existing"
        checked={mode === 'existing'}
        onchange={() => setMode('existing')}
        class="text-blue-600 focus:ring-blue-500"
      />
      <span>{t?.caseSpace?.newDebate?.existing ?? 'Existing case'}</span>
    </label>
    <label
      class="inline-flex items-center gap-1.5 cursor-pointer p-1 rounded
             {mode === 'new' ? 'bg-gray-100 dark:bg-gray-700' : ''}"
    >
      <input
        type="radio"
        name="case-mode"
        value="new"
        checked={mode === 'new'}
        onchange={() => setMode('new')}
        class="text-blue-600 focus:ring-blue-500"
      />
      <span>{t?.caseSpace?.newDebate?.new ?? 'New case'}</span>
    </label>
  </fieldset>

  {#if mode === 'existing'}
    <div class="flex flex-col gap-1">
      <label for="new-debate-case" class="text-sm text-gray-700 dark:text-gray-300">
        {t?.caseSpace?.newDebate?.caseLabel ?? 'Case'}
      </label>
      {#if activeCaseId && selectedCaseId === activeCaseId && !caseSearchInput}
        <div
          class="inline-flex items-center gap-2 p-2 border rounded
                 bg-indigo-50 dark:bg-indigo-900/30
                 border-indigo-200 dark:border-indigo-700"
          data-testid="active-case-chip"
        >
          <span class="text-xs text-indigo-600 dark:text-indigo-300">
            {t?.caseSpace?.newDebate?.activeCase ?? 'Active case'}
          </span>
          <code class="font-mono text-sm text-gray-900 dark:text-gray-100">
            {activeCaseId}
          </code>
          <button
            type="button"
            class="text-blue-600 dark:text-blue-400 hover:underline
                   focus:outline-none focus:ring-2 focus:ring-blue-500 bg-transparent border-0 p-0"
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
          class="flex-1 w-full px-2 py-1.5 border rounded text-sm
                 border-gray-300 dark:border-gray-600
                 bg-white dark:bg-gray-700
                 text-gray-900 dark:text-gray-100
                 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {#if caseSearchLoading}
          <small class="text-xs text-gray-500 dark:text-gray-400">
            {t?.caseSpace?.newDebate?.searching ?? 'Searching…'}
          </small>
        {:else if caseSearchResults.length > 0}
          <ul
            class="list-none p-0 mt-1 border rounded
                   border-gray-200 dark:border-gray-700
                   bg-white dark:bg-gray-700
                   max-h-48 overflow-y-auto"
            role="listbox"
          >
            {#each caseSearchResults as c (c.id)}
              <li>
                <button
                  type="button"
                  class="block w-full text-left px-3 py-2
                         hover:bg-gray-100 dark:hover:bg-gray-600
                         text-gray-900 dark:text-gray-100 bg-transparent border-0"
                  onclick={() => pickExistingCase(c)}
                >
                  <span class="font-medium">{c.title}</span>
                  {#if c.tags?.length}
                    <span class="ml-2 inline-flex gap-1">
                      {#each c.tags.slice(0, 3) as tag}
                        <span
                          class="text-[0.7rem] px-1.5 py-0.5 rounded
                                 bg-gray-100 dark:bg-gray-600
                                 text-gray-600 dark:text-gray-300"
                        >{tag}</span>
                      {/each}
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
    <div class="flex flex-col gap-1">
      <label for="new-debate-case-title" class="text-sm text-gray-700 dark:text-gray-300">
        {t?.caseSpace?.newDebate?.newCaseTitle ?? 'New case name'}
      </label>
      <input
        id="new-debate-case-title"
        type="text"
        bind:value={newCaseTitle}
        placeholder={t?.caseSpace?.newDebate?.newCaseTitlePlaceholder ?? 'e.g. AI ethics research'}
        class="w-full px-2 py-1.5 border rounded text-sm
               border-gray-300 dark:border-gray-600
               bg-white dark:bg-gray-700
               text-gray-900 dark:text-gray-100
               focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>

    {#if visibleSuggestions}
      <div class="flex flex-col gap-1">
        <span class="text-sm text-gray-700 dark:text-gray-300">
          {t?.caseSpace?.newDebate?.suggestedTags ??
            `Suggested tags from the active case (${activeCaseId})`}
        </span>
        <div class="flex flex-wrap gap-1.5" data-testid="suggested-tags">
          {#each suggestedTags as tag (tag.tag_id)}
            <button
              type="button"
              data-testid="suggested-tag"
              class="text-xs font-medium border-0 rounded-full px-2.5 py-0.5
                     hover:opacity-80
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     transition-opacity"
              style="background-color: {tag.color || '#e5e7eb'};
                     color: {tag.color ? '#fff' : '#374151'};"
              onclick={() => applySuggestion(tag)}
            >
              + {tag.name}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <div class="flex flex-col gap-1">
      <label class="text-sm text-gray-700 dark:text-gray-300">
        {t?.caseSpace?.newDebate?.newCaseTags ?? 'Tags'}
      </label>
      <TagPicker value={newCaseTags} caseId={activeCaseId} onchange={(v) => (newCaseTags = v)} />
    </div>
  {/if}

  <div class="flex flex-col gap-1">
    <label for="new-debate-topic" class="text-sm text-gray-700 dark:text-gray-300">
      {t?.caseSpace?.newDebate?.topic ?? 'Topic / question'}
    </label>
    <textarea
      id="new-debate-topic"
      rows="3"
      bind:value={topic}
      placeholder={t?.caseSpace?.newDebate?.topicPlaceholder ?? 'What should the agents debate?'}
      class="w-full px-2 py-1.5 border rounded text-sm resize-y
             border-gray-300 dark:border-gray-600
             bg-white dark:bg-gray-700
             text-gray-900 dark:text-gray-100
             focus:outline-none focus:ring-2 focus:ring-blue-500"
    ></textarea>
  </div>

  {#if submitError}
    <div
      class="banner p-3 rounded border text-sm
             bg-red-50 dark:bg-red-900/20
             border-red-200 dark:border-red-700
             text-red-900 dark:text-red-100"
      role="alert"
      data-testid="submit-error"
    >
      {submitError}
    </div>
  {/if}

  <form class="submit-form" onsubmit={handleSubmit}>
    <div class="flex justify-end gap-2 mt-1">
      <button
        type="button"
        class="px-4 py-1.5 rounded text-sm
               bg-gray-100 dark:bg-gray-700
               text-gray-700 dark:text-gray-200
               hover:bg-gray-200 dark:hover:bg-gray-600
               focus:outline-none focus:ring-2 focus:ring-blue-500"
        onclick={onCancel}
        disabled={submitting}
      >
        {t?.caseSpace?.newDebate?.cancel ?? 'Cancel'}
      </button>
      <button
        type="submit"
        class="px-4 py-1.5 rounded text-sm font-medium
               bg-blue-600 hover:bg-blue-700
               text-white
               focus:outline-none focus:ring-2 focus:ring-blue-500
               disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={submitting || !(topic || '').trim()}
        data-testid="submit-new-debate"
      >
        {#if submitting}
          {t?.caseSpace?.newDebate?.submitting ?? 'Starting…'}
        {:else}
          {t?.caseSpace?.newDebate?.submit ?? 'Start debate'}
        {/if}
      </button>
    </div>
  </form>
</div>
<style>
  /* All visual styling is inline Tailwind with paired dark:
     variants so the modal honours whichever theme the rest of
     the app is running.  See the <div> in this file. */
</style>
