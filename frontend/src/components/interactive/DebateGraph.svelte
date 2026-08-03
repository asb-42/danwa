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
  import EventDetailPanel from './EventDetailPanel.svelte';
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
  let selectedEventId = $state(null);

  // Subscribe to stores
  $effect(() => {
    const unsub1 = eventsArray.subscribe((events) => {
      // Build position map from existing events first
      const posMap = new Map();
      for (const evt of events) {
        if (!evt.parent_id) {
          posMap.set(evt.event_id, { x: 250, y: 50 });
        }
      }
      // Second pass: position children relative to parents
      const newNodes = events.map((evt, idx) => {
        if (!evt.parent_id) {
          return {
            id: evt.event_id,
            type: 'debateEvent',
            position: posMap.get(evt.event_id),
            data: evt,
          };
        }
        const parentPos = posMap.get(evt.parent_id);
        if (parentPos) {
          // Count siblings placed so far
          let siblingCount = 0;
          for (const [id, pos] of posMap) {
            if (pos.y === parentPos.y + 150 && pos.x >= parentPos.x) {
              siblingCount++;
            }
          }
          const pos = {
            x: parentPos.x + siblingCount * 200,
            y: parentPos.y + 150,
          };
          posMap.set(evt.event_id, pos);
          return {
            id: evt.event_id,
            type: 'debateEvent',
            position: pos,
            data: evt,
          };
        }
        // Fallback: stack vertically
        return {
          id: evt.event_id,
          type: 'debateEvent',
          position: { x: 250, y: 50 + idx * 150 },
          data: evt,
        };
      });
      nodes = newNodes;
    });

    const unsub2 = debateEdges.subscribe((eds) => {
      edges = eds;
    });

    const unsub3 = eventStore.subscribe((state) => {
      selectedEventId = state.selectedEventId;
    });

    return () => {
      unsub1();
      unsub2();
      unsub3();
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

  function handleFork(event) {
    forkModalStore.open(event);
  }

  function handleNodeClick({ node }) {
    if (node?.data?.event_id) {
      eventStore.setSelectedEvent(node.data.event_id);
    }
  }

  let hasSelection = $derived(selectedEventId !== null);
</script>

<div class="debate-graph-wrapper h-full w-full flex">
  <!-- Main graph area -->
  <div class="debate-graph-container h-full" style="flex: 1 1 0%; min-width: 0;">
    {#if $spaceStore.loading || $eventStore.loading}
    <div class="flex items-center justify-center h-full">
      <div class="text-gray-500 dark:text-gray-400">Loading debate tree...</div>
    </div>
  {:else if nodes.length === 0}
    <div class="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
      <div class="text-4xl mb-4">🌳</div>
      <div class="text-lg font-medium mb-2">No events yet</div>
      <div class="text-sm">Click [+] on a node to start the debate.</div>
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

  <!-- Side panel (shown when an event is selected) -->
  {#if hasSelection}
    <div class="h-full flex-shrink-0">
      <EventDetailPanel {spaceId} />
    </div>
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
  .debate-graph-wrapper {
    overflow: hidden;
  }

  .debate-graph-container {
    overflow: hidden;
  }

  .debate-graph-container :global(.debate-flow) {
    background: #f8fafc;
  }
  .debate-graph-container :global(.dark .debate-flow) {
    background: #1f2937;
  }
  /* Ensure fork button is not clipped by SvelteFlow containers */
  .debate-graph-container :global(.react-flow__node) {
    overflow: visible !important;
  }
</style>
