<script>
  /**
   * InterjectionEdge — Rose dotted edge for external input points.
   *
   * Used in Workflow Mode to indicate where external input
   * (user query, OOB input, external event) enters the workflow.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';
  import { edgeStatusClass } from '../../../lib/blueprint/edgeStatus.js';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
  let statusClass = $derived(edgeStatusClass(data));
</script>

<BaseEdge {id} {path} class="blueprint-edge interjection-edge {statusClass}" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.interjection-edge) {
    stroke: #f43f5e;
    stroke-width: 2;
    stroke-dasharray: 4 4;
  }
</style>
