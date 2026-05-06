<script>
  /**
   * InjectPanel — Allows users to inject context into a running debate.
   * Non-blocking: the debate continues while the injection is queued.
   * Shows persistent feedback with injection history.
   */

  import { injectContext } from '../../lib/hitl.js';
  import { hitlStatus, hitlInteractions } from '../../lib/stores/hitl.svelte.js';

  let { debateId = '', agentRoles = [] } = $props();

  let content = $state('');
  let targetAgent = $state('');
  let priority = $state('normal');
  let isSubmitting = $state(false);
  let submitError = $state(null);
  let submitSuccess = $state(false);
  let isExpanded = $state(false);

  let status = $derived($hitlStatus);
  let isRunning = $derived(status.hitl_enabled && !status.is_paused);

  // Track recent inject interactions from the store
  let recentInjections = $derived(
    ($hitlInteractions || [])
      .filter(i => i.type === 'inject')
      .slice(-5)
      .reverse()
  );

  const priorities = [
    { value: 'low', label: 'Low', icon: '⬇️' },
    { value: 'normal', label: 'Normal', icon: '➡️' },
    { value: 'high', label: 'High', icon: '⬆️' },
    { value: 'urgent', label: 'Urgent', icon: '🔴' },
  ];

  async function handleSubmit() {
    if (!content.trim() || isSubmitting) return;

    isSubmitting = true;
    submitError = null;
    submitSuccess = false;

    try {
      await injectContext(debateId, {
        content: content.trim(),
        target_agent: targetAgent || null,
        priority,
      });
      content = '';
      submitSuccess = true;
      setTimeout(() => { submitSuccess = false; }, 3000);
    } catch (err) {
      submitError = err.message || 'Failed to inject context';
    } finally {
      isSubmitting = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSubmit();
    }
  }

  function toggleExpanded() {
    isExpanded = !isExpanded;
  }

  function truncate(text, maxLen = 80) {
    if (!text || text.length <= maxLen) return text;
    return text.slice(0, maxLen) + '…';
  }

  function formatTime(timestamp) {
    if (!timestamp) return '';
    try {
      return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return timestamp;
    }
  }
</script>

