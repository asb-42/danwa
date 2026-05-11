<script>
  /**
   * LLMProfileNode — Custom Svelte Flow node for LLM Profiles.
   *
   * Displays: provider icon, model name, A2A badge.
   * Handles: LEFT (target), RIGHT (source).
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  const providerIcons = {
    openrouter: '🌐',
    openai: '🟢',
    anthropic: '🟠',
    local: '💻',
    ollama: '🦙',
    google: '🔵',
    azure: '☁️',
  };

  let icon = $derived(providerIcons[data?.provider] || '🧠');
  let hasA2A = $derived(data?.protocol === 'a2a' || !!data?.a2a_endpoint);
  let isA2A = $derived(data?.protocol === 'a2a');
  let agentName = $derived(data?.a2a_config?.name || '');
  let isDraft = $derived(!!data?.isDraft);
</script>

<div
  class="blueprint-node llm-profile-node"
  class:selected
  class:draft={isDraft}
  data-testid="node-llm-profile-{data?.blueprint_id || 'draft'}"
>
  <Handle type="target" position={Position.Left} />

  <div class="node-header">
    <span class="node-icon">🧠</span>
    <span class="node-type-label">LLM Profile</span>
    {#if isDraft}
      <span class="draft-badge">Draft</span>
    {/if}
  </div>

  <div class="node-body">
    <span class="node-name">{data?.name || 'Unnamed'}</span>

    <div class="provider-row">
      <span class="provider-icon">{icon}</span>
      <span class="provider-label">{data?.provider || 'unknown'}</span>
    </div>

    {#if data?.model}
      <span class="model-name">{data.model}</span>
    {/if}

    {#if hasA2A}
      <span class="a2a-badge" title="A2A endpoint configured">A2A</span>
    {/if}
  </div>

  <Handle type="source" position={Position.Right} />
</div>

<style>
  .blueprint-node {
    background: #eff6ff;
    border: 2px solid #3b82f6;
    border-radius: 12px;
    padding: 12px;
    min-width: 180px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
  }
  :global(.dark) .blueprint-node {
    background: #1e1b4b;
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px #3b82f6, 0 4px 12px rgba(0,0,0,0.15);
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
    color: #6b7280;
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
    color: #1e3a5f;
  }
  :global(.dark) .node-name { color: #bfdbfe; }
  .provider-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .provider-icon { font-size: 12px; }
  .provider-label {
    font-size: 11px;
    color: #6b7280;
    text-transform: capitalize;
  }
  .model-name {
    font-size: 10px;
    color: #9ca3af;
    font-family: monospace;
    word-break: break-all;
  }
  .a2a-badge {
    display: inline-block;
    font-size: 9px;
    background: #8b5cf6;
    color: white;
    padding: 1px 6px;
    border-radius: 8px;
    font-weight: 700;
    width: fit-content;
    margin-top: 2px;
  }
</style>
