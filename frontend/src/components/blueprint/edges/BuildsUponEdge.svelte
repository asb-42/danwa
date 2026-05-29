<script>
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
</script>

<BaseEdge {id} {path} class="blueprint-edge builds-upon-edge" marker-end="url(#arrow-green)" />

<svelte:head>
  <svg style="position:absolute;width:0;height:0;">
    <defs>
      <marker id="arrow-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
      </marker>
    </defs>
  </svg>
</svelte:head>

<style>
  :global(.builds-upon-edge) {
    stroke: #22c55e;
    stroke-width: 2;
    stroke-dasharray: 6 3;
  }
</style>
