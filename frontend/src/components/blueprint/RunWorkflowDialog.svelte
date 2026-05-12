<script>
  /**
   * RunWorkflowDialog — Collects debate parameters before starting a workflow.
   *
   * Fields: topic/case description, language, max rounds, consensus threshold.
   * On confirm, calls the onstart callback with the collected parameters.
   */
  import { i18n } from '../../lib/i18n/index.js';

  /** @type {{ visible?: boolean, layoutName?: string, onstart?: Function, onclose?: Function }} */
  let {
    visible = false,
    layoutName = '',
    onstart = () => {},
    onclose = () => {},
  } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let topic = $state('');
  let language = $state('de');
  let maxRounds = $state(5);
  let consensusThreshold = $state(0.9);
  let error = $state('');
  let isStarting = $state(false);

  function handleConfirm() {
    if (!topic.trim()) {
      error = t('blueprint.workflow.topicRequired');
      return;
    }
    error = '';
    isStarting = true;
    try {
      onstart({
        topic: topic.trim(),
        language,
        maxRounds,
        consensusThreshold,
      });
    } catch (err) {
      error = err.message || 'Failed to start';
    } finally {
      isStarting = false;
    }
  }

  function handleCancel() {
    topic = '';
    error = '';
    onclose();
  }

  // Reset form when dialog opens
  $effect(() => {
    if (visible) {
      topic = '';
      language = 'de';
      maxRounds = 5;
      consensusThreshold = 0.9;
      error = '';
      isStarting = false;
    }
  });
</script>

{#if visible}
  <div
    class="dialog-overlay"
    role="button"
    tabindex="-1"
    onclick={handleCancel}
    onkeydown={(e) => { if (e.key === 'Escape') handleCancel(); }}
  >
    <div
      class="dialog dialog-wide"
      role="dialog"
      aria-modal="true"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => { if (e.key === 'Enter' && !isStarting) handleConfirm(); }}
    >
      <h3 class="dialog-title">▶️ {t('blueprint.workflow.runDebate')}</h3>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
        {t('blueprint.workflow.runDebateHint')}
      </p>

      {#if error}
        <p class="dialog-error">{error}</p>
      {/if}

      <label class="dialog-field">
        <span class="dialog-label">{t('blueprint.workflow.topic')}</span>
        <textarea
          bind:value={topic}
          class="dialog-input dialog-textarea"
          placeholder={t('blueprint.workflow.topicPlaceholder')}
          rows="3"
          data-testid="run-workflow-topic"
        ></textarea>
      </label>

      <label class="dialog-field">
        <span class="dialog-label">{t('blueprint.workflow.language')}</span>
        <select bind:value={language} class="dialog-input" data-testid="run-workflow-language">
          <option value="de">Deutsch</option>
          <option value="en">English</option>
        </select>
      </label>

      <div class="grid grid-cols-2 gap-3 mb-4">
        <label class="dialog-field">
          <span class="dialog-label">{t('blueprint.workflow.maxRounds')}</span>
          <input
            type="number"
            bind:value={maxRounds}
            min="1"
            max="50"
            class="dialog-input"
            data-testid="run-workflow-max-rounds"
          />
        </label>
        <label class="dialog-field">
          <span class="dialog-label">{t('blueprint.workflow.consensusThreshold')}</span>
          <input
            type="number"
            bind:value={consensusThreshold}
            min="0"
            max="1"
            step="0.05"
            class="dialog-input"
            data-testid="run-workflow-consensus"
          />
        </label>
      </div>

      <div class="dialog-actions">
        <button class="dialog-btn-cancel" onclick={handleCancel}>
          {t('blueprint.inspector.cancel')}
        </button>
        <button
          class="dialog-btn-save dialog-btn-run"
          onclick={handleConfirm}
          disabled={isStarting || !topic.trim()}
          data-testid="run-workflow-confirm"
        >
          {#if isStarting}
            <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block mr-1"></span>
          {/if}
          ▶ {t('blueprint.workflow.startDebate')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .dialog {
    background: white;
    border-radius: 12px;
    padding: 24px;
    width: 360px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
  }
  .dialog-wide { width: 440px; }
  :global(.dark) .dialog { background: #1f2937; }
  .dialog-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2937;
    margin-bottom: 16px;
  }
  :global(.dark) .dialog-title { color: #e5e7eb; }
  .dialog-error {
    font-size: 12px;
    color: #ef4444;
    margin-bottom: 8px;
  }
  .dialog-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 16px;
  }
  .dialog-label {
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
  }
  .dialog-input {
    padding: 8px 10px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
  }
  .dialog-textarea {
    resize: vertical;
    min-height: 60px;
  }
  :global(.dark) .dialog-input {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .dialog-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  .dialog-btn-cancel {
    padding: 8px 16px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    background: transparent;
    color: #6b7280;
    font-size: 13px;
    cursor: pointer;
  }
  .dialog-btn-save {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    background: #3b82f6;
    color: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  .dialog-btn-save:hover { background: #2563eb; }
  .dialog-btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
  .dialog-btn-run {
    background: #10b981;
  }
  .dialog-btn-run:hover { background: #059669; }
</style>
