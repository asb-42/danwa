<script>
  /**
   * InteractiveDebateView — main view for the interactive debate mode.
   *
   * Combines the debate graph, event list, and controls.
   * Supports DMS/RAG integration via case_id linkage.
   */
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import DebateGraph from '../components/interactive/DebateGraph.svelte';
  import {
    spaceStore,
    eventStore,
  } from '../lib/interactive/stores';
  import { tStore } from '../lib/i18n/index.js';
  import { workspaceStore } from '../lib/stores/workspaceStore.svelte.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';

  let t = $derived($tStore);
  let spaceId = $state(null);
  let spaceTitle = $state('');
  let spaceDescription = $state('');
  let showCreateModal = $state(false);
  let filterByCase = $state(true);

  onMount(async () => {
    await spaceStore.loadSpaces();
  });

  function selectSpace(space) {
    spaceStore.setCurrent(space);
    spaceId = space.space_id;
    spaceTitle = space.title;
  }

  async function handleCreateSpace() {
    if (!spaceTitle.trim()) return;
    const caseId = filterByCase ? workspaceStore.activeCaseId : null;
    const tenant = get(currentTenant);
    const tenantId = tenant?.id;
    const space = await spaceStore.create(
      spaceTitle.trim(),
      spaceDescription.trim() || undefined,
      caseId,
      tenantId
    );
    spaceId = space.space_id;
    showCreateModal = false;
    spaceTitle = '';
    spaceDescription = '';
  }

  function getCaseLabel(space) {
    if (space.case_id) {
      return space.case_id.slice(0, 8) + '…';
    }
    return null;
  }

  let activeCaseId = $derived(workspaceStore.activeCaseId);
  let filteredSpaces = $derived(
    filterByCase && activeCaseId
      ? $spaceStore.spaces.filter(s => s.case_id === activeCaseId)
      : $spaceStore.spaces
  );
</script>

<div class="interactive-view h-full flex flex-col">
  <!-- Header -->
  <header class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex items-center gap-4">
    <h1 class="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('interactive.title')}</h1>

    {#if $spaceStore.current}
      <span class="text-sm text-gray-500 dark:text-gray-400">
        | {$spaceStore.current.title}
      </span>
      {#if $spaceStore.current.case_id}
        <span class="text-xs px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300" title="Linked to case {$spaceStore.current.case_id}">
          📄 {getCaseLabel($spaceStore.current)}
        </span>
      {/if}
      <span class="text-xs px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300">
        {$spaceStore.current.event_count} {t('interactive.events')}
      </span>
    {/if}

    <div class="flex-1"></div>

    {#if !$spaceStore.current}
      <button
        class="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
        onclick={() => (showCreateModal = true)}
      >
        {t('interactive.newRoom')}
      </button>
    {:else}
      <button
        class="px-3 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        onclick={() => {
          spaceStore.setCurrent(null);
          spaceId = null;
          eventStore.clear();
        }}
      >
        {t('interactive.backToRooms')}
      </button>
    {/if}
  </header>

  <!-- Main content -->
  <div class="flex-1 flex">
    {#if !spaceId}
      <!-- Space list -->
      <div class="flex-1 p-6 overflow-auto">
        <!-- Filter controls -->
        {#if $spaceStore.spaces.length > 0}
          <div class="flex items-center gap-4 mb-4">
            <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <input
                type="checkbox"
                bind:checked={filterByCase}
                class="rounded border-gray-300 dark:border-gray-600"
              />
              {t('interactive.filterByCase')}
            </label>
            {#if filterByCase && activeCaseId}
              <span class="text-xs text-gray-500 dark:text-gray-400">
                {t('interactive.showingForCase')} {activeCaseId.slice(0, 8)}…
              </span>
            {/if}
          </div>
        {/if}

        {#if filteredSpaces.length === 0}
          <div class="text-center py-12 text-gray-500 dark:text-gray-400">
            <div class="text-4xl mb-4">💬</div>
            <div class="text-lg mb-2">{t('interactive.noSpaces')}</div>
            <button
              class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              onclick={() => (showCreateModal = true)}
            >
              {t('interactive.createFirst')}
            </button>
          </div>
        {:else}
          <div class="grid gap-4 max-w-2xl">
            {#each filteredSpaces as space}
              <button
                class="text-left p-4 border border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md transition-all"
                onclick={() => selectSpace(space)}
              >
                <div class="flex items-center justify-between">
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <span class="font-medium text-gray-800 dark:text-gray-100">{space.title}</span>
                      {#if space.case_id}
                        <span class="text-xs px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300">
                          📄 Case
                        </span>
                      {/if}
                    </div>
                    {#if space.description}
                      <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {space.description}
                      </div>
                    {/if}
                  </div>
                  <div class="text-right text-sm text-gray-400 dark:text-gray-500 ml-4">
                    <div>{space.event_count} {t('interactive.events')}</div>
                    <div>{space.fork_count} {t('interactive.forks')}</div>
                  </div>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <!-- Debate graph -->
      <div class="flex-1">
        <DebateGraph {spaceId} />
      </div>
    {/if}
  </div>
</div>

<!-- Create Space Modal -->
{#if showCreateModal}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    onclick={(e) => {
      if (e.target === e.currentTarget) showCreateModal = false;
    }}
  >
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
      <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-100">{t('interactive.newRoom')}</h2>

      <!-- Case context indicator -->
      {#if filterByCase && activeCaseId}
        <div class="mb-4 p-3 bg-purple-50 dark:bg-purple-900/30 rounded-lg border border-purple-200 dark:border-purple-700">
          <div class="flex items-center gap-2 text-sm">
            <span class="text-purple-600 dark:text-purple-400">📄</span>
            <span class="text-purple-700 dark:text-purple-300 font-medium">{t('interactive.linkedToCase')}</span>
          </div>
          <div class="text-xs text-purple-600 dark:text-purple-400 mt-1 font-mono">
            {activeCaseId}
          </div>
          <div class="text-xs text-purple-500 dark:text-purple-400 mt-1">
            {t('interactive.caseDocumentsHint')}
          </div>
        </div>
      {/if}

      <!-- Title input -->
      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {t('interactive.roomTitle')}
      </label>
      <input
        type="text"
        bind:value={spaceTitle}
        placeholder={t('interactive.roomTitlePlaceholder')}
        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm mb-3 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100"
        onkeydown={(e) => {
          if (e.key === 'Enter') handleCreateSpace();
        }}
      />

      <!-- Description input -->
      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {t('interactive.description')} <span class="text-gray-400">({t('common.optional')})</span>
      </label>
      <textarea
        bind:value={spaceDescription}
        placeholder={t('interactive.descriptionPlaceholder')}
        rows="2"
        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm mb-4 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 resize-none"
      ></textarea>

      <!-- Link to case checkbox -->
      <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mb-4">
        <input
          type="checkbox"
          bind:checked={filterByCase}
          disabled={!activeCaseId}
          class="rounded border-gray-300 dark:border-gray-600"
        />
        {t('interactive.linkToCurrentCase')}
      </label>

      <div class="flex justify-end gap-3">
        <button
          class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          onclick={() => (showCreateModal = false)}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          onclick={handleCreateSpace}
          disabled={!spaceTitle.trim()}
        >
          {t('common.create')}
        </button>
      </div>
    </div>
  </div>
{/if}
