<script>
  /**
   * DebateGraph — SvelteFlow-based interactive debate tree.
   *
   * Renders events as nodes, parent_id relationships as edges.
   * Supports real-time updates via SSE, forking via [+] button.
   */
  import { onMount, onDestroy } from 'svelte';
  import {
    SvelteFlow,
    Background,
    Controls,
    MiniMap,
    useSvelteFlow,
  } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';

  import DebateEventNode from './DebateEventNode.svelte';
  import ForkModal from './ForkModal.svelte';
  import {
    eventStore,
    eventsArray,
    debateEdges,
    forkModalStore,
    spaceStore,
  } from '../../lib/interactive/stores';

  let { spaceId = null } = $props();

  const nodeTypes = { debateEvent: DebateEventNode };

  let nodes = $state([]);
  let edges = $state([]);

  // Subscribe to stores
  $effect(() => {
    const unsub1 = eventsArray.subscribe((events) => {
      nodes = events.map((evt, idx) => ({
        id: evt.event_id,
        type: 'debateEvent',
        position: calculatePosition(evt, idx),
        data: evt,
      }));
    });

    const unsub2 = debateEdges.subscribe((eds) => {
      edges = eds;
    });

    return () => {
      unsub1();
      unsub2();
    };
  });

  // Load tree and start streaming
  $effect(() => {
    if (spaceId) {
      eventStore.loadTree(spaceId);
      eventStore.startStreaming(spaceId);
    }

    return () => {
      eventStore.stopStreaming();
    };
  });

  /**
   * Calculate node position based on parent relationships.
   * Uses a simple tree layout algorithm.
   */
  function calculatePosition(event, index) {
    if (!event.parent_id) {
      return { x: 250, y: 50 };
    }

    // Find parent node
    const parentIdx = nodes.findIndex((n) => n.id === event.parent_id);
    if (parentIdx >= 0) {
      const parent = nodes[parentIdx];
      // Count siblings (events with same parent)
      const siblings = nodes.filter(
        (n) => n.data?.parent_id === event.parent_id
      );
      const siblingIndex = siblings.length;

      return {
        x: parent.position.x + (siblingIndex - 1) * 200,
        y: parent.position.y + 150,
      };
    }

    // Fallback: stack vertically
    return { x: 250, y: 50 + index * 150 };
  }

  function handleFork(event) {
    forkModalStore.open(event);
  }

  function handleNodeClick(event) {
    // Node selection logic (if needed)
  }
</script>

<div class="debate-graph-container h-full w-full">
  {#if $spaceStore.loading || $eventStore.loading}
    <div class="flex items-center justify-center h-full">
      <div class="text-gray-500">Lade Debattenbaum...</div>
    </div>
  {:else if nodes.length === 0}
    <div class="flex flex-col items-center justify-center h-full text-gray-500">
      <div class="text-4xl mb-4">🌳</div>
      <div class="text-lg font-medium mb-2">Noch keine Events</div>
      <div class="text-sm">Klicke auf [+] um die Debatte zu starten.</div>
    </div>
  {:else}
    <SvelteFlow
      {nodes}
      {edges}
      {nodeTypes}
      fitView
      onnodeclick={handleNodeClick}
      class="debate-flow"
    >
      <Background gap={20} />
      <Controls />
      <MiniMap
        nodeColor={(n) => {
          if (n.data?.actor_type === 'user') return '#22c55e';
          if (n.data?.actor_type === 'agent') return '#a855f7';
          if (n.data?.actor_type === 'a2a') return '#f97316';
          return '#6b7280';
        }}
      />
    </SvelteFlow>
  {/if}
</div>

<!-- Fork Modal -->
{#if $forkModalStore.open}
  <ForkModal
    targetEvent={$forkModalStore.targetEvent}
    {spaceId}
    onclose={() => forkModalStore.close()}
  />
{/if}

<style>
  .debate-graph-container :global(.debate-flow) {
    background: #f8fafc;
  }
</style>
