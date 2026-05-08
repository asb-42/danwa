<script>
  /**
   * ImplementsRoleEdge — Violet solid edge for AgentBlueprint → RoleDefinition connections.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
</script>

<BaseEdge {id} {path} class="blueprint-edge implements-role-edge" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.implements-role-edge) {
    stroke: #8b5cf6;
    stroke-width: 2;
  }
</style>
