<script>
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let isActive = $derived(data?.isActive);
  let isCompleted = $derived(data?.status === 'completed');

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0]
  );

  let edgeClass = $derived(
    ['flow-edge', isActive && 'active', isCompleted && 'completed'].filter(Boolean).join(' ')
  );
</script>

<BaseEdge {id} {path} class={edgeClass} />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.flow-edge) {
    stroke: #94a3b8;
    stroke-width: 2;
    transition: all 0.3s ease;
  }
  :global(.flow-edge.active) {
    stroke: #3b82f6;
    stroke-width: 3;
    stroke-dasharray: 8 4;
    animation: flow-dash 1s linear infinite;
  }
  :global(.flow-edge.completed) {
    stroke: #10b981;
    stroke-width: 2;
  }
  @keyframes flow-dash {
    from { stroke-dashoffset: 12; }
    to { stroke-dashoffset: 0; }
  }
</style>
