<script>
  /**
   * ConditionalEdge — Amber dashed edge for branching logic.
   *
   * Used in Workflow Mode for conditional branches with a condition label.
   * Uses foreignObject for the label since EdgeLabelRenderer is not
   * available in @xyflow/svelte@1.5.x.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';
  import { edgeStatusClass } from '../../../lib/blueprint/edgeStatus.js';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let [path, labelX, labelY] = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY }),
  );
  let statusClass = $derived(edgeStatusClass(data));
</script>

<BaseEdge {id} {path} class="blueprint-edge conditional-edge {statusClass}" />

{#if data?.condition}
  <foreignObject x={labelX - 60} y={labelY - 12} width="120" height="24"
    style="overflow: visible; pointer-events: none;"
  >
    <div
      class="conditional-label"
      xmlns="http://www.w3.org/1999/xhtml"
    >
      {data.condition}
    </div>
  </foreignObject>
{/if}

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.conditional-edge) {
    stroke: #f59e0b;
    stroke-width: 2;
    stroke-dasharray: 8 4;
  }
  .conditional-label {
    font-size: 10px;
    font-weight: 600;
    color: #92400e;
    background: #fef3c7;
    border: 1px solid #f59e0b;
    border-radius: 4px;
    padding: 1px 6px;
    text-align: center;
    white-space: nowrap;
    pointer-events: all;
  }
  :global(.dark) .conditional-label {
    color: #fbbf24;
    background: #451a03;
    border-color: #92400e;
  }
</style>
