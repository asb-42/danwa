<script>
  /**
   * ExecutionPanel — Side panel for workflow execution control.
   *
   * Shows: current node, round counter, consensus score, elapsed time.
   * Buttons: Pause/Resume, Cancel.
   * Interjection input: text field + submit button.
   * Node output log: scrollable list of completed node outputs.
   */
  import { i18n } from '../../lib/i18n/index.js';
  import {
    startWorkflow,
    pauseWorkflow,
    resumeWorkflow,
    cancelWorkflow,
    submitInterjection,
    getWorkflowState,
  } from '../../lib/workflowExec.js';
  import { createWorkflowSSE } from '../../lib/workflowSSE.js';
  import { patchActiveWorkflowSession } from '../../lib/workflowSession.js';

  /**
   * @type {{
   *   workflowId?: string,
   *   sessionId?: string|null,
   *   context?: string,
   *   startOptions?: object,
   *   visible?: boolean,
   *   onclose?: Function,
   *   onNodeStatusUpdate?: Function
   * }}
   */
  let {
    workflowId = null,
    sessionId: initialSessionId = null,
    context = '',
    startOptions = {},
    visible = false,
    onclose = () => {},
    onNodeStatusUpdate = () => {},
  } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  // Execution state
  let sessionId = $state(null);
  let status = $state('idle'); // idle | running | paused | completed | failed | cancelled
  let currentNodeId = $state('');
  let currentRound = $state(0);
  let maxRounds = $state(10);
  let consensus = $state(0);
  let elapsedMs = $state(0);
  let nodeOutputs = $state([]);
  let interjectionText = $state('');
  let error = $state('');
  let cleanupSSE = $state(null);

  // Workflow state viewer
  let showState = $state(false);
  let stateData = $state(null);
  let isLoadingState = $state(false);

  // Elapsed time timer
  let startTime = $state(null);
  let timerInterval = $state(null);

  function startTimer() {
    startTime = Date.now();
    timerInterval = setInterval(() => {
      elapsedMs = Date.now() - startTime;
    }, 100);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }

  /** Connect SSE to a running workflow session. */
  function connectSSE(sid) {
    cleanupSSE = createWorkflowSSE(sid, {
      onWorkflowStarted: () => {
        status = 'running';
      },
      onNodeStart: (data) => {
        currentNodeId = data.node_id || '';
        onNodeStatusUpdate(data.node_id, 'running');
      },
      onNodeComplete: (data) => {
        nodeOutputs = [...nodeOutputs, {
          nodeId: data.node_id,
          nodeType: data.node_type,
          role: data.role,
          content: data.content,
          durationMs: data.duration_ms,
          round: data.round,
        }];
        onNodeStatusUpdate(data.node_id, 'completed');
        if (data.consensus !== undefined) {
          consensus = data.consensus;
        }
        if (data.round !== undefined) {
          currentRound = data.round;
        }
      },
      onNodeError: (data) => {
        error = data.error || 'Unknown error';
        status = 'failed';
        stopTimer();
        onNodeStatusUpdate(data.node_id, 'failed');
      },
      onWorkflowComplete: (data) => {
        status = 'completed';
        stopTimer();
        if (data.final_consensus !== undefined) {
          consensus = data.final_consensus;
        }
        patchActiveWorkflowSession('status', 'completed');
      },
      onNodeError: (data) => {
        error = data.error || 'Unknown error';
        status = 'failed';
        stopTimer();
        onNodeStatusUpdate(data.node_id, 'failed');
        patchActiveWorkflowSession('status', 'failed');
      },
      onWorkflowPaused: () => {
        status = 'paused';
      },
      onWorkflowResumed: () => {
        status = 'running';
      },
      onError: (err) => {
        console.error('[ExecutionPanel] SSE error:', err);
      },
    });
  }

  // Auto-start when initialSessionId is provided (workflow already started by parent)
  $effect(() => {
    if (initialSessionId && visible) {
      sessionId = initialSessionId;
      status = 'running';
      nodeOutputs = [];
      currentRound = 0;
      consensus = 0;
      elapsedMs = 0;
      startTimer();
      connectSSE(initialSessionId);
    }
  });

  // Start workflow execution
  async function handleStart() {
    if (!workflowId) return;
    error = '';
    status = 'running';
    nodeOutputs = [];
    currentRound = 0;
    consensus = 0;
    elapsedMs = 0;

    try {
      const result = await startWorkflow(
        workflowId,
        context || 'Workflow execution',
        { maxRounds: maxRounds, ...startOptions },
      );
      sessionId = result.session_id;
      startTimer();
      connectSSE(sessionId);
    } catch (err) {
      error = err.message || 'Failed to start workflow';
      status = 'failed';
      stopTimer();
    }
  }

  // Pause/Resume
  async function handlePauseResume() {
    if (!sessionId) return;
    try {
      if (status === 'running') {
        await pauseWorkflow(sessionId);
        status = 'paused';
      } else if (status === 'paused') {
        await resumeWorkflow(sessionId);
        status = 'running';
      }
    } catch (err) {
      error = err.message || 'Failed to toggle pause';
    }
  }

  // Cancel
  async function handleCancel() {
    if (!sessionId) return;
    try {
      await cancelWorkflow(sessionId);
      status = 'cancelled';
      stopTimer();
      if (cleanupSSE) cleanupSSE();
    } catch (err) {
      error = err.message || 'Failed to cancel';
    }
  }

  // Submit interjection
  async function handleInterject() {
    if (!sessionId || !interjectionText.trim()) return;
    try {
      await submitInterjection(sessionId, interjectionText.trim());
      interjectionText = '';
    } catch (err) {
      error = err.message || 'Failed to submit interjection';
    }
  }

  // View workflow state
  async function handleViewState() {
    if (!sessionId) return;
    isLoadingState = true;
    try {
      stateData = await getWorkflowState(sessionId);
      showState = true;
    } catch (err) {
      error = err.message || 'Failed to load state';
    } finally {
      isLoadingState = false;
    }
  }

  // Cleanup on unmount
  $effect(() => {
    return () => {
      stopTimer();
      if (cleanupSSE) cleanupSSE();
    };
  });
