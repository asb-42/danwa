<script>
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0]
  );
</script>

<BaseEdge {id} {path} class="feedback-edge" />
{#if data?.label}
  <text
    x={(sourceX + targetX) / 2}
    y={(sourceY + targetY) / 2 - 10}
    text-anchor="middle"
    class="feedback-label"
  >
    {data.label}
  </text>
{/if}

<style>
  :global(.feedback-edge) {
    stroke: #f59e0b;
    stroke-width: 2;
    stroke-dasharray: 6 4;
    animation: feedback-flow 1.5s linear infinite;
  }
  .feedback-label {
    font-size: 10px;
    fill: #d97706;
    font-weight: 600;
  }
  :global(.dark) .feedback-label { fill: #fbbf24; }
  @keyframes feedback-flow {
    from { stroke-dashoffset: 10; }
    to { stroke-dashoffset: 0; }
  }
</style>
