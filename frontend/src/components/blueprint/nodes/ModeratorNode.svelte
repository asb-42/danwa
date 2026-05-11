<script>
  /**
   * ModeratorNode — Moderator workflow step.
   *
   * Green (#10b981) themed, 🎯 icon.
   * LEFT target + RIGHT source + BOTTOM feedback handles.
   * TOP config input port (for injects_config edges).
   * Shows label, AgentBlueprint name if linked, linked status.
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let isLinked = $derived(!!data?.agent_blueprint_id);
  let blueprintName = $derived(data?.blueprintName || data?.agent_blueprint_id || '');
</script>

<div
  class="blueprint-node moderator-node"
  class:selected
  style="border-color: #10b981; --node-bg: #ecfdf5; --node-dark-bg: #022c22; --node-border: #10b981;"
  data-testid="node-wf-moderator"
>
  <Handle type="target" position={Position.Top} id="config-in" class="config-input-port port-config" title="Tone" />
  <Handle type="target" position={Position.Left} id="in" class="port-sequence" />

  <div class="node-header">
    <span class="node-icon">🎯</span>
    <span class="node-type-label">Moderator</span>
  </div>

  <div class="node-body">
    <span class="node-name">{data?.label || 'Moderator'}</span>
    {#if isLinked}
      <div class="linked-info">
        <span class="status-linked">✓</span>
        <span class="blueprint-name">{blueprintName}</span>
      </div>
    {:else}
      <span class="status-unlinked">○ Not linked</span>
    {/if}
  </div>

  <Handle type="source" position={Position.Right} id="out" class="port-feedback" />
  <!-- Feedback handle — connects back to agents for another round -->
  <Handle type="source" position={Position.Bottom} id="feedback" class="port-feedback" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #ecfdf5);
    border: 2px solid var(--node-border, #10b981);
    border-radius: 12px;
    padding: 12px;
    min-width: 180px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #022c22);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #10b981), 0 4px 12px rgba(0,0,0,0.15);
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

  /* Config input port (top) — orange/yellow hollow circle */
  :global(.config-input-port) {
    width: 10px !important;
    height: 10px !important;
    background: white !important;
    border: 2px solid #f59e0b !important;
    border-radius: 50% !important;
    top: -5px !important;
    transition: all 0.2s ease;
  }
  :global(.dark) :global(.config-input-port) {
    background: #022c22 !important;
  }
  :global(.config-input-port):hover {
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.3);
  }
</style>
