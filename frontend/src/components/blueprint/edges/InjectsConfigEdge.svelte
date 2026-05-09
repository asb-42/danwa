<script>
  /**
   * InjectsConfigEdge — Orange/yellow dashed edge for config injection.
   *
   * Used in Workflow Mode to connect tone_profile nodes to agent nodes.
   * No arrowhead, thinner than sequential edges, no animation.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
</script>

<BaseEdge {id} {path} class="blueprint-edge injects-config-edge" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.injects-config-edge) {
    stroke: #f59e0b;
    stroke-width: 1.5;
    stroke-dasharray: 6 4;
  }
</style>
