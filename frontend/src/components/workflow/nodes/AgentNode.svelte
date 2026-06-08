<script>
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any }} */
  let { data } = $props();

  const roleIcons = {
    strategist: '🧠',
    critic: '🔍',
    optimizer: '⚡',
    moderator: '🎯',
  };

  const roleColors = {
    strategist: { border: '#8b5cf6', bg: '#f5f3ff', darkBg: '#2e1065' },
    critic: { border: '#ef4444', bg: '#fef2f2', darkBg: '#450a0a' },
    optimizer: { border: '#f59e0b', bg: '#fffbeb', darkBg: '#451a03' },
    moderator: { border: '#10b981', bg: '#ecfdf5', darkBg: '#022c22' },
  };

  let colors = $derived(roleColors[data.role] || roleColors.strategist);
  let icon = $derived(roleIcons[data.role] || '🤖');
  let statusClass = $derived(data.isActive ? 'active' : data.status || 'idle');
  let isFailed = $derived(data.status === 'failed');
  let isCalling = $derived(data.isActive && data.activity === 'llm_calling');
</script>

<div
  class="workflow-node agent-node status-{statusClass}"
  class:failed={isFailed}
  style="border-color: {isFailed ? '#ef4444' : colors.border}; --role-bg: {colors.bg}; --role-dark-bg: {colors.darkBg}; --role-border: {isFailed ? '#ef4444' : colors.border};"
>
  <Handle type="target" position={Position.Left} />
  <div class="node-header">
    <span class="node-icon">{icon}</span>
    <span class="node-role">{data.role}</span>
    {#if data.hasFeedbackLoop}
      <span class="loop-badge" title="Has feedback loop">🔄</span>
    {/if}
    {#if isFailed}
      <span class="error-badge" title="Failed">❌</span>
    {/if}
  </div>
  <div class="node-body">
    <span class="node-round">Round {data.round}</span>
    {#if data.profile}
      <span class="node-profile">{data.profile}</span>
    {/if}
    {#if data.model}
      <span class="node-model">🤖 {data.model}</span>
    {/if}
    {#if data.activity}
      <span class="node-activity">
        {#if data.activity === 'searching'}🔍 {data.activityDetail || 'Searching...'}
        {:else if data.activity === 'llm_calling'}
          <span class="spinner"></span> LLM calling…
        {:else if data.activity === 'thinking'}🧠 Thinking...
        {:else}{data.activity}
        {/if}
      </span>
    {/if}
  </div>
  {#if data.isActive}
    <div class="pulse-ring"></div>
  {/if}
  <Handle type="source" position={Position.Right} />
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
  :global(.dark) .workflow-node {
    background: var(--role-dark-bg, #1f2937);
  }
  .workflow-node.active {
    box-shadow: 0 0 16px rgba(59,130,246,0.4);
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
  .loop-badge {
    margin-left: auto;
    font-size: 12px;
    opacity: 0.7;
  }
  .error-badge {
    margin-left: auto;
    font-size: 12px;
  }
  .workflow-node.failed {
    border-color: #ef4444 !important;
    box-shadow: 0 0 12px rgba(239,68,68,0.3);
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
  .node-profile {
    font-size: 10px;
    color: #9ca3af;
    font-family: monospace;
  }
  .node-model {
    font-size: 9px;
    color: #6b7280;
    font-family: monospace;
  }
  :global(.dark) .node-model { color: #9ca3af; }
  .node-activity {
    font-size: 10px;
    color: #3b82f6;
    font-style: italic;
    margin-top: 2px;
    animation: activity-pulse 1.5s ease-in-out infinite;
  }
  @keyframes activity-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  .spinner {
    display: inline-block;
    width: 10px;
    height: 10px;
    border: 2px solid #3b82f6;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    vertical-align: middle;
    margin-right: 3px;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .pulse-ring {
    position: absolute;
    inset: -4px;
    border-radius: 14px;
    border: 2px solid var(--role-border, #3b82f6);
    opacity: 0;
    animation: pulse 2s ease-in-out infinite;
    pointer-events: none;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.02); }
  }
  @keyframes node-glow {
    from { box-shadow: 0 0 8px rgba(59,130,246,0.2); }
    to { box-shadow: 0 0 20px rgba(59,130,246,0.5); }
  }
</style>
