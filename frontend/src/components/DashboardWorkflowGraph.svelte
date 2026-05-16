<script>
  /**
   * DashboardWorkflowGraph — Static ELK.js visualization of the standard debate pipeline.
   * Renders an SVG-based flow diagram: Input → Strategist → Critic → Optimizer → Moderator → Result
   */
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import ELK from 'elkjs/lib/elk.bundled.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const NODES = [
    { id: 'input', label: 'Input', icon: '📥', color: '#6b7280', width: 100, height: 48 },
    { id: 'strategist', label: 'Strategist', icon: '🧠', color: '#8b5cf6', width: 130, height: 48 },
    { id: 'critic', label: 'Critic', icon: '🔍', color: '#ef4444', width: 100, height: 48 },
    { id: 'optimizer', label: 'Optimizer', icon: '⚡', color: '#f59e0b', width: 120, height: 48 },
    { id: 'moderator', label: 'Moderator', icon: '🎯', color: '#6366f1', width: 120, height: 48 },
    { id: 'result', label: 'Result', icon: '📋', color: '#10b981', width: 100, height: 48 },
  ];

  const EDGES = [
    { id: 'e1', source: 'input', target: 'strategist' },
    { id: 'e2', source: 'strategist', target: 'critic' },
    { id: 'e3', source: 'critic', target: 'optimizer' },
    { id: 'e4', source: 'optimizer', target: 'moderator' },
    { id: 'e5', source: 'moderator', target: 'result' },
  ];

  let layoutResult = $state(null);
  let svgWidth = $state(700);
  let svgHeight = $state(120);

  onMount(async () => {
    try {
      const elk = new ELK();
      const graph = {
        id: 'root',
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': 'RIGHT',
          'elk.layered.spacing.nodeNodeBetweenLayers': '60',
          'elk.spacing.nodeNode': '30',
        },
        children: NODES.map(n => ({ id: n.id, width: n.width, height: n.height })),
        edges: EDGES.map(e => ({ id: e.id, sources: [e.source], targets: [e.target] })),
      };

      const result = await elk.layout(graph);
      layoutResult = result;

      // Calculate SVG bounds
      let maxX = 0, maxY = 0;
      function calcBounds(node) {
        if (node.x != null) maxX = Math.max(maxX, node.x + (node.width || 0));
        if (node.y != null) maxY = Math.max(maxY, node.y + (node.height || 0));
        if (node.children) node.children.forEach(calcBounds);
      }
      if (result.children) result.children.forEach(calcBounds);
      svgWidth = maxX + 40;
      svgHeight = maxY + 40;
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
    const x1 = src.x + srcNode.width;
    const y1 = src.y + srcNode.height / 2;
    const x2 = tgt.x;
    const y2 = tgt.y + tgtNode.height / 2;
    const cx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`;
  }
</script>

<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
  <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('dashboard.workflowTitle')}</h3>

  {#if layoutResult}
    <div class="overflow-x-auto">
      <svg width={svgWidth} height={svgHeight} viewBox={`0 0 ${svgWidth} ${svgHeight}`} class="mx-auto">
        <!-- Edges -->
        {#each EDGES as edge}
          <path
            d={getEdgePath(edge)}
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            class="text-gray-300 dark:text-gray-600"
            marker-end="url(#arrowhead)"
          />
        {/each}

        <!-- Arrow marker -->
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" class="fill-gray-400 dark:fill-gray-500" />
          </marker>
        </defs>

        <!-- Nodes -->
        {#each NODES as node}
          {@const pos = getNodePos(node.id)}
          {#if pos}
            <g transform={`translate(${pos.x}, ${pos.y})`}>
              <!-- Node background -->
              <rect
                width={node.width}
                height={node.height}
                rx="8"
                class="fill-gray-50 dark:fill-gray-700 stroke-gray-200 dark:stroke-gray-600"
                stroke-width="1.5"
              />
              <!-- Color accent bar -->
              <rect
                width="4"
                height={node.height}
                rx="2"
                fill={node.color}
              />
              <!-- Icon -->
              <text x="16" y={node.height / 2 + 5} font-size="16" text-anchor="middle">{node.icon}</text>
              <!-- Label -->
              <text
                x={node.width / 2 + 8}
                y={node.height / 2 + 5}
                font-size="12"
                font-weight="600"
                class="fill-gray-700 dark:fill-gray-200"
                text-anchor="middle"
              >{node.label}</text>
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
