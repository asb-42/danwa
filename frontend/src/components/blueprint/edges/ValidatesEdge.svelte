<script>
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';
  import { edgeStatusClass } from '../../../lib/blueprint/edgeStatus.js';

  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
  let statusClass = $derived(edgeStatusClass(data));
</script>

<BaseEdge {id} {path} class="blueprint-edge validates-edge {statusClass}" marker-end="url(#arrow-slate)" />

<svelte:head>
  <svg style="position:absolute;width:0;height:0;">
    <defs>
      <marker id="arrow-slate" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
      </marker>
    </defs>
  </svg>
</svelte:head>

<style>
  :global(.validates-edge) {
    stroke: #64748b;
    stroke-width: 2.5;
  }
</style>
