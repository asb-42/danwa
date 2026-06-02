<script>
  /**
   * DashboardWorkflowGraph — Animated ELK.js visualization of the debate pipeline.
   * Renders an SVG-based flow diagram with:
   * - Forward flow: Input → Strategist → Critic → Optimizer → Moderator → Result
   * - Feedback loop: Moderator → Strategist (retry when consensus below threshold)
   * - Animated flow particles when status === 'running'
   * - Active node highlighting via activeNodeId prop
   */
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { getElk } from '../lib/elk-service.js';

  let { activeNodeId = null, status = 'idle' } = $props();

  let t = $derived($tStore);

  const NODES = [
    { id: 'input', label: 'Input', icon: '📥', color: '#6b7280', width: 100, height: 48 },
    { id: 'strategist', label: 'Strategist', icon: '🧠', color: '#8b5cf6', width: 130, height: 48 },
    { id: 'critic', label: 'Critic', icon: '🔍', color: '#ef4444', width: 100, height: 48 },
    { id: 'optimizer', label: 'Optimizer', icon: '⚡', color: '#f59e0b', width: 120, height: 48 },
    { id: 'moderator', label: 'Moderator', icon: '🎯', color: '#6366f1', width: 120, height: 48 },
    { id: 'result', label: 'Result', icon: '📋', color: '#10b981', width: 100, height: 48 },
  ];

  const FORWARD_EDGES = [
    { id: 'e1', source: 'input', target: 'strategist' },
    { id: 'e2', source: 'strategist', target: 'critic' },
    { id: 'e3', source: 'critic', target: 'optimizer' },
    { id: 'e4', source: 'optimizer', target: 'moderator' },
    { id: 'e5', source: 'moderator', target: 'result' },
  ];

  const FEEDBACK_EDGES = [
    { id: 'fb1', source: 'moderator', target: 'strategist', label: 'Retry' },
  ];

  const ALL_EDGES = [...FORWARD_EDGES, ...FEEDBACK_EDGES];

  let layoutResult = $state(null);
  let svgWidth = $state(700);
  let svgHeight = $state(160);
  let isLayoutReady = $state(false);

  onMount(async () => {
    try {
      const elk = getElk();
      const graph = {
        id: 'root',
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': 'RIGHT',
          'elk.layered.spacing.nodeNodeBetweenLayers': '60',
          'elk.spacing.nodeNode': '30',
          'elk.layered.feedbackEdges': 'true',
          'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
        },
        children: NODES.map(n => ({ id: n.id, width: n.width, height: n.height })),
        edges: ALL_EDGES.map(e => ({ id: e.id, sources: [e.source], targets: [e.target] })),
      };

      const result = await elk.layout(graph);
      layoutResult = result;
      isLayoutReady = true;

      let maxX = 0, maxY = 0;
      function calcBounds(node) {
        if (node.x != null) maxX = Math.max(maxX, node.x + (node.width || 0));
        if (node.y != null) maxY = Math.max(maxY, node.y + (node.height || 0));
        if (node.children) node.children.forEach(calcBounds);
      }
      if (result.children) result.children.forEach(calcBounds);
      svgWidth = maxX + 60;
      svgHeight = maxY + 80;
    } catch (err) {
      console.warn('[DashboardWorkflowGraph] ELK layout failed:', err);
    }
  });

  function getNodePos(nodeId) {
    if (!layoutResult?.children) return null;
    function find(node) {
      if (node.id === nodeId) return { x: node.x ?? 0, y: node.y ?? 0 };
      if (node.children) {
        for (const child of node.children) {
          const found = find(child);
          if (found) return found;
        }
      }
      return null;
    }
    for (const child of layoutResult.children) {
      const found = find(child);
      if (found) return found;
    }
    return null;
  }

  function getEdgePath(edge) {
    const src = getNodePos(edge.source);
    const tgt = getNodePos(edge.target);
    const srcNode = NODES.find(n => n.id === edge.source);
    const tgtNode = NODES.find(n => n.id === edge.target);
    if (!src || !tgt || !srcNode || !tgtNode) return '';

    const isFeedback = edge.source === 'moderator' && edge.target === 'strategist';

    if (isFeedback) {
      const x1 = src.x + srcNode.width / 2;
      const y1 = src.y + srcNode.height;
      const x2 = tgt.x + tgtNode.width / 2;
      const y2 = tgt.y + tgtNode.height;
      const midY = Math.max(y1, y2) + 40;
      return `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;
    }

    const x1 = src.x + srcNode.width;
    const y1 = src.y + srcNode.height / 2;
    const x2 = tgt.x;
    const y2 = tgt.y + tgtNode.height / 2;
    const cx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`;
  }

  function getEdgeLabelPos(edge) {
    const src = getNodePos(edge.source);
    const tgt = getNodePos(edge.target);
    const srcNode = NODES.find(n => n.id === edge.source);
    const tgtNode = NODES.find(n => n.id === edge.target);
    if (!src || !tgt || !srcNode || !tgtNode) return null;

    const x1 = src.x + srcNode.width / 2;
    const y1 = src.y + srcNode.height;
    const x2 = tgt.x + tgtNode.width / 2;
    const y2 = tgt.y + tgtNode.height;
    const midY = Math.max(y1, y2) + 40;
    return { x: (x1 + x2) / 2, y: midY - 6 };
  }
</script>

<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
  <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('dashboard.workflowTitle')}</h3>

  {#if isLayoutReady && layoutResult}
    <div class="overflow-x-auto">
      <svg width={svgWidth} height={svgHeight} viewBox={`0 0 ${svgWidth} ${svgHeight}`} class="mx-auto">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" class="fill-gray-400 dark:fill-gray-500" />
          </marker>
          <marker id="arrowhead-feedback" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" class="fill-amber-500" />
          </marker>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        <!-- Forward edges -->
        {#each FORWARD_EDGES as edge}
          {@const path = getEdgePath(edge)}
          {#if path}
            <path
              d={path}
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              class="text-gray-300 dark:text-gray-600"
              marker-end="url(#arrowhead)"
            />
            {#if status === 'running'}
              <circle r="3" class="fill-blue-500" opacity="0.8">
                <animateMotion dur="2s" repeatCount="indefinite" path={path} />
              </circle>
            {/if}
          {/if}
        {/each}

        <!-- Feedback edges -->
        {#each FEEDBACK_EDGES as edge}
          {@const path = getEdgePath(edge)}
          {@const labelPos = getEdgeLabelPos(edge)}
          {#if path}
            <path
              d={path}
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-dasharray="4,3"
              class="text-amber-500 dark:text-amber-400"
              marker-end="url(#arrowhead-feedback)"
            />
            {#if labelPos}
              <text
                x={labelPos.x}
                y={labelPos.y}
                font-size="9"
                font-weight="500"
                class="fill-amber-600 dark:fill-amber-400"
                text-anchor="middle"
              >{edge.label || 'Retry'}</text>
            {/if}
            {#if status === 'running'}
              <circle r="3" class="fill-amber-500" opacity="0.8">
                <animateMotion dur="3s" repeatCount="indefinite" path={path} />
              </circle>
            {/if}
          {/if}
        {/each}

        <!-- Nodes -->
        {#each NODES as node}
          {@const pos = getNodePos(node.id)}
          {@const isActive = activeNodeId === node.id}
          {@const isCompleted = status === 'completed'}
          {#if pos}
            <g transform={`translate(${pos.x}, ${pos.y})`} class:active-node={isActive}>
              {#if isActive}
                <rect
                  x="-3" y="-3"
                  width={node.width + 6}
                  height={node.height + 6}
                  rx="10"
                  fill="none"
                  stroke={node.color}
                  stroke-width="2"
                  opacity="0.6"
                  filter="url(#glow)"
                >
                  <animate attributeName="opacity" values="0.3;0.8;0.3" dur="1.5s" repeatCount="indefinite" />
                </rect>
              {/if}
              {#if isCompleted && node.id === 'result'}
                <rect
                  x="-4" y="-4"
                  width={node.width + 8}
                  height={node.height + 8}
                  rx="12"
                  fill="none"
                  stroke="#10b981"
                  stroke-width="2.5"
                  filter="url(#glow)"
                >
                  <animate attributeName="opacity" values="0.4;0.9;0.4" dur="2s" repeatCount="indefinite" />
                </rect>
              {/if}
              <rect
                width={node.width}
                height={node.height}
                rx="8"
                class="fill-gray-50 dark:fill-gray-700 stroke-gray-200 dark:stroke-gray-600"
                stroke-width="1.5"
              />
              <rect
                width="4"
                height={node.height}
                rx="2"
                fill={node.color}
              />
              <text x="16" y={node.height / 2 + 5} font-size="16" text-anchor="middle">{node.icon}</text>
              <text
                x={node.width / 2 + 8}
                y={node.height / 2 + 5}
                font-size="12"
                font-weight="600"
                class="fill-gray-700 dark:fill-gray-200"
                text-anchor="middle"
              >{node.label}</text>
              {#if isCompleted && node.id === 'result'}
                <text
                  x={node.width - 8}
                  y="-6"
                  font-size="14"
                  text-anchor="middle"
                >✓</text>
              {/if}
            </g>
          {/if}
        {/each}
      </svg>
    </div>

    <!-- Legend -->
    <div class="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
      <div class="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400">
        <span class="flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 rounded-full" style="background:#8b5cf6"></span>
          {t('dashboard.workflowLegend.strategist') || 'Strategy'}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 rounded-full" style="background:#ef4444"></span>
          {t('dashboard.workflowLegend.critic') || 'Critique'}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 rounded-full" style="background:#f59e0b"></span>
          {t('dashboard.workflowLegend.optimizer') || 'Synthesis'}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 rounded-full" style="background:#6366f1"></span>
          {t('dashboard.workflowLegend.moderator') || 'Consensus'}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-4 h-0.5 bg-amber-500" style="border-top: 1.5px dashed currentColor; height: 0;"></span>
          {t('dashboard.workflowLegend.retry') || 'Retry loop'}
        </span>
      </div>
    </div>
  {:else}
    <div class="flex items-center justify-center h-32">
      <div class="flex items-center gap-2 text-gray-400 dark:text-gray-500">
        <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span class="text-sm">{t('common.loading')}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .active-node {
    animation: node-pulse 1.5s ease-in-out infinite;
  }
  @keyframes node-pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.02); }
  }
</style>
