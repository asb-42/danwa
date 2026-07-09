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
    eventsArray,
  } from '../lib/interactive/stores';

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
  <header class="px-4 py-3 border-b border-gray-200 bg-white flex items-center gap-4">
    <h1 class="text-lg font-semibold text-gray-800">Interactive Debate</h1>

    {#if $spaceStore.current}
      <span class="text-sm text-gray-500">
        | {$spaceStore.current.title}
      </span>
      <span class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
        {$spaceStore.current.event_count} Events
      </span>
    {/if}

    <div class="flex-1"></div>

    {#if !$spaceStore.current}
      <button
        class="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
        onclick={() => (showCreateModal = true)}
      >
        + Neuer Debattenraum
      </button>
    {:else}
      <button
        class="px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
        onclick={() => {
          spaceStore.setCurrent(null);
          spaceId = null;
          eventStore.clear();
        }}
      >
        ← Räume
      </button>
    {/if}
  </header>

  <!-- Main content -->
  <div class="flex-1 flex">
    {#if !spaceId}
      <!-- Space list -->
      <div class="flex-1 p-6 overflow-auto">
        {#if $spaceStore.spaces.length === 0}
          <div class="text-center py-12 text-gray-500">
            <div class="text-4xl mb-4">💬</div>
            <div class="text-lg mb-2">Keine Debattenräume vorhanden</div>
            <button
              class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              onclick={() => (showCreateModal = true)}
            >
              Ersten Raum erstellen
            </button>
          </div>
        {:else}
          <div class="grid gap-4 max-w-2xl">
            {#each $spaceStore.spaces as space}
              <button
                class="text-left p-4 border border-gray-200 rounded-xl hover:border-blue-300 hover:shadow-md transition-all"
                onclick={() => selectSpace(space)}
              >
                <div class="flex items-center justify-between">
                  <div>
                    <div class="font-medium text-gray-800">{space.title}</div>
                    {#if space.description}
                      <div class="text-sm text-gray-500 mt-1">
                        {space.description}
                      </div>
                    {/if}
                  </div>
                  <div class="text-right text-sm text-gray-400">
                    <div>{space.event_count} Events</div>
                    <div>{space.fork_count} Forks</div>
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

      <!-- Event list sidebar -->
      <aside class="w-80 border-l border-gray-200 bg-white overflow-auto">
        <div class="p-4">
          <h3 class="text-sm font-semibold text-gray-700 mb-3">Event-Verlauf</h3>
          {#if $eventsArray.length === 0}
            <div class="text-sm text-gray-400">Noch keine Events</div>
          {:else}
            <div class="space-y-2">
              {#each $eventsArray as event (event.event_id)}
                <div class="p-2 rounded-lg bg-gray-50 text-sm">
                  <div class="flex items-center gap-2">
                    <span class="text-xs">
                      {event.actor_type === 'user'
                        ? '👤'
                        : event.actor_type === 'agent'
                          ? '🤖'
                          : event.actor_type === 'a2a'
                            ? '🔗'
                            : '⚙️'}
                    </span>
                    <span class="font-medium text-gray-700">
                      {event.actor_id}
                    </span>
                    <span class="text-[10px] text-gray-400 ml-auto">
                      {new Date(event.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div class="text-gray-600 mt-1 line-clamp-2">
                    {typeof event.content === 'string'
                      ? event.content.slice(0, 100)
                      : '...'}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </aside>
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
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
      <h2 class="text-lg font-semibold mb-4">Neuer Debattenraum</h2>
      <input
        type="text"
        bind:value={spaceTitle}
        placeholder="Raumtitel..."
        class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-4"
        onkeydown={(e) => {
          if (e.key === 'Enter') handleCreateSpace();
        }}
      />
      <div class="flex justify-end gap-3">
        <button
          class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          onclick={() => (showCreateModal = false)}
        >
          Abbrechen
        </button>
        <button
          class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          onclick={handleCreateSpace}
          disabled={!spaceTitle.trim()}
        >
          Erstellen
        </button>
      </div>
    </div>
  </div>
{/if}
