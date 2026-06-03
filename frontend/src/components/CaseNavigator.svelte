<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { activeCase, addToast } from '../lib/stores.js';
  import { getCases, createCase } from '../lib/api/case.js';

  let { navigate } = $props();

  let t = $derived($tStore);

  let cases = $state([]);
  let isOpen = $state(false);
  let isLoading = $state(false);
  let showCreate = $state(false);
  let newTitle = $state('');
  let newDescription = $state('');
  let isCreating = $state(false);

  onMount(() => {
    loadCases();
  });

  $effect(() => {
    if ($currentTenant) {
      loadCases();
    }
  });

  async function loadCases() {
    if (!$currentTenant) return;
    isLoading = true;
    try {
      cases = await getCases($currentTenant.id);
    } catch (err) {
      console.warn('Could not load cases:', err);
    } finally {
      isLoading = false;
    }
  }

  function selectCase(c) {
    activeCase.set({ id: c.id, title: c.title });
    isOpen = false;
  }

  async function handleCreate() {
    if (import.meta.env.DEV) console.debug('[CaseNavigator] handleCreate:', { newTitle: newTitle.trim(), tenant: $currentTenant, hasTenant: !!$currentTenant });
    if (!newTitle.trim() || !$currentTenant) return;
    isCreating = true;
    try {
      const c = await createCase($currentTenant.id, { title: newTitle.trim(), description: newDescription.trim() });
      if (import.meta.env.DEV) console.debug('[CaseNavigator] createCase response:', c);
      cases = [...cases, c];
      activeCase.set({ id: c.id, title: c.title });
      newTitle = '';
      newDescription = '';
      showCreate = false;
    } catch (err) {
      addToast({ type: 'error', message: t('cases.saveFailed', { error: err.message }) });
    } finally {
      isCreating = false;
    }
  }

  function handleClickOutside(event) {
    if (!event.target.closest('.case-navigator')) {
      isOpen = false;
      showCreate = false;
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="case-navigator relative">
  <button
    class="w-full flex items-center gap-1.5 px-2 py-1.5 text-xs rounded-md
           border border-gray-200 dark:border-gray-600
           bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300
           hover:border-blue-400 dark:hover:border-blue-500
           transition-colors"
    onclick={(e) => { e.stopPropagation(); isOpen = !isOpen; }}
    aria-haspopup="listbox"
    aria-expanded={isOpen}
  >
    <span class="text-xs" aria-hidden="true">📁</span>
    {#if $activeCase}
      <span class="truncate max-w-[140px]">{$activeCase.title}</span>
    {:else}
      <span class="text-gray-400">{t('cases.noActiveCase')}</span>
    {/if}
    <svg class="w-3 h-3 text-gray-400 flex-shrink-0 ml-auto transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  {#if isOpen}
    <div
      class="absolute left-0 right-0 z-50 mt-1 bg-white dark:bg-gray-800 rounded-lg shadow-lg
             border border-gray-200 dark:border-gray-700 max-h-64 overflow-y-auto"
      role="listbox"
    >
      {#if isLoading}
        <div class="px-3 py-2 text-sm text-gray-500">{t('common.loading')}</div>
      {:else if cases.length === 0}
        <div class="px-3 py-2 text-sm text-gray-500">{t('cases.noCases')}</div>
      {:else}
        {#each cases as c}
          <button
            class="w-full text-left px-3 py-2 text-sm flex items-center justify-between
                   hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors
                   {$activeCase?.id === c.id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700' : 'text-gray-700 dark:text-gray-300'}"
            onclick={() => selectCase(c)}
            role="option"
            aria-selected={$activeCase?.id === c.id}
          >
            <span class="truncate">{c.title}</span>
            {#if $activeCase?.id === c.id}
              <span class="text-blue-600 flex-shrink-0">✓</span>
            {/if}
          </button>
        {/each}
      {/if}
      <div class="border-t border-gray-200 dark:border-gray-700">
        <button
          class="w-full text-left px-3 py-2 text-sm text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
          class:hidden={showCreate}
          onclick={(e) => { e.stopPropagation(); showCreate = true; }}
        >
          + {t('cases.create')}
        </button>
        <div class:hidden={!showCreate} class="px-3 py-2 space-y-2">
          <input
            type="text"
            bind:value={newTitle}
            placeholder={t('cases.title_label')}
            class="w-full px-2 py-1 text-sm border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
            onkeydown={(e) => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') showCreate = false; e.stopPropagation(); }}
          />
          <input
            type="text"
            bind:value={newDescription}
            placeholder={t('cases.description')}
            class="w-full px-2 py-1 text-sm border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
          />
          <div class="flex gap-1">
            <button
              class="flex-1 px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:hover:bg-blue-600 disabled:opacity-50"
              onclick={handleCreate}
              disabled={isCreating || !newTitle.trim()}
            >
              {isCreating ? t('common.loading') : t('common.save')}
            </button>
            <button
              class="px-2 py-1 text-xs border rounded hover:bg-gray-100 dark:hover:bg-gray-700 dark:border-gray-600"
              onclick={() => { showCreate = false; newTitle = ''; newDescription = ''; }}
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .hidden { display: none; }
</style>
