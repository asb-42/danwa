<script>
  /**
   * InputNode — Entry point for workflow graphs.
   *
   * Blue (#3b82f6) themed, 📥 icon.
   * RIGHT source handle only (no target — it's the entry point).
   * Shows "Case Input" label, linked status.
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let isLinked = $derived(!!data?.linked);
</script>

<div
  class="blueprint-node input-node"
  class:selected
  style="border-color: #3b82f6; --node-bg: #eff6ff; --node-dark-bg: #1e3a5f; --node-border: #3b82f6;"
  data-testid="node-wf-input"
>
  <div class="node-header">
    <span class="node-icon">📥</span>
    <span class="node-type-label">Input</span>
  </div>

  <div class="node-body">
    <span class="node-name">{data?.label || 'Case Input'}</span>
    <div class="status-row">
      {#if isLinked}
        <span class="status-linked">✓ Linked</span>
      {:else}
        <span class="status-unlinked">○ Not linked</span>
      {/if}
    </div>
  </div>

  <!-- Source only — entry point has no incoming edge -->
  <Handle type="source" position={Position.Right} id="out" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #eff6ff);
    border: 2px solid var(--node-border, #3b82f6);
    border-radius: 12px;
    padding: 12px;
    min-width: 160px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #1e3a5f);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #3b82f6), 0 4px 12px rgba(0,0,0,0.15);
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
  .status-row { margin-top: 2px; }
  .status-linked {
    font-size: 10px;
    color: #10b981;
    font-weight: 600;
  }
  .status-unlinked {
    font-size: 10px;
    color: #9ca3af;
  }
</style>
