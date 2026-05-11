<script>
  /**
   * RoleTypeNode — Custom Svelte Flow node for Role Types.
   *
   * Displays: icon, name, color badge, default settings.
   * Handles: LEFT (target), RIGHT (source).
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let isDraft = $derived(!!data?.isDraft);
  let nodeColor = $derived(data?.color || '#8b5cf6');
  let nodeIcon = $derived(data?.icon || '👤');
</script>

<div
  class="blueprint-node role-type-node"
  class:selected
  class:draft={isDraft}
  style="border-color: {nodeColor}; --node-bg: {nodeColor}11; --node-dark-bg: {nodeColor}22; --node-border: {nodeColor};"
  data-testid="node-role-type-{data?.blueprint_id || 'draft'}"
>
  <Handle type="target" position={Position.Left} class="port-role" />

  <div class="node-header">
    <span class="node-icon">{nodeIcon}</span>
    <span class="node-type-label">Role Type</span>
    {#if isDraft}
      <span class="draft-badge">Draft</span>
    {/if}
  </div>

  <div class="node-body">
    <span class="node-name">{data?.name || 'Unnamed'}</span>

    <div class="color-row">
      <span class="color-swatch" style="background: {nodeColor};"></span>
      <span class="color-label">{nodeColor}</span>
    </div>

    {#if data?.description}
      <span class="node-description">{data.description}</span>
    {/if}

    <div class="defaults-row">
      <span class="default-tag">Rounds: {data?.default_max_rounds ?? 5}</span>
      <span class="default-tag">Threshold: {data?.default_consensus_threshold ?? 0.9}</span>
    </div>
  </div>

  <Handle type="source" position={Position.Right} class="port-role" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #f5f3ff);
    border: 2px solid var(--node-border, #8b5cf6);
    border-radius: 12px;
    padding: 12px;
    min-width: 180px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #2e1065);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #8b5cf6), 0 4px 12px rgba(0,0,0,0.15);
  }
  .blueprint-node.draft {
    opacity: 0.7;
    border-style: dashed;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }
  .node-icon { font-size: 16px; }
  .node-type-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
  }
  :global(.dark) .node-type-label { color: #9ca3af; }
  .draft-badge {
    font-size: 9px;
    background: #f59e0b;
    color: white;
    padding: 1px 6px;
    border-radius: 8px;
    font-weight: 600;
    margin-left: auto;
  }
  .node-body {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .node-name {
    font-weight: 700;
    font-size: 14px;
    color: #1f2937;
  }
  :global(.dark) .node-name { color: #e5e7eb; }
  .color-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .color-swatch {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid rgba(0,0,0,0.15);
  }
  .color-label {
    font-size: 11px;
    color: #6b7280;
    font-family: monospace;
  }
  :global(.dark) .color-label { color: #9ca3af; }
  .node-description {
    font-size: 11px;
    color: #9ca3af;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .defaults-row {
    display: flex;
    gap: 6px;
    margin-top: 2px;
  }
  .default-tag {
    font-size: 10px;
    background: #f3f4f6;
    color: #6b7280;
    padding: 1px 6px;
    border-radius: 4px;
  }
  :global(.dark) .default-tag {
    background: #374151;
    color: #9ca3af;
  }
</style>
