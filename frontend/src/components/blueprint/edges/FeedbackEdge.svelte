<script>
  /**
   * FeedbackEdge — Green dash-dot edge for feedback loops.
   *
   * Used in Workflow Mode for feedback connections (e.g. moderator → strategist).
   * Uses getBezierPath with offset for visual feedback loop.
   * Shows "feedback" label via foreignObject.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let [path, labelX, labelY] = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY }),
  );
</script>

<BaseEdge {id} {path} class="blueprint-edge feedback-edge" />

<foreignObject x={labelX - 35} y={labelY - 10} width="70" height="20"
  style="overflow: visible; pointer-events: none;"
>
  <div
    class="feedback-label"
    xmlns="http://www.w3.org/1999/xhtml"
  >
    feedback
  </div>
</foreignObject>

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.feedback-edge) {
    stroke: #10b981;
    stroke-width: 2;
    stroke-dasharray: 12 4 4 4;
  }
  .feedback-label {
    font-size: 9px;
    font-weight: 600;
    color: #065f46;
    background: #d1fae5;
    border: 1px solid #10b981;
    border-radius: 4px;
    padding: 0 5px;
    text-align: center;
    white-space: nowrap;
    pointer-events: all;
    line-height: 18px;
  }
  :global(.dark) .feedback-label {
    color: #6ee7b7;
    background: #022c22;
    border-color: #065f46;
  }
</style>
