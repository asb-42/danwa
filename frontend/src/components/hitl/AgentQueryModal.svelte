<script>
  /**
   * AgentQueryModal — Modal dialog shown when an agent asks the user a question.
   * Displays the agent's question, context, and allows the user to respond.
   */

  import { respondToQuery } from '../../lib/hitl.js';
  import { hitlStatus, showAgentQueryModal, currentAgentQuery } from '../../lib/stores/hitl.svelte.js';

  let { debateId = '' } = $props();

  let response = $state('');
  let isSubmitting = $state(false);
  let submitError = $state(null);

  let status = $derived($hitlStatus);
  let interrupt = $derived(status.active_interrupt);
  let query = $derived($currentAgentQuery);
  let isVisible = $derived($showAgentQueryModal && interrupt !== null);

  // Agent role display names and icons
  const agentIcons = {
    strategist: '🎯',
    critic: '🔍',
    optimizer: '⚡',
    moderator: '🏛️',
  };

  let agentIcon = $derived(agentIcons[interrupt?.agent_role] || '🤖');
  let agentRole = $derived(interrupt?.agent_role || 'Agent');
  let question = $derived(interrupt?.question || query?.question || '');
  let context = $derived(interrupt?.context || query?.context || '');
  let round = $derived(interrupt?.round || 0);
  let elapsed = $derived(interrupt?.elapsed_seconds || 0);

  function formatElapsed(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  }

  async function handleSubmit() {
    if (!response.trim() || isSubmitting || !interrupt) return;

    isSubmitting = true;
    submitError = null;

    try {
      await respondToQuery(debateId, {
        interrupt_id: interrupt.interrupt_id,
        response: response.trim(),
      });
      response = '';
      showAgentQueryModal.set(false);
    } catch (err) {
      submitError = err.message || 'Failed to send response';
    } finally {
      isSubmitting = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSubmit();
    }
    if (e.key === 'Escape') {
      // Don't close — agent is waiting
    }
  }

  function handleSkip() {
    // Close modal without responding (agent will timeout)
    showAgentQueryModal.set(false);
  }
</script>

{#if isVisible}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-label="Agent query">
    <div class="modal-content" role="presentation">
      <div class="modal-header">
        <div class="agent-info">
          <span class="agent-icon">{agentIcon}</span>
          <div class="agent-details">
            <span class="agent-role">{agentRole}</span>
            <span class="round-info">Round {round}</span>
          </div>
        </div>
        <div class="header-meta">
          <span class="elapsed" title="Time waiting">⏱️ {formatElapsed(elapsed)}</span>
        </div>
      </div>

      <div class="modal-body">
        <div class="question-section">
          <h3 class="question-label">Agent's Question</h3>
          <div class="question-text">{question}</div>
        </div>

        {#if context}
          <div class="context-section">
            <h3 class="context-label">Context</h3>
            <div class="context-text">{context}</div>
          </div>
        {/if}

        <div class="response-section">
          <h3 class="response-label">Your Response</h3>
          <textarea
            bind:value={response}
            onkeydown={handleKeydown}
            placeholder="Type your response to the agent's question..."
            class="response-textarea resize-y"
            rows="4"
            disabled={isSubmitting}
            autofocus
          ></textarea>
          <div class="response-hint">Ctrl+Enter to send</div>
        </div>

        {#if submitError}
          <div class="modal-error" role="alert">{submitError}</div>
        {/if}
      </div>

      <div class="modal-footer">
        <button class="btn-skip" onclick={handleSkip} disabled={isSubmitting}>
          Skip (agent will timeout)
        </button>
        <button
          class="btn-send"
          onclick={handleSubmit}
          disabled={!response.trim() || isSubmitting}
        >
          {#if isSubmitting}
            <span class="spinner"></span> Sending...
          {:else}
            📤 Send Response
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .modal-content {
    background: var(--color-surface, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 12px;
    width: 100%;
    max-width: 600px;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
    animation: slideUp 0.2s ease;
  }

  @keyframes slideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border, #313244);
  }

  .agent-info {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .agent-icon {
    font-size: 1.5rem;
  }

  .agent-details {
    display: flex;
    flex-direction: column;
  }

  .agent-role {
    font-weight: 600;
    font-size: 1rem;
    color: var(--color-text, #cdd6f4);
    text-transform: capitalize;
  }

  .round-info {
    font-size: 0.75rem;
    color: var(--color-text-muted, #a6adc8);
  }

  .elapsed {
    font-size: 0.8rem;
    color: var(--color-text-muted, #a6adc8);
  }

  .modal-body {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .question-section, .context-section, .response-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .question-label, .context-label, .response-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--color-text-muted, #a6adc8);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0;
  }

  .question-text {
    padding: 12px 16px;
    background: rgba(137, 180, 250, 0.08);
    border: 1px solid rgba(137, 180, 250, 0.2);
    border-radius: 8px;
    color: var(--color-text, #cdd6f4);
    font-size: 0.95rem;
    line-height: 1.6;
  }

  .context-text {
    padding: 10px 14px;
    background: var(--color-input-bg, #181825);
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    color: var(--color-text-muted, #a6adc8);
    font-size: 0.8rem;
    line-height: 1.5;
    max-height: 120px;
    overflow-y: auto;
    white-space: pre-wrap;
  }

  .response-textarea {
    width: 100%;
    padding: 12px;
    background: var(--color-input-bg, #181825);
    border: 1px solid var(--color-border, #313244);
    border-radius: 8px;
    color: var(--color-text, #cdd6f4);
    font-size: 0.9rem;
    font-family: inherit;
    line-height: 1.5;
    resize: vertical;
    min-height: 80px;
  }

  .response-textarea:focus {
    outline: none;
    border-color: var(--color-primary, #89b4fa);
    box-shadow: 0 0 0 2px rgba(137, 180, 250, 0.15);
  }

  .response-hint {
    font-size: 0.7rem;
    color: var(--color-text-muted, #a6adc8);
    text-align: right;
  }

  .modal-error {
    padding: 10px 14px;
    background: rgba(243, 139, 168, 0.1);
    border: 1px solid rgba(243, 139, 168, 0.3);
    border-radius: 6px;
    color: #f38ba8;
    font-size: 0.85rem;
  }

  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-top: 1px solid var(--color-border, #313244);
  }

  .btn-skip {
    padding: 8px 16px;
    background: none;
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    color: var(--color-text-muted, #a6adc8);
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-skip:hover:not(:disabled) {
    border-color: var(--color-text-muted, #a6adc8);
    color: var(--color-text, #cdd6f4);
  }

  .btn-send {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    background: var(--color-primary, #89b4fa);
    color: var(--color-bg, #1e1e2e);
    border: none;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-send:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-send:disabled {
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
</style>
