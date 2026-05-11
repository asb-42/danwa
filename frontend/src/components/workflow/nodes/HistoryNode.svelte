<script>
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any }} */
  let { data } = $props();
</script>

<div class="workflow-node history-node">
  <Handle type="target" position={Position.Left} />
  <div class="node-header">
    <span class="node-icon">📚</span>
    <span class="node-title">Round {data.round}</span>
  </div>
  <div class="node-body">
    {#if data.executionPath}
      <div class="path-summary">
        {data.executionPath.length} steps
      </div>
    {/if}
    {#if data.completedAt}
      <span class="completed-time">
        {new Date(data.completedAt).toLocaleTimeString()}
      </span>
    {/if}
  </div>
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .workflow-node {
    background: #f9fafb;
    border: 2px solid #d1d5db;
    border-radius: 12px;
    padding: 10px;
    min-width: 120px;
    font-size: 12px;
    opacity: 0.7;
    transition: all 0.3s ease;
  }
  :global(.dark) .workflow-node {
    background: #111827;
    border-color: #374151;
  }
  .workflow-node:hover { opacity: 1; }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }
  .node-icon { font-size: 14px; }
  .node-title {
    font-weight: 600;
    color: #6b7280;
    font-size: 12px;
  }
  :global(.dark) .node-title { color: #9ca3af; }
  .node-body { color: #9ca3af; font-size: 11px; }
  .path-summary { margin-bottom: 2px; }
  .completed-time {
    font-size: 10px;
    color: #d1d5db;
    font-family: monospace;
  }
</style>
