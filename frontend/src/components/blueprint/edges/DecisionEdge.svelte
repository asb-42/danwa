<script>
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';
  import { edgeStatusClass } from '../../../lib/blueprint/edgeStatus.js';

  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );

  let condition = $derived(data?.condition || 'revision_required');
  let color = $derived(condition === 'approved' ? '#22c55e' : '#f59e0b');
  let markerId = $derived(condition === 'approved' ? 'arrow-decision-approved' : 'arrow-decision-rejected');
  let statusClass = $derived(edgeStatusClass(data));
</script>

<BaseEdge {id} {path} class="blueprint-edge decision-edge {statusClass}" style="stroke: {color};" marker-end="url(#{markerId})" />

<svelte:head>
  <svg style="position:absolute;width:0;height:0;">
    <defs>
      <marker id="arrow-decision-approved" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
      </marker>
      <marker id="arrow-decision-rejected" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
      </marker>
    </defs>
  </svg>
</svelte:head>

<style>
  :global(.decision-edge) {
    stroke-width: 2;
    stroke-dasharray: 4 2;
  }
</style>
