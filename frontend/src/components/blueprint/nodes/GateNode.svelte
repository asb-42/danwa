<script>
  /**
   * GateNode — Conditional branching gate in workflow.
   *
   * Rose (#f43f5e) themed, 🔀 icon.
   * LEFT target + RIGHT true-branch + BOTTOM false-branch handles.
   * Shows label, condition summary.
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let condition = $derived(data?.config?.condition || data?.condition || '');
</script>

<div
  class="blueprint-node gate-node"
  class:selected
  style="border-color: #f43f5e; --node-bg: #fff1f2; --node-dark-bg: #4c0519; --node-border: #f43f5e;"
  data-testid="node-wf-gate"
>
  <Handle type="target" position={Position.LEFT} id="in" />

  <div class="node-header">
    <span class="node-icon">🔀</span>
    <span class="node-type-label">Gate</span>
  </div>

  <div class="node-body">
    <span class="node-name">{data?.label || 'Gate'}</span>
    {#if condition}
      <div class="condition-row">
        <span class="condition-text">{condition}</span>
      </div>
    {/if}
  </div>

  <!-- True branch (right) -->
  <Handle type="source" position={Position.RIGHT} id="true" />
  <!-- False branch (bottom) -->
  <Handle type="source" position={Position.BOTTOM} id="false" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #fff1f2);
    border: 2px solid var(--node-border, #f43f5e);
    border-radius: 12px;
    padding: 12px;
    min-width: 160px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #4c0519);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #f43f5e), 0 4px 12px rgba(0,0,0,0.15);
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
  .condition-row { margin-top: 2px; }
  .condition-text {
    font-size: 10px;
    color: #be123c;
    background: #ffe4e6;
    border: 1px solid #f43f5e;
    border-radius: 4px;
    padding: 1px 6px;
    font-family: monospace;
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: inline-block;
  }
  :global(.dark) .condition-text {
    color: #fda4af;
    background: #4c0519;
    border-color: #9f1239;
  }
</style>
