<script>
  /**
   * UsesCoreEdge — Teal solid edge for AgentBlueprint → AgentCore connections.
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

<BaseEdge {id} {path} class="blueprint-edge uses-core-edge {statusClass}" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.uses-core-edge) {
    stroke: #0d9488;
    stroke-width: 2;
  }
</style>
