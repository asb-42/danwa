<script>
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any }} */
  let { data } = $props();

  const actionIcons = {
    clarify: '❓',
    provide_context: '💬',
    start: '▶️',
    cancel: '⏹️',
  };

  let icon = $derived(actionIcons[data.actionType] || '👤');
  let statusClass = $derived(data.status || 'idle');
</script>

<div
  class="workflow-node user-action-node status-{statusClass}"
  class:oob={data.isOOB}
  class:blocking={data.isBlocking}
>
  <Handle type="target" position={Position.LEFT} />
  <div class="node-header">
    <span class="node-icon">{icon}</span>
    <span class="node-title">
      {data.isOOB ? 'Extra Info' : data.actionType || 'User Action'}
    </span>
    {#if data.isBlocking}
      <span class="blocking-badge">⏳</span>
    {/if}
  </div>
  <div class="node-body">
    <p class="node-label">{data.label || 'User input'}</p>
    {#if data.requestedBy}
      <span class="requested-by">from {data.requestedBy}</span>
    {/if}
  </div>
  <Handle type="source" position={Position.RIGHT} />
</div>

<style>
  .workflow-node {
    background: white;
    border: 2px solid #f59e0b;
    border-radius: 12px;
    padding: 10px;
    min-width: 140px;
    font-size: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
  }
  :global(.dark) .workflow-node { background: #1f2937; }
  .workflow-node.oob {
    border-color: #3b82f6;
    border-style: dashed;
  }
  .workflow-node.blocking {
    border-color: #ef4444;
    animation: blocking-pulse 2s ease-in-out infinite;
  }
  .workflow-node.status-resolved {
    border-color: #10b981;
    opacity: 0.8;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }
  .node-icon { font-size: 14px; }
  .node-title {
    font-weight: 600;
    color: #92400e;
    font-size: 11px;
    text-transform: capitalize;
  }
  :global(.dark) .node-title { color: #fbbf24; }
  .blocking-badge { margin-left: auto; }
  .node-body { color: #6b7280; }
  :global(.dark) .node-body { color: #9ca3af; }
  .node-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
    margin: 0;
  }
  .requested-by {
    font-size: 10px;
    color: #9ca3af;
    font-style: italic;
  }
  @keyframes blocking-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.3); }
    50% { box-shadow: 0 0 12px 4px rgba(239,68,68,0.2); }
  }
</style>
