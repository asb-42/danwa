<script>
  /**
   * AgentNode — Generic workflow agent node referencing an AgentBundle.
   *
   * Color and icon are dynamically derived from the referenced RoleType.
   * Shows bundle name, role type, and LLM profile if linked.
   * LEFT target + RIGHT source handles.
   * TOP config input port (for injects_config edges from tone_profile nodes).
   */
  import { Handle, Position } from '@xyflow/svelte';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';

  /** @type {{ id: string, data: any, selected?: boolean }} */
  let { id, data, selected = false } = $props();

  let bundleId = $derived(data?.bundle_id || data?.data?.bundle_id || '');
  let bundleName = $derived(data?.label || data?.data?.label || data?.bundle_name || 'Agent');
  let roleTypeIcon = $derived(data?.data?.role_type_icon || data?.role_type_icon || '\u{1F464}');
  let roleTypeName = $derived(data?.data?.role_type_name || data?.role_type_name || '');
  let roleTypeColor = $derived(data?.data?.role_type_color || data?.role_type_color || '#8b5cf6');
  let llmProfileName = $derived(data?.data?.llm_profile_name || data?.llm_profile_name || '');

  let isLinked = $derived(!!bundleId);

  // Compute edge info locally from the store
  let hasIncomingEdge = $derived(canvasStore.edges.some((e) => e.target === id));
  let hasOutgoingEdge = $derived(canvasStore.edges.some((e) => e.source === id));
  let incomingEdgeTypes = $derived(
    canvasStore.edges.filter((e) => e.target === id).map((e) => e.type)
  );

  // Dynamic CSS vars from RoleType color
  let nodeBg = $derived(roleTypeColor + '15'); // 15 hex = ~10% opacity
  let nodeDarkBg = $derived(roleTypeColor + '30');
</script>

<div
  class="blueprint-node agent-node"
  class:selected
  style="border-color: {roleTypeColor}; --node-bg: {nodeBg}; --node-dark-bg: {nodeDarkBg}; --node-border: {roleTypeColor};"
  data-testid="node-wf-agent"
>
  <!-- Config input port (top) — orange/yellow hollow circle -->
  <Handle
    type="target"
    position={Position.Top}
    id="config-in"
    class="config-input-port"
    title="Tone"
  />

  <Handle type="target" position={Position.Left} id="in" class="port-sequence" />

  <div class="node-header">
    <span class="node-icon">{roleTypeIcon}</span>
    <span class="node-type-label">Agent</span>
  </div>

  <div class="node-body">
    <span class="node-name">{bundleName}</span>
    {#if roleTypeName}
      <span class="role-type-name">{roleTypeIcon} {roleTypeName}</span>
    {/if}
    {#if isLinked}
      <div class="linked-info">
        <span class="status-linked">✓</span>
        <span class="bundle-name">{bundleName}</span>
      </div>
      {#if llmProfileName}
        <span class="llm-info">{llmProfileName}</span>
      {/if}
    {:else if hasIncomingEdge}
      <div class="linked-info">
        <span class="status-connected">●</span>
        <span class="edge-info">{incomingEdgeTypes.join(', ')}</span>
      </div>
    {:else}
      <span class="status-unlinked">○ No bundle</span>
    {/if}
  </div>

  <Handle type="source" position={Position.Right} id="out" class="port-sequence" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #f5f3ff);
    border: 2px solid var(--node-border, #8b5cf6);
    border-radius: 12px;
    padding: 12px;
    min-width: 200px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #2e1065);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #8b5cf6), 0 4px 12px rgba(0,0,0,0.15);
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
  .role-type-name {
    font-size: 11px;
    color: #6b7280;
  }
  :global(.dark) .role-type-name { color: #9ca3af; }
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
  .bundle-name {
    font-size: 10px;
    color: #6b7280;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 160px;
  }
  :global(.dark) .bundle-name { color: #9ca3af; }
  .llm-info {
    font-size: 9px;
    color: #9ca3af;
    font-style: italic;
  }
  .status-unlinked {
    font-size: 10px;
    color: #9ca3af;
  }
  .status-connected {
    font-size: 10px;
    color: #3b82f6;
    font-weight: 600;
  }
  .edge-info {
    font-size: 9px;
    color: #6b7280;
    font-style: italic;
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
    background: var(--node-dark-bg, #2e1065) !important;
  }
  :global(.config-input-port):hover {
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.3);
  }
</style>
