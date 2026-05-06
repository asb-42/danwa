<script>
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let isConsumed = $derived(data?.isConsumed);
  let isStale = $derived(data?.isStale);

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0]
  );

  let strokeColor = $derived(
    isStale ? '#9ca3af' : isConsumed ? '#10b981' : '#f59e0b'
  );
</script>

<g>
  <!-- Main path -->
  <path
    d={path}
    fill="none"
    stroke={strokeColor}
    stroke-width={isConsumed ? 2 : 3}
    stroke-dasharray={isConsumed ? 'none' : '8 4'}
    opacity={isStale ? 0.4 : 1}
  />

  <!-- Animation for pending -->
  {#if !isConsumed && !isStale}
    <path
      d={path}
      fill="none"
      stroke="#f59e0b"
      stroke-width={3}
      stroke-dasharray="12 8"
      class="animate-oob-flow"
    />
  {/if}

  <!-- Label -->
  {#if data?.label}
    <text
      x={(sourceX + targetX) / 2}
      y={(sourceY + targetY) / 2 - 10}
      text-anchor="middle"
      class="oob-label"
      fill={isStale ? '#9ca3af' : '#d97706'}
    >
      {data.label}{isConsumed ? ' ✓' : ''}
    </text>
  {/if}
</g>

<style>
  @keyframes oob-flow {
    from { stroke-dashoffset: 20; }
    to { stroke-dashoffset: 0; }
  }
  .animate-oob-flow {
    animation: oob-flow 1.5s linear infinite;
  }
  .oob-label {
    font-size: 11px;
    font-weight: 600;
  }
</style>
