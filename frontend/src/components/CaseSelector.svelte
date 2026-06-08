<script>
  import { onMount } from 'svelte';
  import { activeCase } from '../lib/stores.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { getCases } from '../lib/api.js';
  import { tStore } from '../lib/i18n/index.js';

  let { compact = false } = $props();

  let t = $derived($tStore);
  let tenantId = $derived($currentTenant?.id);

  let cases = $state([]);
  let isOpen = $state(false);
  let isLoading = $state(false);

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
    isOpen = false;
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
    onclick={(e) => { e.stopPropagation(); isOpen = !isOpen; if (isOpen && tenantId) loadCases(); }}
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
      {#if isLoading}
        <div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
          {t('common.loading')}
        </div>
      {:else if cases.length === 0}
        <div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
          {t('cases.noCases') || 'No cases available'}
        </div>
      {:else}
        {#each cases as caseObj}
          <button
            class="w-full text-left px-3 py-2 text-sm flex items-center justify-between
                   hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors
                   {$activeCase?.id === caseObj.id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}"
            onclick={() => selectCase(caseObj)}
            role="option"
            aria-selected={$activeCase?.id === caseObj.id}
          >
            <span class="truncate">
              {caseObj.title}
              {#if caseObj.tags && caseObj.tags.length > 0}
                <span class="text-xs text-gray-400 dark:text-gray-500 ml-1">
                  ({caseObj.tags.length})
                </span>
              {/if}
            </span>
            {#if $activeCase?.id === caseObj.id}
              <span class="text-blue-600 dark:text-blue-400 flex-shrink-0">✓</span>
            {/if}
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</div>