</script>

{#if visible}
  <div class="execution-panel" data-testid="execution-panel">
    <div class="panel-header">
      <h3 class="panel-title">🚀 {t('workflow.execution.title')}</h3>
      <button class="close-btn" onclick={onclose} title={t('workflow.execution.close')}>✕</button>
    </div>

    <!-- Status bar -->
    <div class="status-bar status-{status}">
      <span class="status-dot"></span>
      <span class="status-text">{t(`workflow.execution.status.${status}`)}</span>
      {#if sessionId}
        <span class="session-id">{sessionId}</span>
      {/if}
    </div>

    <!-- Metrics -->
    <div class="metrics-grid">
      <div class="metric">
        <span class="metric-label">{t('workflow.execution.round')}</span>
        <span class="metric-value">{currentRound}</span>
      </div>
      <div class="metric">
        <span class="metric-label">{t('workflow.execution.consensus')}</span>
        <span class="metric-value">{(consensus * 100).toFixed(0)}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">{t('workflow.execution.elapsed')}</span>
        <span class="metric-value">{formatDuration(elapsedMs)}</span>
      </div>
      <div class="metric">
        <span class="metric-label">{t('workflow.execution.currentNode')}</span>
        <span class="metric-value">{currentNodeId || '—'}</span>
      </div>
    </div>

    <!-- Control buttons -->
    <div class="controls">
      {#if status === 'idle'}
        <button class="btn btn-primary" onclick={handleStart} disabled={!workflowId}>
          ▶ {t('workflow.execution.start')}
        </button>
      {:else if status === 'running' || status === 'paused'}
        <button class="btn btn-secondary" onclick={handlePauseResume}>
          {#if status === 'running'}
            ⏸ {t('workflow.execution.pause')}
          {:else}
            ▶ {t('workflow.execution.resume')}
          {/if}
        </button>
        <button class="btn btn-danger" onclick={handleCancel}>
          ⏹ {t('workflow.execution.cancel')}
        </button>
      {/if}
    </div>

    <!-- Error display -->
    {#if error}
      <div class="error-box">
        <span class="error-icon">⚠️</span>
        <span class="error-text">{error}</span>
      </div>
    {/if}

    <!-- Interjection input -->
    {#if status === 'running' || status === 'paused'}
      <div class="interjection-section">
        <label for="exec-field-257" class="interjection-label">{t('workflow.execution.interjection')}</label>
        <div class="interjection-row">
          <input id="exec-field-257"
            type="text"
            class="interjection-input"
            bind:value={interjectionText}
            placeholder={t('workflow.execution.interjectionPlaceholder')}
            onkeydown={(e) => e.key === 'Enter' && handleInterject()}
          />
          <button class="btn btn-small" onclick={handleInterject} disabled={!interjectionText.trim()}>
            {t('workflow.execution.submit')}
          </button>
        </div>
      </div>
    {/if}

    <!-- Node output log -->
    {#if nodeOutputs.length > 0}
      <div class="output-section">
        <h4 class="output-title">{t('workflow.execution.nodeOutputs')}</h4>
        <div class="output-list">
          {#each nodeOutputs as output}
            <div class="output-item">
              <div class="output-header">
                <span class="output-role">{output.role || output.nodeType}</span>
                <span class="output-duration">{output.durationMs}ms</span>
              </div>
              <div class="output-content">{output.content}</div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- View State button -->
    {#if sessionId && (status === 'running' || status === 'paused' || status === 'completed' || status === 'failed')}
      <div class="state-section">
        <button
          class="btn btn-small btn-state"
          onclick={handleViewState}
          disabled={isLoadingState}
        >
          {isLoadingState ? '...' : t('workflow.execution.viewState')}
        </button>
        {#if showState && stateData}
          <details open class="state-details">
            <summary class="state-summary">{t('workflow.execution.currentState')}</summary>
            <pre class="state-json">{JSON.stringify(stateData, null, 2)}</pre>
          </details>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .execution-panel {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 360px;
    background: white;
    border-left: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    z-index: 20;
    overflow-y: auto;
    box-shadow: -4px 0 12px rgba(0, 0, 0, 0.05);
  }
  :global(.dark) .execution-panel {
    background: #1f2937;
    border-color: #374151;
    color: #e5e7eb;
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
    margin: 0;
  }
  .close-btn {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 16px;
    color: #9ca3af;
    padding: 4px;
  }
  .close-btn:hover { color: #374151; }
  :global(.dark) .close-btn { color: #9ca3af; }
  :global(.dark) .close-btn:hover { color: #e5e7eb; }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 500;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .status-idle .status-dot { background: #9ca3af; }
  .status-running .status-dot { background: #3b82f6; animation: blink 1s infinite; }
  .status-paused .status-dot { background: #f59e0b; }
  .status-completed .status-dot { background: #22c55e; }
  .status-failed .status-dot { background: #ef4444; }
  .status-cancelled .status-dot { background: #6b7280; }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .session-id {
    margin-left: auto;
    font-size: 10px;
    color: #9ca3af;
    font-family: monospace;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 12px 16px;
  }
  .metric {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .metric-label {
    font-size: 10px;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .metric-value {
    font-size: 16px;
    font-weight: 600;
    color: #374151;
  }
  :global(.dark) .metric-value { color: #e5e7eb; }

  .controls {
    display: flex;
    gap: 8px;
    padding: 8px 16px;
  }
  .btn {
    padding: 8px 16px;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  :global(.dark) .btn { border-color: #4b5563; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary {
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
  }
  .btn-primary:hover:not(:disabled) { background: #2563eb; }
  .btn-secondary {
    background: white;
    color: #374151;
  }
  .btn-secondary:hover:not(:disabled) { border-color: #3b82f6; }
  :global(.dark) .btn-secondary {
    background: #374151;
    color: #e5e7eb;
    border-color: #4b5563;
  }
  :global(.dark) .btn-secondary:hover:not(:disabled) { border-color: #60a5fa; }
  .btn-danger {
    background: white;
    color: #ef4444;
    border-color: #fecaca;
  }
  .btn-danger:hover:not(:disabled) { background: #fef2f2; }
  :global(.dark) .btn-danger {
    background: #374151;
    color: #f87171;
    border-color: #7f1d1d;
  }
  :global(.dark) .btn-danger:hover:not(:disabled) { background: #4b5563; }
  .btn-small {
    padding: 6px 12px;
    font-size: 11px;
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
  }

  .error-box {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 16px;
    margin: 0 16px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    font-size: 12px;
    color: #991b1b;
  }
  :global(.dark) .error-box {
    background: #450a0a;
    border-color: #7f1d1d;
    color: #fca5a5;
  }

  .interjection-section {
    padding: 12px 16px;
    border-top: 1px solid #f3f4f6;
  }
  :global(.dark) .interjection-section { border-color: #374151; }
  .interjection-label {
    font-size: 11px;
    font-weight: 500;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
    display: block;
  }
  .interjection-row {
    display: flex;
    gap: 6px;
  }
  .interjection-input {
    flex: 1;
    padding: 6px 10px;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    font-size: 12px;
    outline: none;
  }
  .interjection-input:focus { border-color: #3b82f6; }
  :global(.dark) .interjection-input {
    background: #111827;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  :global(.dark) .interjection-input:focus { border-color: #60a5fa; }

  .output-section {
    padding: 12px 16px;
    border-top: 1px solid #f3f4f6;
    flex: 1;
    overflow-y: auto;
  }
  :global(.dark) .output-section { border-color: #374151; }
  .output-title {
    font-size: 11px;
    font-weight: 500;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 8px 0;
  }
  .output-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .output-item {
    padding: 8px;
    background: #f9fafb;
    border-radius: 6px;
    border: 1px solid #f3f4f6;
  }
  :global(.dark) .output-item {
    background: #111827;
    border-color: #1f2937;
  }
  .output-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
  }
  .output-role {
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
  }
  :global(.dark) .output-role { color: #9ca3af; }
  .output-duration {
    font-size: 10px;
    color: #9ca3af;
  }
  .output-content {
    font-size: 12px;
    color: #374151;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 120px;
    overflow-y: auto;
  }
  :global(.dark) .output-content { color: #d1d5db; }

  .state-section {
    padding: 8px 16px;
    border-top: 1px solid #f3f4f6;
  }
  :global(.dark) .state-section { border-color: #374151; }
  .btn-state {
    background: #8b5cf6;
    border-color: #8b5cf6;
    color: white;
    width: 100%;
  }
  .btn-state:hover:not(:disabled) {
    background: #7c3aed;
  }
  .state-details {
    margin-top: 8px;
  }
  .state-summary {
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    cursor: pointer;
  }
  .state-json {
    margin-top: 6px;
    padding: 8px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    font-size: 11px;
    font-family: monospace;
    color: #374151;
    overflow-x: auto;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }
  :global(.dark) .state-json {
    background: #111827;
    border-color: #1f2937;
    color: #d1d5db;
  }
</style>
