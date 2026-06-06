<script>
  /**
   * UsesLlmEdge — Blue solid edge for AgentBlueprint → LLMProfile connections.
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

<BaseEdge {id} {path} class="blueprint-edge uses-llm-edge {statusClass}" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.uses-llm-edge) {
    stroke: #3b82f6;
    stroke-width: 2;
  }
</style>
