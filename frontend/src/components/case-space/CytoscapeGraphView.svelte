<!--
  CytoscapeGraphView — Phase 4.5-4.7 Cytoscape renderer.

  Mounted lazily by BrowseView and the Workspace Inspector
  graph tab.  We import cytoscape dynamically so the
  ~1.4 MB raw / ~440 kB gzipped bundle only loads when
  the user actually opens the Graph view.

  Uses the same /api/v1/graph/* payload as the list-mode
  InspectorGraphTab so the two views are visually
  complementary: list for quick scanning, Cytoscape for
  spatial exploration.

  Per Konzept §A.8 we cap at 200 nodes (server-side
  ``GLOBAL_DEFAULT_LIMIT``); on overflow the backend sets
  ``truncated: true`` and the user sees a small hint.

  @see plans/2026-06-14_case-space-workspace.md (Phase 4.5-4.7)
-->
<script>
  import { onMount, onDestroy } from 'svelte';

  let { nodes = [], edges = [], height = 480 } = $props();

  let containerEl = $state(null);
  let cy = null;            // cytoscape.Core instance, not reactive
  let loadError = $state(null);
  let loaded = $state(false);

  onMount(async () => {
    try {
      // Dynamic import: keeps cytoscape out of the main chunk.
      const cytoscapeMod = await import('cytoscape');
      const cytoscape = cytoscapeMod.default || cytoscapeMod;
      if (!containerEl) return;
      cy = cytoscape({
        container: containerEl,
        elements: [
          ...nodes.map((n) => ({
            data: { id: n.id, label: n.label ?? n.id, kind: n.type ?? 'node' },
          })),
          ...edges.map((e) => ({
            data: {
              id: `${e.src}__${e.tgt}__${e.type}`,
              source: e.src,
              target: e.tgt,
              label: e.type ?? '',
              weight: e.weight ?? 0,
            },
          })),
        ],
        layout: { name: 'cose', animate: false, fit: true, padding: 24 },
        style: [
          {
            selector: 'node',
            style: {
              'background-color': '#3b82f6',
              'border-color': '#1e40af',
              'border-width': 1,
              label: 'data(label)',
              color: '#0f172a',
              'font-size': 10,
              'text-valign': 'center',
              'text-halign': 'center',
              'text-wrap': 'wrap',
              'text-max-width': 120,
              width: 'label',
              height: 'label',
              padding: 6,
              'background-opacity': 0.85,
            },
          },
          {
            selector: 'edge',
            style: {
              'line-color': '#94a3b8',
              'target-arrow-color': '#94a3b8',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              width: 1.2,
              'font-size': 8,
              color: '#475569',
              label: 'data(label)',
              'text-rotation': 'autorotate',
              'text-background-color': '#fff',
              'text-background-opacity': 0.8,
              'text-background-padding': 1,
            },
          },
        ],
      });
      loaded = true;
    } catch (err) {
      loadError = err;
    }
  });

  // Re-render when nodes/edges change (e.g. after refresh)
  $effect(() => {
    if (!cy || !loaded) return;
    // Add / update
    const presentIds = new Set(cy.nodes().map((n) => n.id()));
    for (const n of nodes) {
      if (!presentIds.has(n.id)) {
        cy.add({
          group: 'nodes',
          data: { id: n.id, label: n.label ?? n.id, kind: n.type ?? 'node' },
        });
      }
    }
    const presentEdgeIds = new Set(cy.edges().map((e) => e.id()));
    for (const e of edges) {
      const eid = `${e.src}__${e.tgt}__${e.type}`;
      if (!presentEdgeIds.has(eid)) {
        cy.add({
          group: 'edges',
          data: {
            id: eid,
            source: e.src,
            target: e.tgt,
            label: e.type ?? '',
            weight: e.weight ?? 0,
          },
        });
      }
    }
    cy.layout({ name: 'cose', animate: false, fit: true, padding: 24 }).run();
  });

  onDestroy(() => {
    if (cy) {
      try {
        cy.destroy();
      } catch {
        // Cytoscape occasionally throws on destroy during HMR.
        // Safe to ignore.
      }
      cy = null;
    }
  });
</script>

<div
  class="border rounded-lg overflow-hidden
         border-gray-200 dark:border-gray-700
         bg-white dark:bg-gray-800"
  data-testid="cytoscape-graph-view"
>
  {#if loadError}
    <div class="p-4 text-sm text-red-600 dark:text-red-400" role="alert">
      Cytoscape could not be loaded: {loadError?.message ?? String(loadError)}
    </div>
  {/if}
  <div
    bind:this={containerEl}
    style:height="{height}px"
    style:width="100%"
    aria-label="Cytoscape graph view"
    role="img"
  ></div>
</div>
