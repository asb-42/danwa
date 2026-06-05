<script>
  /**
   * PipelineNode — single node in the WorkflowPipeline.
   * Pure presentational: receives a node + position, draws the rect.
   * Status-driven styling via STATUS_COLORS.
   */
  import { STATUS_COLORS, NODE_STATUS } from '../../../lib/workflow/pipeline-utils.js';
  import PipelineMetrics from './PipelineMetrics.svelte';

  let {
    node,
    x = 0,
    y = 0,
    active = false,
    showMetrics = true,
    compact = false,
    onClick = null,
  } = $props();

  let colors = $derived(STATUS_COLORS[node.status] || STATUS_COLORS[NODE_STATUS.PENDING]);
  let isInteractive = $derived(typeof onClick === 'function');
  let isDone = $derived(node.status === NODE_STATUS.DONE);
  let isFailed = $derived(node.status === NODE_STATUS.FAILED);

  function handleClick() {
    if (isInteractive) onClick(node);
  }

  function handleKeydown(e) {
    if (!isInteractive) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick(node);
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<g
  transform={`translate(${x}, ${y})`}
  class:active-node={active}
  class:done-node={isDone}
  class:failed-node={isFailed}
  class:interactive={isInteractive}
  role={isInteractive ? 'button' : 'img'}
  tabindex={isInteractive ? 0 : undefined}
  aria-label={isInteractive
    ? `${node.label} — ${node.status}`
    : `${node.label} (${node.status})`}
  onclick={handleClick}
  onkeydown={isInteractive ? handleKeydown : null}
>
  {#if active}
    <rect
      x="-3" y="-3"
      width={node.width + 6}
      height={node.height + 6}
      rx="10"
      fill="none"
      stroke={colors.fill}
      stroke-width="2"
      opacity="0.6"
      filter="url(#workflow-pipeline-glow)"
    >
      <animate attributeName="opacity" values="0.3;0.8;0.3" dur="1.5s" repeatCount="indefinite" />
    </rect>
  {/if}

  <rect
    width={node.width}
    height={node.height}
    rx="8"
    class="pipeline-node-bg fill-gray-50 dark:fill-gray-700 stroke-gray-200 dark:stroke-gray-600"
    stroke-width="1.5"
    opacity={colors.opacity}
  />
  <rect
    width="4"
    height={node.height}
    rx="2"
    fill={node.color || colors.fill}
  />
  <text
    x="16"
    y={node.height / 2 + 5}
    font-size="16"
    text-anchor="middle"
  >{node.icon || '▫️'}</text>
  <text
    x={node.width / 2 + 8}
    y={node.height / 2 + 5}
    font-size="12"
    font-weight="600"
    class="fill-gray-700 dark:fill-gray-200"
    text-anchor="middle"
  >{node.label}</text>

  {#if isDone}
    <text
      x={node.width - 8}
      y="-6"
      font-size="14"
      text-anchor="middle"
      fill="#10b981"
    >✓</text>
  {/if}
  {#if isFailed}
    <text
      x={node.width - 8}
      y="-6"
      font-size="14"
      text-anchor="middle"
      fill="#ef4444"
    >⚠</text>
  {/if}

  {#if showMetrics && !compact && node.metrics}
    <PipelineMetrics metrics={node.metrics} x={node.width / 2} y={node.height + 4} />
  {/if}
  {#if showMetrics && compact && node.metrics}
    <PipelineMetrics metrics={node.metrics} x={node.width / 2} y={node.height + 4} compact />
  {/if}
</g>

<style>
  g.interactive {
    cursor: pointer;
  }
  g.interactive:hover .pipeline-node-bg {
    fill: rgb(243 244 246);
  }
  :global(.dark) g.interactive:hover .pipeline-node-bg {
    fill: rgb(75 85 99);
  }
  g.interactive:focus-visible {
    outline: none;
  }
  g.interactive:focus-visible .pipeline-node-bg {
    stroke: #3b82f6;
    stroke-width: 2.5;
  }
</style>
