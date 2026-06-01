<script>
  import { Handle, Position } from '@xyflow/svelte';
  /** @type {import('@xyflow/svelte').NodeProps} */
  let { data, selected, id } = $props();
</script>

<div
  class="blueprint-node angels-advocate-node"
  class:selected
  style="border-color: #f59e0b; --node-bg: #fffbeb; --node-dark-bg: #451a03; --node-border: #f59e0b;"
  data-testid="node-wf-angels-advocate"
>
  <Handle type="target" position={Position.Left} />

  <div class="node-header">
    <span class="node-icon">🛡️</span>
    <span class="node-label">{data.label || "Angel's Advocate"}</span>
  </div>

  {#if data.agent_blueprint_id}
    <div class="node-detail">BP: {data.agent_blueprint_id}</div>
  {/if}

  <Handle type="source" position={Position.Right} />
</div>

<style>
  .blueprint-node {
    padding: 8px 12px;
    border: 2px solid var(--node-border);
    border-radius: 8px;
    background: var(--node-bg);
    min-width: 160px;
    font-size: 12px;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border);
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
  }
  .node-icon {
    font-size: 16px;
  }
  .node-detail {
    margin-top: 4px;
    font-size: 10px;
    opacity: 0.7;
  }
</style>
