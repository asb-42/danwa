<script>
  /**
   * PromptedByEdge — Emerald dashed edge for RoleDefinition → PromptTemplate connections.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
</script>

<BaseEdge {id} {path} class="blueprint-edge prompted-by-edge" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.prompted-by-edge) {
    stroke: #10b981;
    stroke-width: 2;
    stroke-dasharray: 8 4;
  }
</style>
