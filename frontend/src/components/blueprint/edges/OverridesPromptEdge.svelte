<script>
  /**
   * OverridesPromptEdge — Amber dotted edge for AgentBlueprint → PromptTemplate connections.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
</script>

<BaseEdge {id} {path} class="blueprint-edge overrides-prompt-edge" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.overrides-prompt-edge) {
    stroke: #f59e0b;
    stroke-width: 2;
    stroke-dasharray: 4 4;
  }
</style>
