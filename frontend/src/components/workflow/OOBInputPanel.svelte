<script>
  /**
   * OOBInputPanel — Floating panel for submitting out-of-band inputs
   * during a running debate.
   */

  import { runtime, pendingOOBCount } from '../../lib/workflow/store.js';
  import { submitOOBInput } from '../../lib/workflow/oob.js';
  import { i18n } from '../../lib/i18n/index.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let content = $state('');
  let targetRole = $state('next');
  let urgency = $state('append');

  let roles = $derived([
    { value: 'next', label: t('oob.targetNext') },
    { value: 'strategist', label: t('oob.targetStrategist') },
    { value: 'critic', label: t('oob.targetCritic') },
    { value: 'optimizer', label: t('oob.targetOptimizer') },
    { value: 'moderator', label: t('oob.targetModerator') },
    { value: 'current_active', label: t('oob.targetCurrent') },
  ]);

  let rt = $derived($runtime);
  let pendingCount = $derived($pendingOOBCount);
  let isVisible = $derived(rt.status === 'running' || rt.status === 'waiting_for_user');

  function handleSubmit() {
    if (!content.trim()) return;

    const target = targetRole === 'next'
      ? { type: 'next_agent', currentAgentRole: getCurrentRole() }
      : targetRole === 'current_active'
        ? { type: 'current_active' }
        : { type: 'specific_agent', agentRole: targetRole, round: rt.currentRound };

    submitOOBInput({ content: content.trim(), target, urgency });
    content = '';
  }

  function getCurrentRole() {
    if (!rt.activeNodeId) return 'input';
    const match = rt.activeNodeId.match(/^(\w+)_r\d+$/);
    return match ? match[1] : 'input';
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSubmit();
    }
  }
</script>

{#if isVisible}
  <div class="oob-panel">
    <div class="panel-header">
      <span class="header-icon">💬</span>
      <span class="header-title">{t('oob.injectContext')}</span>
      {#if pendingCount > 0}
        <span class="pending-badge">{t('oob.pending', { count: pendingCount })}</span>
      {/if}
    </div>

    <textarea
      bind:value={content}
      onkeydown={handleKeydown}
      placeholder={t('oob.placeholder')}
      class="oob-textarea"
    ></textarea>

    <div class="oob-controls">
      <select bind:value={targetRole} class="oob-select">
        {#each roles as role}
          <option value={role.value}>{role.label}</option>
        {/each}
      </select>

      <select bind:value={urgency} class="oob-select">
        <option value="append">{t('oob.urgencyAppend')}</option>
        <option value="inject_now">{t('oob.urgencyInject')}</option>
      </select>
    </div>

    <button
      onclick={handleSubmit}
      disabled={!content.trim()}
      class="oob-submit"
      class:enabled={content.trim()}
    >
      {t('oob.submit')}
    </button>

    <p class="oob-hint">{t('oob.shortcut')}</p>

    {#if rt.status === 'waiting_for_user'}
      <div class="oob-warning">
        ⚠️ {t('oob.waitingWarning')}
      </div>
    {/if}
  </div>
{/if}

<style>
  .oob-panel {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 320px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.15);
    border: 1px solid #e5e7eb;
    padding: 16px;
    z-index: 50;
  }
  :global(.dark) .oob-panel {
    background: #1f2937;
    border-color: #374151;
  }
  .panel-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  .header-icon { font-size: 18px; }
  .header-title {
    font-size: 14px;
    font-weight: 600;
    color: #111827;
  }
  :global(.dark) .header-title { color: #f3f4f6; }
  .pending-badge {
    margin-left: auto;
    background: #f59e0b;
    color: white;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
  }
  .oob-textarea {
    width: 100%;
    min-height: 80px;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #d1d5db;
    font-size: 13px;
    resize: vertical;
    margin-bottom: 10px;
    background: white;
    color: #111827;
  }
  :global(.dark) .oob-textarea {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .oob-textarea:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2);
  }
  .oob-controls {
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
  }
  .oob-select {
    flex: 1;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid #d1d5db;
    font-size: 12px;
    background: white;
    color: #374151;
  }
  :global(.dark) .oob-select {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .oob-submit {
    width: 100%;
    padding: 10px;
    border-radius: 8px;
    border: none;
    font-size: 13px;
    font-weight: 600;
    cursor: not-allowed;
    background: #d1d5db;
    color: #6b7280;
    transition: all 0.2s ease;
  }
  .oob-submit.enabled {
    background: #3b82f6;
    color: white;
    cursor: pointer;
  }
  .oob-submit.enabled:hover {
    background: #2563eb;
  }
  .oob-hint {
    text-align: center;
    font-size: 10px;
    color: #9ca3af;
    margin: 6px 0 0 0;
  }
  .oob-warning {
    margin-top: 10px;
    padding: 8px 10px;
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 6px;
    font-size: 11px;
    color: #9a3412;
  }
  :global(.dark) .oob-warning {
    background: #451a03;
    border-color: #92400e;
    color: #fbbf24;
  }
</style>
