<script>
  /**
   * WorkflowNode — Template for workflow step nodes.
   *
   * Used for Strategist, Critic, Optimizer, Moderator, and User Input
   * workflow steps. Displays role-based coloring, linked status,
   * and sequential I/O ports.
   */
  import { Handle, Position } from '@xyflow/svelte';
  import { i18n } from '../../../lib/i18n/index.js';

  /** @type {{ data: { role: string, label: string, isDraft: boolean, blueprintId?: string, icon?: string } }} */
  let { data } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

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
</script>

<div
  class="workflow-node rounded-xl border-2 p-3 min-w-[180px] shadow-sm transition-all"
  class:opacity-60={data.isDraft}
  style="border-color: {colors.border}; background: {colors.bg};"
  data-testid="node-workflow-{data.role}"
>
  <!-- Previous step input -->
  <Handle type="target" position={Position.LEFT} id="prev" />

  <div class="flex items-center gap-2 mb-1">
    <span class="text-lg">{icon}</span>
    <span class="font-bold text-sm" style="color: {colors.border};">{data.label}</span>
  </div>

  <div class="text-xs text-gray-500">
    {#if isLinked}
      <span class="text-green-600">✓ {t('blueprint.node.linked')}</span>
    {:else}
      <span class="text-gray-400">○ {t('blueprint.node.notLinked')}</span>
    {/if}
  </div>

  <!-- Next step output -->
  <Handle type="source" position={Position.RIGHT} id="next" />

  <!-- Interjection input (for user_input / external input) -->
  {#if data.role === 'user_input'}
    <Handle type="target" position={Position.BOTTOM} id="interjection" />
  {/if}
</div>
