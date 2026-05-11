<script>
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any }} */
  let { data } = $props();

  const typeIcons = {
    strategy: '📋',
    critique: '🔎',
    synthesis: '🔧',
    consensus: '✅',
  };

  const typeColors = {
    strategy: '#8b5cf6',
    critique: '#ef4444',
    synthesis: '#f59e0b',
    consensus: '#10b981',
  };

  let icon = $derived(typeIcons[data.artifactType] || '📄');
  let color = $derived(typeColors[data.artifactType] || '#6b7280');
  let statusIcon = $derived(
    data.status === 'final' ? '✅' : data.status === 'draft' ? '📝' : ''
  );
</script>

<div
  class="workflow-node artifact-node"
  style="border-color: {color};"
  class:final={data.status === 'final'}
>
  <Handle type="target" position={Position.Left} />
  <div class="node-header">
    <span class="node-icon">{icon}</span>
    <span class="node-type" style="color: {color};">{data.artifactType}</span>
    {#if statusIcon}
      <span class="status-icon">{statusIcon}</span>
    {/if}
  </div>
  <div class="node-body">
    {#if data.summary}
      <p class="node-summary">{data.summary}</p>
    {/if}
    {#if data.tokenCount}
      <span class="token-count">{data.tokenCount} tokens</span>
    {/if}
  </div>
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .workflow-node {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    padding: 10px;
    min-width: 150px;
    font-size: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
  }
  :global(.dark) .workflow-node { background: #1f2937; }
  .workflow-node.final {
    opacity: 0.9;
    border-style: solid;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }
  .node-icon { font-size: 14px; }
  .node-type {
    font-weight: 600;
    text-transform: capitalize;
    font-size: 12px;
  }
  .status-icon { margin-left: auto; font-size: 12px; }
  .node-body { color: #6b7280; }
  :global(.dark) .node-body { color: #9ca3af; }
  .node-summary {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
    margin: 0 0 4px 0;
  }
  .token-count {
    font-size: 10px;
    color: #9ca3af;
    font-family: monospace;
  }
</style>