{#if isRunning}
  <div class="inject-panel" class:expanded={isExpanded}>
    <button class="inject-header" onclick={toggleExpanded} aria-expanded={isExpanded}>
      <span class="header-icon">💉</span>
      <span class="header-title">Inject Context</span>
      <span class="header-chevron" class:rotated={isExpanded}>▼</span>
    </button>

    {#if isExpanded}
      <div class="inject-body">
        <textarea
          bind:value={content}
          onkeydown={handleKeydown}
          placeholder="Type context or information to inject into the debate..."
          class="inject-textarea resize-y"
          rows="3"
          disabled={isSubmitting}
        ></textarea>

        <div class="inject-controls">
          <div class="control-row">
            <label class="control-label">
              Target Agent
              <select bind:value={targetAgent} class="inject-select">
                <option value="">All agents</option>
                {#each agentRoles as role}
                  <option value={role}>{role}</option>
                {/each}
              </select>
            </label>

            <label class="control-label">
              Priority
              <select bind:value={priority} class="inject-select">
                {#each priorities as p}
                  <option value={p.value}>{p.icon} {p.label}</option>
                {/each}
              </select>
            </label>
          </div>

          <div class="control-row">
            <span class="hint">Ctrl+Enter to submit</span>
            <button
              class="inject-submit"
              onclick={handleSubmit}
              disabled={!content.trim() || isSubmitting}
            >
              {#if isSubmitting}
                <span class="spinner"></span> Sending...
              {:else}
                💉 Inject
              {/if}
            </button>
          </div>
        </div>

        {#if submitError}
          <div class="inject-error" role="alert">{submitError}</div>
        {/if}

        {#if submitSuccess}
          <div class="inject-success" role="status">✓ Context injected successfully</div>
        {/if}

        {#if recentInjections.length > 0}
          <div class="recent-injections">
            <div class="recent-header">Recent injections</div>
            {#each recentInjections as inj (inj.interaction_id)}
              <div class="recent-item" class:consumed={inj.status === 'consumed'}>
                <span class="recent-status" class:status-pending={inj.status === 'pending'} class:status-consumed={inj.status === 'consumed'}>
                  {inj.status === 'consumed' ? '✅' : '⏳'}
                </span>
                <span class="recent-text">{truncate(inj.content)}</span>
                <span class="recent-time">{formatTime(inj.timestamp)}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .inject-panel {
    background: var(--color-surface, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 8px;
    overflow: hidden;
    transition: all 0.2s ease;
  }

  .inject-panel.expanded {
    border-color: var(--color-primary, #89b4fa);
  }

  .inject-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 10px 14px;
    background: none;
    border: none;
    color: var(--color-text, #cdd6f4);
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    transition: background 0.15s;
  }

  .inject-header:hover {
    background: var(--color-surface-hover, #252536);
  }

  .header-icon {
    font-size: 1.1rem;
  }

  .header-title {
    flex: 1;
    text-align: left;
  }

  .header-chevron {
    font-size: 0.75rem;
    transition: transform 0.2s;
  }

  .header-chevron.rotated {
    transform: rotate(180deg);
  }

  .inject-body {
    padding: 0 14px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .inject-textarea {
    width: 100%;
    padding: 10px;
    background: var(--color-input-bg, #181825);
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    color: var(--color-text, #cdd6f4);
    font-size: 0.85rem;
    font-family: inherit;
    line-height: 1.5;
    resize: vertical;
    min-height: 60px;
  }

  .inject-textarea:focus {
    outline: none;
    border-color: var(--color-primary, #89b4fa);
    box-shadow: 0 0 0 2px rgba(137, 180, 250, 0.15);
  }

  .inject-textarea:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .inject-controls {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .control-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .control-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 0.8rem;
    color: var(--color-text-muted, #a6adc8);
    flex: 1;
  }

  .inject-select {
    padding: 6px 8px;
    background: var(--color-input-bg, #181825);
    border: 1px solid var(--color-border, #313244);
    border-radius: 4px;
    color: var(--color-text, #cdd6f4);
    font-size: 0.8rem;
  }

  .hint {
    font-size: 0.75rem;
    color: var(--color-text-muted, #a6adc8);
  }

  .inject-submit {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: var(--color-primary, #89b4fa);
    color: var(--color-bg, #1e1e2e);
    border: none;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .inject-submit:hover:not(:disabled) {
    opacity: 0.9;
  }

  .inject-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(30, 30, 46, 0.3);
    border-top-color: var(--color-bg, #1e1e2e);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .inject-error {
    padding: 8px 12px;
    background: rgba(243, 139, 168, 0.1);
    border: 1px solid rgba(243, 139, 168, 0.3);
    border-radius: 4px;
    color: #f38ba8;
    font-size: 0.8rem;
  }

  .inject-success {
    padding: 8px 12px;
    background: rgba(166, 227, 161, 0.1);
    border: 1px solid rgba(166, 227, 161, 0.3);
    border-radius: 4px;
    color: #a6e3a1;
    font-size: 0.8rem;
  }

  .recent-injections {
    margin-top: 8px;
    border-top: 1px solid var(--color-border, #313244);
    padding-top: 8px;
  }

  .recent-header {
    font-size: 0.75rem;
    color: var(--color-text-muted, #a6adc8);
    margin-bottom: 6px;
    font-weight: 500;
  }

  .recent-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 0;
    font-size: 0.78rem;
    color: var(--color-text-muted, #a6adc8);
  }

  .recent-item.consumed {
    opacity: 0.7;
  }

  .recent-status {
    flex-shrink: 0;
    font-size: 0.7rem;
  }

  .recent-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .recent-time {
    flex-shrink: 0;
    font-size: 0.7rem;
    color: var(--color-text-muted, #a6adc8);
    opacity: 0.7;
  }
</style>
