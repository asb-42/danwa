<script>
  /**
   * SequentialEdge — Indigo solid edge for workflow step A → step B.
   *
   * Used in Workflow Mode to connect sequential workflow steps.
   */
  import { BaseEdge, getBezierPath } from '@xyflow/svelte';

  /** @type {{ id: string, sourceX: number, sourceY: number, targetX: number, targetY: number, data?: any }} */
  let { id, sourceX, sourceY, targetX, targetY, data = {} } = $props();

  let path = $derived(
    getBezierPath({ sourceX, sourceY, targetX, targetY })[0],
  );
</script>

<BaseEdge {id} {path} class="blueprint-edge sequential-edge" />

<!-- svelte-ignore css_unused_selector -->
<style>
  :global(.sequential-edge) {
    stroke: #6366f1;
    stroke-width: 2.5;
  }
</style>
