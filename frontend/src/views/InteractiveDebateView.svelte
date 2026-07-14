<script>
  /**
   * InteractiveDebateView — main view for the interactive debate mode.
   *
   * Combines the debate graph, event list, and controls.
   */
  import { onMount } from 'svelte';
  import DebateGraph from '../components/interactive/DebateGraph.svelte';
  import {
    spaceStore,
    eventStore,
  } from '../lib/interactive/stores';
  import { tStore } from '../lib/i18n/index.js';

  let t = $derived($tStore);
  let spaceId = $state(null);
  let spaceTitle = $state('');
  let showCreateModal = $state(false);

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
    const space = await spaceStore.create(spaceTitle.trim());
    spaceId = space.space_id;
    showCreateModal = false;
  }
</script>

<div class="interactive-view h-full flex flex-col">
  <!-- Header -->
  <header class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex items-center gap-4">
    <h1 class="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('interactive.title')}</h1>

    {#if $spaceStore.current}
      <span class="text-sm text-gray-500 dark:text-gray-400">
        | {$spaceStore.current.title}
      </span>
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
        {#if $spaceStore.spaces.length === 0}
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
            {#each $spaceStore.spaces as space}
              <button
                class="text-left p-4 border border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md transition-all"
                onclick={() => selectSpace(space)}
              >
                <div class="flex items-center justify-between">
                  <div>
                    <div class="font-medium text-gray-800 dark:text-gray-100">{space.title}</div>
                    {#if space.description}
                      <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {space.description}
                      </div>
                    {/if}
                  </div>
                  <div class="text-right text-sm text-gray-400 dark:text-gray-500">
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
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
      <h2 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-100">{t('interactive.newRoom')}</h2>
      <input
        type="text"
        bind:value={spaceTitle}
        placeholder={t('interactive.newRoom')}
        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm mb-4 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100"
        onkeydown={(e) => {
          if (e.key === 'Enter') handleCreateSpace();
        }}
      />
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
