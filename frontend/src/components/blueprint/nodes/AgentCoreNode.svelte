<script>
  /**
   * AgentCoreNode — Custom Svelte Flow node for Agent Core modules.
   *
   * Displays: module name, role badge, description.
   * Handles: LEFT (target), RIGHT (source).
   * Color: Teal (#0d9488) — distinct from legacy types.
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let isDraft = $derived(!!data?.isDraft);
  let moduleName = $derived(data?.name || data?.module_name || 'Agent Core');
  let moduleRole = $derived(data?.role || '');
  let moduleDescription = $derived(data?.description || '');
  let moduleId = $derived(data?.module_id || data?.blueprint_id || '');

  const ROLE_ICONS = {
    strategist: '🧠', critic: '🔍', optimizer: '⚡', moderator: '🎯',
    analyst: '📊', creative: '💡', 'fact-checker': '✅',
    'expert-reviewer': '🔬', mediator: '🤝', ethicist: '⚖️',
    synthesizer: '🔗', 'devils-advocate': '👿',
  };

  let nodeIcon = $derived(ROLE_ICONS[moduleRole] || '🧬');
</script>

<div
  class="blueprint-node agent-core-node"
  class:selected
  class:draft={isDraft}
  data-testid="node-agent-core-{moduleId || 'draft'}"
>
  <Handle type="target" position={Position.Left} class="port-agent-core" />

  <div class="node-header">
    <span class="node-icon">{nodeIcon}</span>
    <span class="node-type-label">Agent Core</span>
    {#if isDraft}
      <span class="draft-badge">Draft</span>
    {/if}
  </div>

  <div class="node-body">
    <span class="node-name">{moduleName}</span>

    {#if moduleRole}
      <span class="role-badge">{moduleRole}</span>
    {/if}

    {#if moduleDescription}
      <span class="node-description">{moduleDescription}</span>
    {/if}
  </div>

  <Handle type="source" position={Position.Right} class="port-agent-core" />
</div>

<style>
  .blueprint-node {
    background: #f0fdfa;
    border: 2px solid #0d9488;
    border-radius: 12px;
    padding: 12px;
    min-width: 180px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
  }
  :global(.dark) .blueprint-node {
    background: #042f2e;
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px #0d9488, 0 4px 12px rgba(0,0,0,0.15);
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
  .role-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #0d9488;
    background: #ccfbf1;
    padding: 2px 8px;
    border-radius: 6px;
    width: fit-content;
  }
  :global(.dark) .role-badge {
    background: #134e4a;
    color: #5eead4;
  }
  .node-description {
    font-size: 11px;
    color: #9ca3af;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
