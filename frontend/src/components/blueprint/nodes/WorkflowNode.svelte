<script>
  /**
   * WorkflowNode — Template for workflow step nodes.
   *
   * Used for Strategist, Critic, Optimizer, Moderator, and User Input
   * workflow steps. Displays role-based coloring, linked status,
   * sequential I/O ports, and execution status visualization.
   */
  import { Handle, Position } from '@xyflow/svelte';
  import { tStore } from '../../../lib/i18n/index.js';

  /** @type {{ data: { role: string, label: string, isDraft: boolean, blueprintId?: string, icon?: string, executionStatus?: string } }} */
  let { data } = $props();

  let t = $derived($tStore);

  const roleColors = {
    strategist: { border: '#8b5cf6', bg: '#f5f3ff' },
    critic: { border: '#ef4444', bg: '#fef2f2' },
    optimizer: { border: '#f59e0b', bg: '#fffbeb' },
    moderator: { border: '#10b981', bg: '#ecfdf5' },
    user_input: { border: '#6366f1', bg: '#eef2ff' },
  };

  const roleIcons = {
    strategist: '🧠',
    critic: '🔍',
    optimizer: '⚡',
    moderator: '🎯',
    user_input: '👤',
  };

  let colors = $derived(roleColors[data.role] || roleColors.strategist);
  let icon = $derived(data.icon || roleIcons[data.role] || '⚙️');
  let isLinked = $derived(!!data.blueprintId);

  // Execution status: 'idle' | 'running' | 'completed' | 'failed' | 'paused'
  let execStatus = $derived(data.executionStatus || 'idle');

  let borderColor = $derived(() => {
    switch (execStatus) {
      case 'running': return '#3b82f6';
      case 'completed': return '#22c55e';
      case 'failed': return '#ef4444';
      case 'paused': return '#f59e0b';
      default: return colors.border;
    }
  });

  let statusIcon = $derived(() => {
    switch (execStatus) {
      case 'running': return '⏳';
      case 'completed': return '✅';
      case 'failed': return '❌';
      case 'paused': return '⏸️';
      default: return null;
    }
  });
</script>

<div
  class="workflow-node rounded-xl border-2 p-3 min-w-[180px] shadow-sm transition-all"
  class:opacity-60={data.isDraft}
  class:exec-running={execStatus === 'running'}
  class:exec-completed={execStatus === 'completed'}
  class:exec-failed={execStatus === 'failed'}
  class:exec-paused={execStatus === 'paused'}
  style="border-color: {borderColor()}; background: {colors.bg};"
  data-testid="node-workflow-{data.role}"
>
  <!-- Previous step input -->
  <Handle type="target" position={Position.Left} id="prev" class="port-sequence" />

  <div class="flex items-center gap-2 mb-1">
    <span class="text-lg">{icon}</span>
    <span class="font-bold text-sm" style="color: {borderColor()};">{data.label}</span>
    {#if statusIcon()}
      <span class="text-sm exec-status-icon">{statusIcon()}</span>
    {/if}
  </div>

  <div class="text-xs text-gray-500">
    {#if execStatus === 'running'}
      <span class="text-blue-500">⟳ {t('blueprint.node.running')}</span>
    {:else if execStatus === 'completed'}
      <span class="text-green-600">✓ {t('blueprint.node.completed')}</span>
    {:else if execStatus === 'failed'}
      <span class="text-red-500">✗ {t('blueprint.node.failed')}</span>
    {:else if execStatus === 'paused'}
      <span class="text-amber-500">⏸ {t('blueprint.node.paused')}</span>
    {:else if isLinked}
      <span class="text-green-600">✓ {t('blueprint.node.linked')}</span>
    {:else}
      <span class="text-gray-400">○ {t('blueprint.node.notLinked')}</span>
    {/if}
  </div>

  <!-- Next step output -->
  <Handle type="source" position={Position.Right} id="next" class="port-sequence" />

  <!-- Interjection input (for user_input / external input) -->
  {#if data.role === 'user_input'}
    <Handle type="target" position={Position.Bottom} id="interjection" />
  {/if}
</div>

<style>
  .exec-running {
    animation: pulse-border 1.5s ease-in-out infinite;
  }
  @keyframes pulse-border {
    0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
    50% { box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2); }
  }
  .exec-completed {
    box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.3);
  }
  .exec-failed {
    box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.3);
  }
  .exec-paused {
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.3);
  }
  .exec-status-icon {
    animation: none;
  }
</style>
