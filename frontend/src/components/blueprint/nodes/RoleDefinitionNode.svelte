<script>
  /**
   * RoleDefinitionNode — Custom Svelte Flow node for Role Definitions.
   *
   * Displays: name, ascendency badge, capabilities count.
   * Handles: LEFT (target), RIGHT (source).
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  const roleIcons = {
    strategist: '🧠',
    critic: '🔍',
    optimizer: '⚡',
    moderator: '🎯',
  };

  const ascendencyColors = {
    kantian: { border: '#8b5cf6', bg: '#f5f3ff', darkBg: '#2e1065', label: 'Kantian' },
    hegelian: { border: '#f59e0b', bg: '#fffbeb', darkBg: '#451a03', label: 'Hegelian' },
    steiner: { border: '#10b981', bg: '#ecfdf5', darkBg: '#022c22', label: 'Steiner' },
  };

  let icon = $derived(roleIcons[data?.role] || '👤');
  let ascendencyTag = $derived(
    (data?.tags || []).find((t) => Object.keys(ascendencyColors).includes(t)),
  );
  let colors = $derived(ascendencyColors[ascendencyTag] || { border: '#8b5cf6', bg: '#f5f3ff', darkBg: '#2e1065', label: null });
  let isDraft = $derived(!!data?.isDraft);
</script>

<div
  class="blueprint-node role-definition-node"
  class:selected
  class:draft={isDraft}
  style="border-color: {colors.border}; --node-bg: {colors.bg}; --node-dark-bg: {colors.darkBg}; --node-border: {colors.border};"
  data-testid="node-role-definition-{data?.blueprint_id || 'draft'}"
>
  <Handle type="target" position={Position.Left} class="port-role" />

  <div class="node-header">
    <span class="node-icon">👤</span>
    <span class="node-type-label">Role Definition</span>
    {#if isDraft}
      <span class="draft-badge">Draft</span>
    {/if}
  </div>

  <div class="node-body">
    <span class="node-name">{data?.name || 'Unnamed'}</span>

    <div class="role-row">
      <span class="role-icon">{icon}</span>
      <span class="role-label">{data?.role || 'unknown'}</span>
    </div>

    {#if colors.label}
      <span class="ascendency-badge" style="background: {colors.border};">
        {colors.label}
      </span>
    {/if}

    {#if data?.tags?.length}
      <span class="tag-count">{data.tags.length} tag{data.tags.length !== 1 ? 's' : ''}</span>
    {/if}
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
    gap: 3px;
  }
  .node-name {
    font-weight: 700;
    font-size: 14px;
    color: #1f2937;
  }
  :global(.dark) .node-name { color: #e5e7eb; }
  .role-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .role-icon { font-size: 12px; }
  .role-label {
    font-size: 11px;
    color: #6b7280;
    text-transform: capitalize;
  }
  .ascendency-badge {
    display: inline-block;
    font-size: 10px;
    color: white;
    padding: 1px 8px;
    border-radius: 8px;
    font-weight: 600;
    width: fit-content;
  }
  .tag-count {
    font-size: 10px;
    color: #9ca3af;
  }
</style>
