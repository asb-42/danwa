<script>
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any }} */
  let { data } = $props();

  let statusClass = $derived(data.isActive ? 'active' : data.status || 'idle');
</script>

<div
  class="workflow-node a2a-node status-{statusClass}"
>
  <Handle type="target" position={Position.LEFT} />
  <div class="node-header">
    <span class="node-icon">🌐</span>
    <span class="node-role">{data.role || 'A2A Agent'}</span>
    <span class="a2a-badge">A2A</span>
  </div>
  <div class="node-body">
    <span class="node-round">Round {data.round}</span>
    {#if data.agentUrl}
      <span class="node-url" title={data.agentUrl}>{new URL(data.agentUrl).hostname}</span>
    {/if}
    {#if data.activity}
      <span class="node-activity">
        {#if data.activity === 'invoking'}🌐 Invoking...
        {:else if data.activity === 'polling'}⏳ Polling...
        {:else}{data.activity}
        {/if}
      </span>
    {/if}
  </div>
  {#if data.isActive}
    <div class="pulse-ring"></div>
  {/if}
  <Handle type="source" position={Position.RIGHT} />
</div>

<style>
  .workflow-node {
    background: white;
    border: 2px solid var(--role-border, #e5e7eb);
    border-radius: 12px;
    padding: 12px;
    min-width: 160px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
    position: relative;
  }
  .a2a-node {
    --role-border: #8b5cf6;
    --role-bg: #f5f3ff;
    --role-dark-bg: #2e1065;
    border-color: var(--role-border);
  }
  :global(.dark) .workflow-node {
    background: var(--role-dark-bg, #1f2937);
  }
  :global(.dark) .a2a-node {
    background: var(--role-dark-bg);
  }
  .workflow-node.active {
    box-shadow: 0 0 16px rgba(139,92,246,0.4);
    animation: node-glow 1.5s ease-in-out infinite alternate;
  }
  .workflow-node.completed {
    opacity: 0.85;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }
  .node-icon { font-size: 18px; }
  .node-role {
    font-weight: 700;
    color: var(--role-border, #374151);
    text-transform: capitalize;
    font-size: 14px;
  }
  :global(.dark) .node-role { color: #e5e7eb; }
  .a2a-badge {
    margin-left: auto;
    font-size: 9px;
    font-weight: 700;
    color: #8b5cf6;
    background: #f5f3ff;
    border: 1px solid #8b5cf6;
    border-radius: 4px;
    padding: 1px 4px;
    letter-spacing: 0.5px;
  }
  :global(.dark) .a2a-badge {
    background: #2e1065;
    color: #c4b5fd;
    border-color: #7c3aed;
  }
  .node-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .node-round {
    font-size: 11px;
    color: #6b7280;
  }
  :global(.dark) .node-round { color: #9ca3af; }
  .node-url {
    font-size: 10px;
    color: #9ca3af;
    font-family: monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
  }
  .node-activity {
    font-size: 10px;
    color: #8b5cf6;
    font-style: italic;
    margin-top: 2px;
    animation: activity-pulse 1.5s ease-in-out infinite;
  }
  @keyframes activity-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  .pulse-ring {
    position: absolute;
    inset: -4px;
    border-radius: 14px;
    border: 2px solid var(--role-border, #8b5cf6);
    opacity: 0;
    animation: pulse 2s ease-in-out infinite;
    pointer-events: none;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.02); }
  }
  @keyframes node-glow {
    from { box-shadow: 0 0 8px rgba(139,92,246,0.2); }
    to { box-shadow: 0 0 20px rgba(139,92,246,0.5); }
  }
</style>
