<script>
  /**
   * NodeDetailPanel — Shows detailed information about a selected workflow node.
   */
  import { tStore } from '../../../lib/i18n/index.js';

  /** @type {{ node: any, onclose?: () => void }} */
  let { node, onclose = () => {} } = $props();

  let t = $derived($tStore);

  function close() {
    onclose();
  }

  let nodeData = $derived(node?.data || {});
  let nodeType = $derived(node?.type || 'unknown');
</script>

<div class="detail-panel">
  <div class="panel-header">
    <h3 class="panel-title">
      {#if nodeType === 'agent'}
        🤖 {t('workflow.agent')}: {nodeData.role}
      {:else if nodeType === 'artifact'}
        📄 {t('workflow.artifact')}: {nodeData.artifactType}
      {:else if nodeType === 'user_action'}
        👤 {t('workflow.userAction')}
      {:else if nodeType === 'decision'}
        ⚖️ {t('workflow.decision')}
      {:else}
        📦 {t('workflow.node')}
      {/if}
    </h3>
    <button class="close-btn" onclick={close}>✕</button>
  </div>

  <div class="panel-body">
    <!-- Status -->
    <div class="detail-row">
      <span class="detail-label">{t('workflow.status')}</span>
      <span class="detail-value status-{nodeData.status || 'idle'}">
        {nodeData.status || 'idle'}
      </span>
    </div>

    <!-- Round -->
    {#if nodeData.round != null}
      <div class="detail-row">
        <span class="detail-label">{t('workflow.round')}</span>
        <span class="detail-value">{nodeData.round}</span>
      </div>
    {/if}

    <!-- Role -->
    {#if nodeData.role}
      <div class="detail-row">
        <span class="detail-label">{t('workflow.role')}</span>
        <span class="detail-value">{nodeData.role}</span>
      </div>
    {/if}

    <!-- Summary -->
    {#if nodeData.summary}
      <div class="detail-section">
        <span class="detail-label">{t('workflow.summary')}</span>
        <p class="detail-text">{nodeData.summary}</p>
      </div>
    {/if}

    <!-- Full content (for OOB) -->
    {#if nodeData.fullContent}
      <div class="detail-section">
        <span class="detail-label">{t('workflow.fullContent')}</span>
        <p class="detail-text">{nodeData.fullContent}</p>
      </div>
    {/if}

    <!-- Token count -->
    {#if nodeData.tokenCount}
      <div class="detail-row">
        <span class="detail-label">{t('workflow.tokens')}</span>
        <span class="detail-value">{nodeData.tokenCount}</span>
      </div>
    {/if}

    <!-- Requested by -->
    {#if nodeData.requestedBy}
      <div class="detail-row">
        <span class="detail-label">{t('workflow.requestedBy')}</span>
        <span class="detail-value">{nodeData.requestedBy}</span>
      </div>
    {/if}

    <!-- Feedback loop -->
    {#if nodeData.hasFeedbackLoop}
      <div class="detail-row">
        <span class="detail-label">{t('workflow.feedbackLoop')}</span>
        <span class="detail-value">🔄 Yes</span>
      </div>
    {/if}

    <!-- Execution path (for history nodes) -->
    {#if nodeData.executionPath}
      <div class="detail-section">
        <span class="detail-label">{t('workflow.executionPath')}</span>
        <div class="path-list">
          {#each nodeData.executionPath as step, i}
            <span class="path-step">{i + 1}. {step}</span>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .detail-panel {
    width: 280px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    margin-left: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  :global(.dark) .detail-panel {
    background: #1f2937;
    border-color: #374151;
  }
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
  }
  :global(.dark) .panel-header { border-color: #374151; }
  .panel-title {
    font-size: 14px;
    font-weight: 600;
    color: #111827;
    margin: 0;
  }
  :global(.dark) .panel-title { color: #f3f4f6; }
  .close-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: #9ca3af;
    font-size: 16px;
    padding: 4px;
  }
  .close-btn:hover { color: #374151; }
  :global(.dark) .close-btn:hover { color: #e5e7eb; }
  .panel-body {
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    max-height: 400px;
  }
  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .detail-label {
    font-size: 11px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
  }
  .detail-value {
    font-size: 13px;
    color: #111827;
    font-weight: 500;
  }
  :global(.dark) .detail-value { color: #e5e7eb; }
  .detail-value.status-active { color: #3b82f6; }
  .detail-value.status-completed { color: #10b981; }
  .detail-value.status-waiting { color: #f59e0b; }
  .detail-value.status-error { color: #ef4444; }
  .detail-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .detail-text {
    font-size: 12px;
    color: #374151;
    line-height: 1.5;
    margin: 0;
    word-break: break-word;
  }
  :global(.dark) .detail-text { color: #d1d5db; }
  .path-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .path-step {
    font-size: 11px;
    color: #6b7280;
    font-family: monospace;
  }
</style>
