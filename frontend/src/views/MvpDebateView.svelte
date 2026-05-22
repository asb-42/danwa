<script>
  import { i18n, formatNumber } from '../lib/i18n/index.js';
  import { getLLMProfiles } from '../lib/api.js';
  import { startMvpDebate } from '../lib/workflowExec.js';
  import { createWorkflowSSE } from '../lib/workflowSSE.js';
  import { activeProject } from '../lib/stores.js';

  let { navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const AGENTS = [
    { role: 'strategist', label: 'Strategist', icon: '\u{1F9E0}', color: '#3b82f6', desc: 'Develops logical argumentation structure' },
    { role: 'critic', label: 'Critic', icon: '\u{1F50D}', color: '#ef4444', desc: 'Identifies weaknesses and risks' },
    { role: 'optimizer', label: 'Optimizer', icon: '\u26A1', color: '#10b981', desc: 'Synthesizes strategy and criticism' },
    { role: 'moderator', label: 'Moderator', icon: '\u{1F3AF}', color: '#8b5cf6', desc: 'Evaluates consensus and scores' },
  ];

  let topic = $state('');
  let maxRounds = $state(5);
  let threshold = $state(0.9);
  let llmProfiles = $state([]);
  let llmAssignments = $state({});
  let isLoadingProfiles = $state(true);

  let sessionId = $state(null);
  let debateId = $state(null);
  let status = $state('idle');
  let currentNodeId = $state('');
  let currentRound = $state(0);
  let consensus = $state(0);
  let elapsedMs = $state(0);
  let nodeOutputs = $state([]);
  let nodeStatuses = $state({});
  let error = $state('');
  let cleanupSSE = $state(null);
  let llmAssignmentsResult = $state({});
  let totalTokens = $state(0);

  let startTime = $state(null);
  let timerInterval = $state(null);

  $effect(() => {
    getLLMProfiles()
      .then((profiles) => {
        llmProfiles = profiles;
        const defaults = {};
        for (const agent of AGENTS) {
          defaults[agent.role] = profiles[0]?.id || '';
        }
        llmAssignments = defaults;
      })
      .catch((err) => {
        error = `Failed to load LLM profiles: ${err.message}`;
      })
      .finally(() => {
        isLoadingProfiles = false;
      });
  });

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

  function renderMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/^### (.+)$/gm, '<h4>$1</h4>')
      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
      .replace(/^# (.+)$/gm, '<h2>$1</h2>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');
  }

  function connectSSE(sid) {
    cleanupSSE = createWorkflowSSE(sid, {
      onWorkflowStarted: () => {
        status = 'running';
      },
      onNodeStart: (data) => {
        currentNodeId = data.node_id || '';
        nodeStatuses = { ...nodeStatuses, [currentNodeId]: 'running' };
      },
      onNodeComplete: (data) => {
        nodeOutputs = [...nodeOutputs, {
          nodeId: data.node_id,
          nodeType: data.node_type,
          role: data.role,
          content: data.content,
          durationMs: data.duration_ms,
          round: data.round,
          tokensUsed: data.tokens_used || 0,
        }];
        nodeStatuses = { ...nodeStatuses, [data.node_id]: 'completed' };
        if (data.consensus !== undefined) consensus = data.consensus;
        if (data.round !== undefined) currentRound = data.round;
        totalTokens = nodeOutputs.reduce((sum, o) => sum + (o.tokensUsed || 0), 0);
      },
      onRoundUpdate: (data) => {
        currentRound = data.round || currentRound;
        consensus = data.consensus ?? consensus;
        totalTokens = data.total_tokens ?? totalTokens;
      },
      onConsensusReached: (data) => {
        consensus = data.score ?? consensus;
      },
      onNodeError: (data) => {
        error = data.error || 'Unknown error';
        status = 'failed';
        stopTimer();
        nodeStatuses = { ...nodeStatuses, [data.node_id]: 'failed' };
      },
      onWorkflowComplete: (data) => {
        status = 'completed';
        stopTimer();
        if (data.final_consensus !== undefined) consensus = data.final_consensus;
      },
      onWorkflowPaused: () => { status = 'paused'; },
      onWorkflowResumed: () => { status = 'running'; },
      onError: (err) => { console.error('[MvpDebateView] SSE error:', err); },
    });
  }

  async function handleStart() {
    if (!topic.trim()) return;
    error = '';
    status = 'running';
    nodeOutputs = [];
    nodeStatuses = {};
    currentRound = 0;
    consensus = 0;
    elapsedMs = 0;
    llmAssignmentsResult = {};
    totalTokens = 0;
    debateId = null;

    const profileMap = {};
    for (const agent of AGENTS) {
      profileMap[agent.role] = llmAssignments[agent.role] || '';
    }

    try {
      const result = await startMvpDebate({
        context: topic.trim(),
        maxRounds,
        threshold,
        llmProfileIds: profileMap,
        projectId: $activeProject?.id,
      });
      sessionId = result.session_id;
      debateId = result.debate_id;
      llmAssignmentsResult = result.llm_assignments || {};
      startTimer();
      connectSSE(sessionId);
    } catch (err) {
      error = err.message || 'Failed to start debate';
      status = 'failed';
      stopTimer();
    }
  }

  async function handleCancel() {
    if (!sessionId) return;
    try {
      const { cancelWorkflow } = await import('../lib/workflowExec.js');
      await cancelWorkflow(sessionId);
      status = 'cancelled';
      stopTimer();
      if (cleanupSSE) cleanupSSE();
    } catch (err) {
      error = err.message || 'Failed to cancel';
    }
  }

  function handleReset() {
    if (cleanupSSE) cleanupSSE();
    sessionId = null;
    debateId = null;
    status = 'idle';
    currentNodeId = '';
    currentRound = 0;
    consensus = 0;
    elapsedMs = 0;
    nodeOutputs = [];
    nodeStatuses = {};
    error = '';
    llmAssignmentsResult = {};
    totalTokens = 0;
    stopTimer();
  }

  $effect(() => {
    return () => {
      stopTimer();
      if (cleanupSSE) cleanupSSE();
    };
  });
</script>

<div class="mvp-debate-view" data-testid="mvp-debate-view">
  <div class="view-header">
    <h1 class="view-title">
      <span class="title-icon">🏛️</span>
      MVP Debate Canvas
    </h1>
    <p class="view-subtitle">4-agent debate with per-agent LLM profiles</p>
  </div>

  {#if status === 'idle'}
    <div class="config-section">
      <div class="form-group">
        <label for="mvp-topic" class="form-label">Debate Topic</label>
        <textarea
          id="mvp-topic"
          class="form-textarea"
          bind:value={topic}
          placeholder="Enter the topic or case to debate..."
          rows="3"
        ></textarea>
      </div>

      <div class="settings-row">
        <div class="form-group">
          <label for="mvp-rounds" class="form-label">Max Rounds</label>
          <input
            id="mvp-rounds"
            type="number"
            class="form-input"
            bind:value={maxRounds}
            min="1"
            max="50"
          />
        </div>
        <div class="form-group">
          <label for="mvp-threshold" class="form-label">Consensus Threshold</label>
          <input
            id="mvp-threshold"
            type="number"
            class="form-input"
            bind:value={threshold}
            min="0"
            max="1"
            step="0.05"
          />
        </div>
      </div>

      <div class="agent-nodes">
        {#each AGENTS as agent, idx}
          <div class="agent-node" style="border-top-color: {agent.color}">
            <div class="agent-header">
              <div class="agent-badge" style="background: {agent.color}20; color: {agent.color}">
                <span class="agent-icon">{agent.icon}</span>
                <span class="agent-label">{agent.label}</span>
              </div>
              {#if nodeStatuses[`node-${agent.role}`]}
                <span class="agent-status agent-status-{nodeStatuses[`node-${agent.role}`]}">
                  {nodeStatuses[`node-${agent.role}`]}
                </span>
              {/if}
            </div>
            <p class="agent-desc">{agent.desc}</p>
            <div class="agent-llm-select">
              <label for="llm-{agent.role}" class="select-label">LLM Profile</label>
              {#if isLoadingProfiles}
                <div class="select-loading">Loading profiles...</div>
              {:else}
                <select
                  id="llm-{agent.role}"
                  class="form-select"
                  bind:value={llmAssignments[agent.role]}
                >
                  {#each llmProfiles as profile}
                    <option value={profile.id}>{profile.name}</option>
                  {/each}
                </select>
              {/if}
            </div>
          </div>
          {#if idx < AGENTS.length - 1}
            <div class="agent-arrow">→</div>
          {/if}
        {/each}
      </div>

      {#if error}
        <div class="error-box" role="alert">
          <span class="error-icon">⚠️</span>
          <span class="error-text">{error}</span>
        </div>
      {/if}

      <div class="actions-row">
        <button
          class="btn btn-start"
          onclick={handleStart}
          disabled={!topic.trim() || isLoadingProfiles}
        >
          ▶ Start Debate
        </button>
      </div>
    </div>
    {:else}
    <div class="execution-section">
      <div class="status-bar status-{status}">
        <span class="status-dot"></span>
        <span class="status-text">{status}</span>
        {#if debateId}
          <span class="debate-id" title="Debate ID: {debateId}">ID: {debateId.substring(0, 12)}…</span>
        {/if}
        {#if sessionId}
          <span class="session-id">{sessionId}</span>
        {/if}
      </div>

      <div class="metrics-grid">
        <div class="metric">
          <span class="metric-label">Round</span>
          <span class="metric-value">{currentRound}/{maxRounds}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Consensus</span>
          <span class="metric-value">{(consensus * 100).toFixed(0)}%</span>
        </div>
        <div class="metric">
          <span class="metric-label">Elapsed</span>
          <span class="metric-value">{formatDuration(elapsedMs)}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Tokens</span>
          <span class="metric-value">{formatNumber(totalTokens)}</span>
        </div>
      </div>

      {#if Object.keys(llmAssignmentsResult).length > 0}
        <div class="llm-summary">
          <h4 class="llm-summary-title">LLM Assignments</h4>
          <div class="llm-assignments">
            {#each Object.entries(llmAssignmentsResult) as [role, profileId]}
              <span class="llm-assignment">
                <span class="llm-role">{role}</span>: <span class="llm-profile">{profileId}</span>
              </span>
            {/each}
          </div>
        </div>
      {/if}

      <div class="controls-row">
        {#if status === 'running'}
          <button class="btn btn-cancel" onclick={handleCancel}>
            ⏹ Cancel
          </button>
        {/if}
        {#if status === 'completed' || status === 'failed' || status === 'cancelled'}
          <button class="btn btn-reset" onclick={handleReset}>
            🔄 New Debate
          </button>
        {/if}
      </div>

      {#if nodeOutputs.length > 0}
        <div class="outputs-section">
          <h4 class="outputs-title">Agent Outputs ({nodeOutputs.length})</h4>
          <div class="outputs-list">
            {#each nodeOutputs as output}
              <div class="output-item">
                <div class="output-header">
                  <span class="output-role">{output.role || output.nodeType}</span>
                  <span class="output-meta">
                    {#if output.round}Round {output.round} · {/if}
                    {formatDuration(output.durationMs)} ·
                    {output.tokensUsed || 0} tokens
                  </span>
                </div>
                <div class="output-content markdown-rendered">{@html renderMarkdown(output.content)}</div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .mvp-debate-view {
    max-width: 960px;
    margin: 0 auto;
    padding: 24px;
  }

  .view-header {
    margin-bottom: 24px;
  }
  .view-title {
    font-size: 24px;
    font-weight: 700;
    color: #1f2937;
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 4px 0;
  }
  :global(.dark) .view-title { color: #e5e7eb; }
  .view-subtitle {
    font-size: 14px;
    color: #6b7280;
    margin: 0;
  }

  .config-section {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .form-label {
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .form-textarea {
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
    resize: vertical;
    outline: none;
    background: white;
    color: #1f2937;
  }
  :global(.dark) .form-textarea {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-textarea:focus { border-color: #3b82f6; }

  .form-input {
    padding: 8px 10px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    width: 100px;
    outline: none;
    background: white;
    color: #1f2937;
  }
  :global(.dark) .form-input {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-input:focus { border-color: #3b82f6; }

  .settings-row {
    display: flex;
    gap: 16px;
  }

  .agent-nodes {
    display: flex;
    flex-direction: column;
    gap: 0;
    align-items: center;
  }

  .agent-node {
    width: 100%;
    padding: 16px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    border-top: 3px solid;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  :global(.dark) .agent-node {
    background: #1f2937;
    border-color: #374151;
  }

  .agent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .agent-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
  }
  .agent-icon { font-size: 16px; }

  .agent-desc {
    font-size: 12px;
    color: #9ca3af;
    margin: 0;
  }

  .agent-llm-select {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .select-label {
    font-size: 11px;
    font-weight: 500;
    color: #6b7280;
  }
  .form-select {
    padding: 8px 10px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 13px;
    background: white;
    color: #1f2937;
    outline: none;
    cursor: pointer;
  }
  :global(.dark) .form-select {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-select:focus { border-color: #3b82f6; }
  .select-loading {
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
  }

  .agent-arrow {
    font-size: 20px;
    color: #9ca3af;
    padding: 4px 0;
  }

  .agent-status {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 4px;
  }
  .agent-status-running {
    background: #dbeafe;
    color: #1d4ed8;
  }
  .agent-status-completed {
    background: #dcfce7;
    color: #166534;
  }
  .agent-status-failed {
    background: #fee2e2;
    color: #991b1b;
  }

  .error-box {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 14px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    font-size: 13px;
    color: #991b1b;
  }
  :global(.dark) .error-box {
    background: #451a1a;
    border-color: #7f1d1d;
    color: #fca5a5;
  }

  .actions-row {
    display: flex;
    justify-content: center;
  }

  .btn {
    padding: 10px 24px;
    border-radius: 8px;
    border: none;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-start {
    background: #3b82f6;
    color: white;
  }
  .btn-start:hover:not(:disabled) { background: #2563eb; }
  .btn-cancel {
    background: #ef4444;
    color: white;
  }
  .btn-cancel:hover { background: #dc2626; }
  .btn-reset {
    background: #10b981;
    color: white;
  }
  .btn-reset:hover { background: #059669; }

  /* Execution section */
  .execution-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 500;
    border-radius: 8px;
    background: #f9fafb;
  }
  :global(.dark) .status-bar { background: #1f2937; }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .status-running .status-dot { background: #3b82f6; animation: blink 1s infinite; }
  .status-completed .status-dot { background: #22c55e; }
  .status-failed .status-dot { background: #ef4444; }
  .status-cancelled .status-dot { background: #6b7280; }
  .session-id {
    margin-left: auto;
    font-size: 11px;
    color: #9ca3af;
    font-family: monospace;
  }
  .debate-id {
    font-size: 11px;
    color: #7dd3fc;
    font-family: monospace;
    font-weight: 600;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }
  .metric {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 12px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }
  :global(.dark) .metric {
    background: #1f2937;
    border-color: #374151;
  }
  .metric-label {
    font-size: 10px;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .metric-value {
    font-size: 18px;
    font-weight: 600;
    color: #374151;
  }
  :global(.dark) .metric-value { color: #e5e7eb; }

  .llm-summary {
    padding: 12px 16px;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 8px;
  }
  :global(.dark) .llm-summary {
    background: #164e63;
    border-color: #155e75;
  }
  .llm-summary-title {
    font-size: 11px;
    font-weight: 600;
    color: #0369a1;
    text-transform: uppercase;
    margin: 0 0 6px 0;
  }
  :global(.dark) .llm-summary-title { color: #7dd3fc; }
  .llm-assignments {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .llm-assignment {
    font-size: 12px;
    font-family: monospace;
    color: #0c4a6e;
  }
  :global(.dark) .llm-assignment { color: #e0f2fe; }
  .llm-role { font-weight: 600; }
  .llm-profile { color: #6b7280; }
  :global(.dark) .llm-profile { color: #9ca3af; }

  .controls-row {
    display: flex;
    gap: 8px;
  }

  .outputs-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .outputs-title {
    font-size: 13px;
    font-weight: 600;
    color: #6b7280;
    margin: 0;
  }
  .outputs-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 500px;
    overflow-y: auto;
  }
  .output-item {
    padding: 12px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }
  :global(.dark) .output-item {
    background: #1f2937;
    border-color: #374151;
  }
  .output-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .output-role {
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
  }
  .output-meta {
    font-size: 11px;
    color: #9ca3af;
  }
  .output-content {
    font-size: 13px;
    color: #374151;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
  :global(.dark) .output-content { color: #d1d5db; }
  .output-content.markdown-rendered {
    white-space: normal;
  }
  .output-content.markdown-rendered :global(h2) {
    font-size: 15px;
    font-weight: 700;
    margin: 8px 0 4px;
  }
  .output-content.markdown-rendered :global(h3) {
    font-size: 14px;
    font-weight: 600;
    margin: 6px 0 3px;
  }
  .output-content.markdown-rendered :global(h4) {
    font-size: 13px;
    font-weight: 600;
    margin: 4px 0 2px;
  }
  .output-content.markdown-rendered :global(strong) {
    font-weight: 700;
  }
  .output-content.markdown-rendered :global(code) {
    background: #f3f4f6;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
    font-family: monospace;
  }
  :global(.dark) .output-content.markdown-rendered :global(code) {
    background: #374151;
  }
  .output-content.markdown-rendered :global(li) {
    margin-left: 16px;
    list-style-type: disc;
  }
</style>
