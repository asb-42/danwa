<script>
  /**
   * WorkflowPipeline — reusable, data-driven workflow visualization.
   *
   * Modes:
   *   - 'static'  : definition only, no live updates
   *   - 'replay'  : paused playback of a completed workflow
   *   - 'live'    : receives updates via props/SSE adapter
   *
   * Data is passed via the `meta`, `nodes`, and `edges` props. The component
   * does NOT fetch anything itself — adapters (see
   * `lib/workflowPipelineAdapter.js`) do that and pass the result in.
   *
   * Used in:
   *   - Dashboard (last completed debate, compact mode)
   *   - DebateView wrapper (live mode, full)
   *   - Future: module admin, audit replay
   */
  import { onMount, untrack } from 'svelte';
  import { tStore } from '../../lib/i18n/index.js';
  import {
    computeLayout,
    nodePosition,
    edgePath,
    EDGE_KIND,
  } from '../../lib/workflow/pipeline-utils.js';
  import PipelineNode from './pipeline/PipelineNode.svelte';
  import PipelineEdge from './pipeline/PipelineEdge.svelte';
  import PipelineLegend from './pipeline/PipelineLegend.svelte';
  import PipelineEmptyState from './pipeline/PipelineEmptyState.svelte';

  let {
    meta = null,
    nodes = [],
    edges = [],
    activeNodeId = null,
    mode = 'static',
    compact = false,
    interactive = false,
    showMetrics = true,
    showLegend = true,
    onNodeClick = null,
    onEdgeClick = null,
    onStartDebate = null,
  } = $props();

  let t = $derived($tStore);

  let layoutResult = $state(null);
  let svgWidth = $state(700);
  let svgHeight = $state(160);
  let isLayoutReady = $state(false);

  // Build a lookup of nodes by id for edge geometry
  let nodeById = $derived.by(() => {
    const m = new Map();
    for (const n of nodes || []) m.set(n.id, n);
    return m;
  });

  // Recompute layout whenever nodes/edges change structurally
  $effect(() => {
    // Read sizes for reactivity tracking
    const layoutInput = (nodes || []).map((n) => ({
      id: n.id,
      width: n.width ?? 120,
      height: n.height ?? 48,
    }));
    const layoutEdges = (edges || []).map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      kind: e.kind,
    }));

    // Untrack the layout result writes so they don't re-trigger this effect
    untrack(() => {
      isLayoutReady = false;
    });

    let cancelled = false;
    computeLayout(layoutInput, layoutEdges, { direction: 'RIGHT' })
      .then((result) => {
        if (cancelled) return;
        layoutResult = result;
        svgWidth = result.width;
        svgHeight = result.height;
        isLayoutReady = true;
      })
      .catch((err) => {
        if (import.meta.env.DEV) {
          console.warn('[WorkflowPipeline] ELK layout failed:', err);
        }
      });

    return () => {
      cancelled = true;
    };
  });

  // Mark forward edges active when their source is the current node
  function isEdgeActive(edge) {
    if (!activeNodeId) return false;
    return edge.source === activeNodeId;
  }

  function handleNodeClick(node) {
    if (typeof onNodeClick === 'function') onNodeClick(node);
  }

  function handleEdgeClick(edge) {
    if (typeof onEdgeClick === 'function') onEdgeClick(edge);
  }

  function labelPosFor(layout, edge, sourceNode, targetNode) {
    const src = nodePosition(layout, edge.source);
    const tgt = nodePosition(layout, edge.target);
    if (!src || !tgt || !sourceNode || !targetNode) return null;
    if (edge.kind === EDGE_KIND.FEEDBACK) {
      const x1 = src.x + sourceNode.width / 2;
      const y1 = src.y + sourceNode.height;
      const x2 = tgt.x + targetNode.width / 2;
      const y2 = tgt.y + targetNode.height;
      const midY = Math.max(y1, y2) + 40;
      return { x: (x1 + x2) / 2, y: midY - 6 };
    }
    return null;
  }

  let hasData = $derived((nodes?.length ?? 0) > 0);
</script>

<div
  class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 workflow-pipeline-root"
  data-testid="workflow-pipeline"
>
  {#if meta?.name}
    <div class="px-6 pt-4 pb-2 flex items-center justify-between">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
        {meta.name}
      </h3>
      <span class="text-xs text-gray-400 dark:text-gray-500">
        {t(`workflowPipeline.mode.${mode}`) || mode}
      </span>
    </div>
  {:else}
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white px-6 pt-4">
      {t('workflowPipeline.title') || 'Workflow Overview'}
    </h3>
  {/if}

  {#if !hasData}
    <div class="px-6 pb-6">
      <PipelineEmptyState {onStartDebate} />
    </div>
  {:else if isLayoutReady && layoutResult}
    <div class="px-6 pb-2 overflow-x-auto">
      <svg
        width={svgWidth}
        height={svgHeight}
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        class="mx-auto"
        aria-label={meta?.name || 'Workflow pipeline'}
        role="img"
      >
        <defs>
          <marker id="workflow-pipeline-arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" class="fill-gray-400 dark:fill-gray-500" />
          </marker>
          <marker id="workflow-pipeline-arrowhead-feedback" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" class="fill-amber-500" />
          </marker>
          <filter id="workflow-pipeline-glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {#each edges as edge}
          {@const srcNode = nodeById.get(edge.source)}
          {@const tgtNode = nodeById.get(edge.target)}
          {@const path = edgePath(layoutResult, edge, srcNode, tgtNode)}
          {@const labelPos = labelPosFor(layoutResult, edge, srcNode, tgtNode)}
          <PipelineEdge
            {edge}
            {path}
            {labelPos}
            active={isEdgeActive(edge)}
            {mode}
          />
        {/each}

        {#each nodes as node}
          {@const pos = nodePosition(layoutResult, node.id)}
          {#if pos}
            <PipelineNode
              {node}
              x={pos.x}
              y={pos.y}
              active={activeNodeId === node.id}
              {showMetrics}
              {compact}
              onClick={interactive ? handleNodeClick : null}
            />
          {/if}
        {/each}
      </svg>
    </div>

    {#if showLegend}
      <div class="px-6 pb-4">
        <PipelineLegend {compact} />
      </div>
    {/if}
  {:else}
    <div class="flex items-center justify-center h-32">
      <div class="flex items-center gap-2 text-gray-400 dark:text-gray-500">
        <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span class="text-sm">{t('common.loading') || 'Loading…'}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .workflow-pipeline-root {
    padding-top: 0.5rem;
  }
</style>
