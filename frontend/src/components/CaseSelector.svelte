<script>
  import { onMount, tick } from 'svelte';
  import { activeCase } from '../lib/stores.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { getCases } from '../lib/api.js';
  import { tStore } from '../lib/i18n/index.js';
  import { searchCases, isCaseSpaceDisabled } from '../lib/api/workspace.js';
  import {
    workspaceStore,
    setActiveCase,
  } from '../lib/stores/workspaceStore.svelte.js';

  let { compact = false } = $props();

  let t = $derived($tStore);
  let tenantId = $derived($currentTenant?.id);

  let cases = $state([]);
  let isOpen = $state(false);
  let isLoading = $state(false);

  // Typeahead additions (Case-Space Phase 1.8)
  let searchQuery = $state('');
  let searchResults = $state([]);
  let isSearching = $state(false);
  let searchInputEl = $state(null);
  let typeaheadEnabled = $state(false);  // true after first user keystroke
  let typeaheadTimer = null;

  // ─── Derived state ───────────────────────────────────────────────
  // When the user has typed, show typeahead results; otherwise show
  // the full cases list (back-compat with the original behaviour).
  let displayedCases = $derived(
    typeaheadEnabled && searchQuery.trim()
      ? searchResults
      : cases,
  );

  // Reload cases when tenant changes
  $effect(() => {
    if (tenantId) {
      loadCases();
    }
  });

  onMount(async () => {
    if (tenantId) {
      await loadCases();
    }
  });

  async function loadCases() {
    if (!tenantId) return;
    isLoading = true;
    try {
      cases = await getCases(tenantId);
      // Auto-select first case if nothing is selected or selection is stale
      if ((!$activeCase || $activeCase.tenant_id !== tenantId) && cases.length > 0) {
        activeCase.set({ id: cases[0].id, title: cases[0].title, tenant_id: tenantId });
      }
      // Validate that active case still exists
      if ($activeCase && $activeCase.tenant_id === tenantId && !cases.find(c => c.id === $activeCase.id)) {
        activeCase.set(cases.length > 0
          ? { id: cases[0].id, title: cases[0].title, tenant_id: tenantId }
          : null);
      }
    } catch (err) {
      if (import.meta.env.DEV) console.warn('Could not load cases:', err);
    } finally {
      isLoading = false;
    }
  }

  function selectCase(caseObj) {
    activeCase.set({ id: caseObj.id, title: caseObj.title, tenant_id: tenantId });
    // Mirror to the new Case-Space workspace store so the Workspace
    // view shows the same selection.
    setActiveCase(caseObj.id);
    isOpen = false;
    typeaheadEnabled = false;
    searchQuery = '';
  }

  // ─── Typeahead handlers ─────────────────────────────────────────
  async function handleSearchInput(event) {
    searchQuery = event.target.value;
    typeaheadEnabled = true;

    if (typeaheadTimer) clearTimeout(typeaheadTimer);
    const needle = searchQuery.trim();
    if (!needle) {
      searchResults = [];
      isSearching = false;
      return;
    }
    isSearching = true;
    typeaheadTimer = setTimeout(async () => {
      try {
        const hits = await searchCases(needle, 10);
        // Only commit if the query hasn't moved on
        if (searchQuery === event.target.value) {
          searchResults = hits;
        }
      } catch (err) {
        // 404 / feature-off / transient failure → keep previous list
        if (isCaseSpaceDisabled(err)) {
          // Feature flag is off — disable typeahead and fall back to full list
          typeaheadEnabled = false;
          searchResults = [];
        }
        if (import.meta.env.DEV) {
          console.debug('[CaseSelector] typeahead failed:', err?.message ?? err);
        }
      } finally {
        if (searchQuery === event.target.value) {
          isSearching = false;
        }
      }
    }, 200);
  }

  function handleSearchKeydown(event) {
    if (event.key === 'Escape') {
      typeaheadEnabled = false;
      searchQuery = '';
      searchResults = [];
      isOpen = false;
      searchInputEl?.blur();
    } else if (event.key === 'Enter') {
      // Enter on the first hit selects it
      const first = searchResults[0];
      if (first) {
        event.preventDefault();
        selectCase({
          id: first.case_id,
          title: first.title,
          tenant_id: first.tenant_id,
        });
      }
    }
  }

  // When the dropdown opens, focus the search input for immediate typing
  async function handleOpenDropdown() {
    isOpen = true;
    if (tenantId) await loadCases();
    await tick();
    searchInputEl?.focus();
  }

  function handleClickOutside(event) {
    if (!event.target.closest('.case-selector')) {
      isOpen = false;
    }
  }

  export function refresh() {
    return loadCases();
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="case-selector relative" class:w-full={!compact}>
  <button
    class="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg
           border border-gray-200 dark:border-gray-600
           bg-white dark:bg-gray-700 text-gray-800 dark:text-white
           hover:border-blue-400 dark:hover:border-blue-500
           focus:ring-2 focus:ring-blue-500 focus:border-blue-500
           transition-colors"
    onclick={(e) => { e.stopPropagation(); if (isOpen) { isOpen = false; } else { handleOpenDropdown(); } }}
    aria-haspopup="listbox"
    aria-expanded={isOpen}
  >
    <span class="flex items-center gap-2 truncate">
      <span class="text-base" aria-hidden="true">📋</span>
      {#if $activeCase}
        <span class="truncate">{$activeCase.title}</span>
      {:else}
        <span class="text-gray-400 dark:text-gray-500">{t('cases.noActiveCase') || 'No case selected'}</span>
      {/if}
    </span>
    <svg class="w-4 h-4 text-gray-400 flex-shrink-0 transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  {#if isOpen}
    <div
      class="absolute z-50 mt-1 w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg
             border border-gray-200 dark:border-gray-700 max-h-64 overflow-y-auto"
      role="listbox"
    >
      <!-- Typeahead search input (Case-Space Phase 1.8) -->
      <div class="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700 px-2 py-1.5">
        <input
          bind:this={searchInputEl}
          type="text"
          class="w-full px-2 py-1 text-sm rounded border border-gray-200 dark:border-gray-600
                 bg-white dark:bg-gray-700 text-gray-800 dark:text-white
                 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none"
          placeholder={t('cases.searchPlaceholder') || 'Search cases…'}
          value={searchQuery}
          oninput={handleSearchInput}
          onkeydown={handleSearchKeydown}
          aria-label={t('cases.searchAriaLabel') || 'Search cases'}
          autocomplete="off"
        />
        {#if isSearching}
          <div class="text-xs text-gray-400 mt-0.5 px-1">{t('common.loading')}</div>
        {/if}
      </div>

      {#if isLoading}
        <div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
          {t('common.loading')}
        </div>
      {:else if displayedCases.length === 0}
        <div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
          {typeaheadEnabled && searchQuery.trim()
            ? (t('cases.noSearchResults') || 'No matching cases')
            : (t('cases.noCases') || 'No cases available')}
        </div>
      {:else}
        {#each displayedCases as caseObj}
          {@const caseId = caseObj.id ?? caseObj.case_id}
          {@const caseTitle = caseObj.title}
          {@const caseTags = caseObj.tags || []}
          <button
            class="w-full text-left px-3 py-2 text-sm flex items-center justify-between
                   hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors
                   {$activeCase?.id === caseId ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}"
            onclick={() => selectCase({ id: caseId, title: caseTitle, tenant_id: tenantId })}
            role="option"
            aria-selected={$activeCase?.id === caseId}
          >
            <span class="truncate">
              {caseTitle}
              {#if caseTags.length > 0}
                <span class="text-xs text-gray-400 dark:text-gray-500 ml-1">
                  ({caseTags.length})
                </span>
              {/if}
            </span>
            {#if $activeCase?.id === caseId}
              <span class="text-blue-600 dark:text-blue-400 flex-shrink-0">✓</span>
            {/if}
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</div>
