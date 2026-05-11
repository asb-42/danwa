<script>
  /**
   * AgentBlueprintNode — Custom Svelte Flow node for Agent Blueprints.
   *
   * Displays: name, ascendency badge, linked indicators for LLM/Role/Prompt.
   * Handles: LEFT (target), RIGHT (source).
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  const ascendencyColors = {
    kantian: { border: '#8b5cf6', bg: '#f5f3ff', darkBg: '#2e1065', label: 'Kantian' },
    hegelian: { border: '#f59e0b', bg: '#fffbeb', darkBg: '#451a03', label: 'Hegelian' },
    steiner: { border: '#10b981', bg: '#ecfdf5', darkBg: '#022c22', label: 'Steiner' },
  };

  let ascendencyTag = $derived(
    (data?.tags || []).find((t) => Object.keys(ascendencyColors).includes(t)),
  );
  let colors = $derived(ascendencyColors[ascendencyTag] || { border: '#6b7280', bg: '#f9fafb', darkBg: '#1f2937', label: null });
  let hasLlm = $derived(!!data?.llm_profile_id);
  let hasRole = $derived(!!data?.role_definition_id);
  let hasPrompt = $derived(!!data?.prompt_template_id);
  let isDraft = $derived(!!data?.isDraft);
</script>

<div
  class="blueprint-node agent-blueprint-node"
  class:selected
  class:draft={isDraft}
  style="border-color: {colors.border}; --node-bg: {colors.bg}; --node-dark-bg: {colors.darkBg}; --node-border: {colors.border};"
  data-testid="node-agent-blueprint-{data?.blueprint_id || 'draft'}"
>
  <Handle type="target" position={Position.Left} class="port-sequence" />

  <div class="node-header">
    <span class="node-icon">🤖</span>
    <span class="node-type-label">Agent Blueprint</span>
    {#if isDraft}
      <span class="draft-badge">Draft</span>
    {/if}
  </div>

  <div class="node-body">
    <span class="node-name">{data?.name || 'Unnamed'}</span>

    {#if colors.label}
      <span class="ascendency-badge" style="background: {colors.border};">
        {colors.label}
      </span>
    {/if}

    <div class="linked-indicators">
      <span class="indicator" class:linked={hasLlm} title={hasLlm ? 'LLM linked' : 'No LLM linked'}>
        {hasLlm ? '✓' : '○'} LLM
      </span>
      <span class="indicator" class:linked={hasRole} title={hasRole ? 'Role linked' : 'No role linked'}>
        {hasLlm ? '✓' : '○'} Role
      </span>
      <span class="indicator" class:linked={hasPrompt} title={hasPrompt ? 'Prompt override' : 'No prompt override'}>
        {hasPrompt ? '✓' : '○'} Prompt
      </span>
    </div>
  </div>

  <Handle type="source" position={Position.Right} class="port-sequence" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #f9fafb);
    border: 2px solid var(--node-border, #6b7280);
    border-radius: 12px;
    padding: 12px;
    min-width: 200px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #1f2937);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #3b82f6), 0 4px 12px rgba(0,0,0,0.15);
  }
  .blueprint-node.draft {
    opacity: 0.8;
    border-style: dashed;
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
  .draft-badge {
    margin-left: auto;
    font-size: 9px;
    background: #f59e0b;
    color: white;
    padding: 1px 6px;
    border-radius: 8px;
    font-weight: 600;
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
  .ascendency-badge {
    display: inline-block;
    font-size: 10px;
    color: white;
    padding: 1px 8px;
    border-radius: 8px;
    font-weight: 600;
    width: fit-content;
  }
  .linked-indicators {
    display: flex;
    gap: 8px;
    margin-top: 4px;
  }
  .indicator {
    font-size: 10px;
    color: #9ca3af;
  }
  .indicator.linked {
    color: #10b981;
    font-weight: 600;
  }
</style>
