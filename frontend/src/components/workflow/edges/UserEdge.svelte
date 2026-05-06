<script>
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let isActive = $derived(data?.isActive);
  let isRequest = $derived(data?.type === 'user_request');

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0]
  );

  let strokeColor = $derived(
    isRequest ? '#f59e0b' : (isActive ? '#10b981' : '#94a3b8')
  );

  let edgeClass = $derived(
    ['user-edge', isActive && 'active'].filter(Boolean).join(' ')
  );
</script>

<BaseEdge {id} {path} class={edgeClass} />
{#if data?.label}
  <text
    x={(sourceX + targetX) / 2}
    y={(sourceY + targetY) / 2 - 10}
    text-anchor="middle"
    class="user-label"
    fill={strokeColor}
  >
    {data.label}
  </text>
{/if}

<style>
  :global(.user-edge) {
    stroke: #94a3b8;
    stroke-width: 2;
    stroke-dasharray: 8 4;
    transition: all 0.3s ease;
  }
  :global(.user-edge.active) {
    stroke: #10b981;
    stroke-width: 3;
    stroke-dasharray: 8 4;
    animation: user-flow 1s linear infinite;
  }
  .user-label {
    font-size: 10px;
    font-weight: 600;
  }
  @keyframes user-flow {
    from { stroke-dashoffset: 12; }
    to { stroke-dashoffset: 0; }
  }
</style>
