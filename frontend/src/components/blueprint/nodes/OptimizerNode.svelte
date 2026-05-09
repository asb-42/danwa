<script>
  /**
   * OptimizerNode — Optimizer workflow step.
   *
   * Amber (#f59e0b) themed, ⚡ icon.
   * LEFT target + RIGHT source handles.
   * Shows label, AgentBlueprint name if linked, linked status.
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let isLinked = $derived(!!data?.agent_blueprint_id);
  let blueprintName = $derived(data?.blueprintName || data?.agent_blueprint_id || '');
</script>

<div
  class="blueprint-node optimizer-node"
  class:selected
  style="border-color: #f59e0b; --node-bg: #fffbeb; --node-dark-bg: #451a03; --node-border: #f59e0b;"
  data-testid="node-wf-optimizer"
>
  <Handle type="target" position={Position.LEFT} id="in" />

  <div class="node-header">
    <span class="node-icon">⚡</span>
    <span class="node-type-label">Optimizer</span>
  </div>

  <div class="node-body">
    <span class="node-name">{data?.label || 'Optimizer'}</span>
    {#if isLinked}
      <div class="linked-info">
        <span class="status-linked">✓</span>
        <span class="blueprint-name">{blueprintName}</span>
      </div>
    {:else}
      <span class="status-unlinked">○ Not linked</span>
    {/if}
  </div>

  <Handle type="source" position={Position.RIGHT} id="out" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #fffbeb);
    border: 2px solid var(--node-border, #f59e0b);
    border-radius: 12px;
    padding: 12px;
    min-width: 180px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #451a03);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #f59e0b), 0 4px 12px rgba(0,0,0,0.15);
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
  }
  .node-icon { font-size: 16px; }
  .node-type-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
    font-weight: 600;
  }
  .node-body {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .node-name {
    font-weight: 700;
    font-size: 14px;
    color: #1f2937;
  }
  :global(.dark) .node-name { color: #e5e7eb; }
  .linked-info {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .status-linked {
    font-size: 10px;
    color: #10b981;
    font-weight: 600;
  }
  .blueprint-name {
    font-size: 10px;
    color: #6b7280;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
  }
  :global(.dark) .blueprint-name { color: #9ca3af; }
  .status-unlinked {
    font-size: 10px;
    color: #9ca3af;
  }
</style>
