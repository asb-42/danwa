<script>
  import { i18n, formatNumber } from '../lib/i18n/index.js';
  import { getLLMProfiles, getDebate, getDocuments } from '../lib/api.js';
  import { startMvpDebate, submitInterjection, getAgentCores, getCompositionComponents } from '../lib/workflowExec.js';
  import { createWorkflowSSE } from '../lib/workflowSSE.js';
  import { activeProject, userLanguage } from '../lib/stores.js';

  import { getHITLStatus, getInteractions } from '../lib/hitl.js';
  import { hitlStatus, hitlInteractions, showAgentQueryModal, currentAgentQuery } from '../lib/stores/hitl.svelte.js';
  import InjectPanel from '../components/hitl/InjectPanel.svelte';
  import PauseControls from '../components/hitl/PauseControls.svelte';
  import AgentQueryModal from '../components/hitl/AgentQueryModal.svelte';
  import InteractionTimeline from '../components/hitl/InteractionTimeline.svelte';

  let { debateId: externalDebateId = null, navigate = () => {} } = $props();

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
  let isLoadingDebate = $state(false);

  // Composition selection (Phase 2 — 4 component types)
  let agentCores = $state([]);
  let argumentationPatterns = $state([]);
  let toneProfiles = $state([]);
  let promptModifiers = $state([]);
  let agentCoreAssignments = $state({});
  let argumentationPatternAssignments = $state({});
  let toneProfileAssignments = $state({});
  let promptModifierAssignments = $state({});
  let isLoadingComponents = $state(true);

  // New config fields
  let searchMode = $state('off');
  let availableDocuments = $state([]);
  let selectedDocumentIds = $state([]);
  let ragAutoRetrieve = $state(false);
  let includeDebateResults = $state(false);

  // Interjection
  let interjectionText = $state('');
  let sendingInterjection = $state(false);
  let interjectionFeedback = $state('');      // Visual feedback for submitted interjections
  let consumedInterjections = $state([]);     // Interjections consumed by agents

  // Confirmation page
  let showConfirm = $state(false);

  let sessionId = $state(null);
  let debateId = $state(null);
  let debateTitle = $state('');
  let status = $state('idle');
  let currentNodeId = $state('');
  let currentRound = $state(0);
  let consensus = $state(0);
  let hasReceivedConsensus = $state(false);
  let elapsedMs = $state(0);
  let nodeOutputs = $state([]);
  let nodeStatuses = $state({});
  let error = $state('');
  let cleanupSSE = null;
  let llmAssignmentsResult = $state({});
  let totalTokens = $state(0);
  let expandedOutputs = $state(new Set());
  let activityText = $state('');

  let startTime = null;           // not reactive — internal timer bookkeeping
  let timerInterval = null;       // not reactive — internal timer bookkeeping
  let hitlPollTimer = null;       // not reactive — polling interval ID, would create $effect loop

  $effect(() => {
    // Load LLM profiles and all composition components in parallel
    Promise.all([
      getLLMProfiles(),
      getCompositionComponents(),
    ])
      .then(([profiles, components]) => {
        llmProfiles = profiles;
        const defaults = {};
        for (const agent of AGENTS) {
          defaults[agent.role] = profiles[0]?.id || '';
        }
        llmAssignments = defaults;

        // Composition components
        agentCores = components.agent_cores || [];
        argumentationPatterns = components.argumentation_patterns || [];
        toneProfiles = components.tone_profiles || [];
        promptModifiers = components.prompt_modifiers || [];

        // Default: empty strings = use built-in defaults
        const emptyDefaults = {};
        for (const agent of AGENTS) {
          emptyDefaults[agent.role] = '';
        }
        agentCoreAssignments = { ...emptyDefaults };
        argumentationPatternAssignments = { ...emptyDefaults };
        toneProfileAssignments = { ...emptyDefaults };
        promptModifierAssignments = { ...emptyDefaults };
      })
      .catch((err) => {
        error = `Failed to load profiles: ${err.message}`;
      })
      .finally(() => {
        isLoadingProfiles = false;
        isLoadingComponents = false;
      });
  });

  // Load available DMS documents for document selection
  $effect(() => {
    getDocuments()
      .then((docs) => { availableDocuments = docs; })
      .catch(() => { availableDocuments = []; });
  });

  // Load existing debate when externalDebateId is provided
  $effect(() => {
    const eid = externalDebateId;
    if (!eid) return;

    isLoadingDebate = true;
    error = '';
    status = 'loading';

    (async () => {
      try {
        const debate = await getDebate(eid);
        debateId = debate.debate_id;
        debateTitle = debate.title || '';
        topic = debate.case_text || '';
        maxRounds = debate.max_rounds || 5;
        threshold = debate.consensus_score ?? 0.9;
        status = debate.status;
        currentRound = debate.current_round || 0;
        if (debate.consensus_score !== null && debate.consensus_score !== undefined) {
          consensus = debate.consensus_score;
          hasReceivedConsensus = true;
        }

        if (debate.session_id) {
          sessionId = debate.session_id;

          // For completed/cancelled/failed debates, load the state snapshot
          if (debate.status === 'completed' || debate.status === 'cancelled' || debate.status === 'failed') {
            const { getWorkflowState } = await import('../lib/workflowExec.js');
            try {
              const state = await getWorkflowState(debate.session_id);
              if (state.node_outputs) {
                nodeOutputs = state.node_outputs;
                totalTokens = state.node_outputs.reduce((sum, o) => sum + (o.tokensUsed || 0), 0);
              }
              if (state.final_consensus !== undefined && state.final_consensus !== null) {
                consensus = state.final_consensus;
              }
              if (state.current_round) currentRound = state.current_round;
            } catch (_) {
              // state may not be available for old sessions
            }
            isLoadingDebate = false;
            return;
          }

          // For running debates, connect SSE
          if (debate.status === 'running' || debate.status === 'paused') {
            const { getWorkflowState } = await import('../lib/workflowExec.js');
            try {
              const state = await getWorkflowState(debate.session_id);
              if (state.node_outputs) {
                nodeOutputs = state.node_outputs;
              }
              if (state.current_round) currentRound = state.current_round;
            } catch (_) { /* ok */ }
            startTimer();
            connectSSE(debate.session_id);
          }
        }
      } catch (err) {
        error = `Failed to load debate: ${err.message}`;
        status = 'failed';
      } finally {
        isLoadingDebate = false;
      }
    })();
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

  function getProfileName(profileId) {
    const profile = llmProfiles.find(p => p.id === profileId);
    return profile ? profile.name : profileId;
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
        try {
          currentNodeId = data.node_id || '';
          const agentLabel = AGENTS.find(a => a.role === data.role)?.label || data.role;
          activityText = `${agentLabel} starting…`;
          nodeStatuses = { ...nodeStatuses, [currentNodeId]: 'running' };
        } catch (e) { console.warn('[MvpDebateView] onNodeStart error:', e); }
      },
      onLLMCallStarted: (data) => {
        try {
          const agentLabel = AGENTS.find(a => a.role === data.role)?.label || data.role;
          const llmName = getProfileName(data.llm_profile_id);
          activityText = `🧠 ${agentLabel} → ${llmName} (Round ${data.round || currentRound})…`;
        } catch (e) { console.warn('[MvpDebateView] onLLMCallStarted error:', e); }
      },
      onWebSearch: (data) => {
        try {
          activityText = `🔍 Searching: ${data.query || ''}…`;
        } catch (e) { console.warn('[MvpDebateView] onWebSearch error:', e); }
      },
      onNodeComplete: (data) => {
        try {
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
          if (data.consensus !== undefined) { consensus = data.consensus; hasReceivedConsensus = true; }
          if (data.round !== undefined) currentRound = data.round;
          totalTokens = nodeOutputs.reduce((sum, o) => sum + (o.tokensUsed || 0), 0);
          const agentLabel = AGENTS.find(a => a.role === data.role)?.label || data.role;
          activityText = `✓ ${agentLabel} completed (${formatDuration(data.duration_ms)}, ${data.tokens_used || 0} tokens)`;
        } catch (e) { console.warn('[MvpDebateView] onNodeComplete error:', e); }
      },
      onRoundUpdate: (data) => {
        currentRound = data.round || currentRound;
        if (data.consensus !== undefined && data.consensus !== null) {
          consensus = data.consensus;
          hasReceivedConsensus = true;
        }
        totalTokens = data.total_tokens ?? totalTokens;
      },
      onConsensusReached: (data) => {
        if (data.score !== undefined && data.score !== null) {
          consensus = data.score;
          hasReceivedConsensus = true;
        }
      },
      onNodeError: (data) => {
        error = data.error || 'Unknown error';
        status = 'failed';
        stopTimer();
        activityText = '';
        nodeStatuses = { ...nodeStatuses, [data.node_id]: 'failed' };
      },
      onWorkflowComplete: (data) => {
        status = 'completed';
        stopTimer();
        activityText = '';
        if (data.final_consensus !== undefined) { consensus = data.final_consensus; hasReceivedConsensus = true; }
        // Proactively close SSE to prevent stale connections from freezing the UI
        if (cleanupSSE) { cleanupSSE(); cleanupSSE = null; }
      },
      onWorkflowPaused: () => { status = 'paused'; },
      onWorkflowResumed: () => { status = 'running'; },
      onError: (err) => { console.error('[MvpDebateView] SSE error:', err); },
      // HITL event handlers
      onHITLQuery: (data) => {
        currentAgentQuery.set({
          interrupt_id: data.interrupt_id,
          agent_role: data.agent_role,
          question: data.question,
          context: data.context || '',
          confidence: data.confidence,
          reason: data.reason,
          round: data.round,
        });
        hitlStatus.update(status => ({
          ...status,
          active_interrupt: {
            interrupt_id: data.interrupt_id,
            agent_role: data.agent_role,
            question: data.question,
            context: data.context || '',
            round: data.round,
            created_at: new Date().toISOString(),
            timeout_seconds: 300,
            status: 'waiting',
            elapsed_seconds: 0,
          },
        }));
        showAgentQueryModal.set(true);
        refreshHITLStatus();
      },
      onHITLResponse: () => {
        showAgentQueryModal.set(false);
        currentAgentQuery.set(null);
        refreshHITLStatus();
        refreshHITLInteractions();
      },
      onInterjectionReceived: (data) => {
        try {
          interjectionFeedback = `✓ Sent: "${(data.content || '').substring(0, 60)}${(data.content || '').length > 60 ? '…' : ''}"`;
          // Clear feedback after 5 seconds
          setTimeout(() => { if (interjectionFeedback.startsWith('✓ Sent:')) interjectionFeedback = ''; }, 5000);
        } catch (e) { console.warn('[MvpDebateView] onInterjectionReceived error:', e); }
      },
      onInterjectionConsumed: (data) => {
        try {
          const agentLabel = AGENTS.find(a => a.role === data.role)?.label || data.role;
          const contents = data.contents || [];
          const preview = contents.length > 0 ? `"${contents[0].substring(0, 80)}${contents[0].length > 80 ? '…' : ''}"` : '';
          interjectionFeedback = `📨 ${agentLabel} received your input (Round ${data.round || '?'}) ${preview}`;
          consumedInterjections = [...consumedInterjections, {
            role: data.role,
            round: data.round,
            count: data.interjection_count,
            contents: data.contents,
            timestamp: Date.now(),
          }];
          // Clear feedback after 8 seconds
          setTimeout(() => { if (interjectionFeedback.startsWith('📨')) interjectionFeedback = ''; }, 8000);
          refreshHITLInteractions();
        } catch (e) { console.warn('[MvpDebateView] onInterjectionConsumed error:', e); }
      },
      onHITLInject: () => {
        refreshHITLStatus();
        refreshHITLInteractions();
      },
      onHITLInjectConsumed: () => {
        refreshHITLStatus();
        refreshHITLInteractions();
      },
      onHITLPause: () => {
        refreshHITLStatus();
      },
      onHITLTimeout: () => {
        showAgentQueryModal.set(false);
        currentAgentQuery.set(null);
        refreshHITLStatus();
      },
    });
  }

  async function refreshHITLStatus() {
    if (!debateId) return;
    try {
      const status = await getHITLStatus(debateId);
      hitlStatus.set(status);
    } catch { /* Silently fail */ }
  }

  async function refreshHITLInteractions() {
    if (!debateId) return;
    try {
      const result = await getInteractions(debateId, { limit: 100 });
      hitlInteractions.set(result.interactions || []);
    } catch { /* Silently fail */ }
  }

  async function handleStart() {
    if (!topic.trim()) return;
    error = '';
    status = 'running';
    nodeOutputs = [];
    nodeStatuses = {};
    currentRound = 0;
    consensus = 0;
    hasReceivedConsensus = false;
    elapsedMs = 0;
    llmAssignmentsResult = {};
    totalTokens = 0;
    expandedOutputs = new Set();
    activityText = '';
    debateId = null;

    const profileMap = {};
    for (const agent of AGENTS) {
      profileMap[agent.role] = llmAssignments[agent.role] || '';
    }

    // Build component maps: only include non-empty selections
    const coreMap = {};
    const argPatternMap = {};
    const toneMap = {};
    const modifierMap = {};
    for (const agent of AGENTS) {
      if (agentCoreAssignments[agent.role]) coreMap[agent.role] = agentCoreAssignments[agent.role];
      if (argumentationPatternAssignments[agent.role]) argPatternMap[agent.role] = argumentationPatternAssignments[agent.role];
      if (toneProfileAssignments[agent.role]) toneMap[agent.role] = toneProfileAssignments[agent.role];
      if (promptModifierAssignments[agent.role]) modifierMap[agent.role] = promptModifierAssignments[agent.role];
    }

    try {
      const result = await startMvpDebate({
        context: topic.trim(),
        language: $userLanguage || 'de',
        maxRounds,
        threshold,
        llmProfileIds: profileMap,
        agentCoreIds: coreMap,
        argumentationPatternIds: argPatternMap,
        toneProfileIds: toneMap,
        promptModifierIds: modifierMap,
        projectId: $activeProject?.id,
        searchMode,
        documentIds: selectedDocumentIds,
        ragAutoRetrieve,
        includeDebateResults,
      });
      sessionId = result.session_id;
      debateId = result.debate_id;
      debateTitle = result.title || '';
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

  function toggleDocumentSelection(docId) {
    const idx = selectedDocumentIds.indexOf(docId);
    if (idx >= 0) {
      selectedDocumentIds = selectedDocumentIds.filter(id => id !== docId);
    } else {
      selectedDocumentIds = [...selectedDocumentIds, docId];
    }
  }

  async function handleSendInterjection() {
    if (!interjectionText.trim() || !sessionId) return;
    sendingInterjection = true;
    try {
      await submitInterjection(sessionId, interjectionText.trim());
      interjectionText = '';
    } catch (err) {
      console.error('Failed to send interjection:', err);
    } finally {
      sendingInterjection = false;
    }
  }

  function handleReset() {
    if (externalDebateId) {
      // Came from archive — navigate back to fresh create page
      navigate('mvp-debate');
      return;
    }
    if (cleanupSSE) cleanupSSE();
    sessionId = null;
    debateId = null;
    debateTitle = '';
    status = 'idle';
    currentNodeId = '';
    currentRound = 0;
    consensus = 0;
    hasReceivedConsensus = false;
    elapsedMs = 0;
    nodeOutputs = [];
    nodeStatuses = {};
    error = '';
    llmAssignmentsResult = {};
    totalTokens = 0;
    expandedOutputs = new Set();
    activityText = '';
    stopTimer();
  }

  // HITL polling when debate is running
  $effect(() => {
    if (status === 'running' && debateId) {
      refreshHITLStatus();
      refreshHITLInteractions();
      if (hitlPollTimer) clearInterval(hitlPollTimer);
      hitlPollTimer = setInterval(() => {
        refreshHITLStatus();
        refreshHITLInteractions();
      }, 5000);
    } else {
      if (hitlPollTimer) { clearInterval(hitlPollTimer); hitlPollTimer = null; }
    }
  });

  $effect(() => {
    return () => {
      stopTimer();
      if (cleanupSSE) cleanupSSE();
      if (hitlPollTimer) clearInterval(hitlPollTimer);
    };
  });
</script>

<div class="mvp-debate-view" data-testid="mvp-debate-view">
  <div class="view-header">
    <h1 class="view-title">
      <span class="title-icon">🏛️</span>
      {debateTitle || 'MVP Debate Canvas'}
    </h1>
    <p class="view-subtitle">
      {#if debateTitle}
        MVP Debate · 4-agent debate with per-agent LLM profiles
      {:else}
        4-agent debate with per-agent LLM profiles
      {/if}
    </p>
  </div>

  {#if isLoadingDebate}
    <div class="loading-section">
      <div class="flex items-center justify-center py-12">
        <span class="loading-spinner"></span>
        <span class="ml-3 text-gray-500 dark:text-gray-400 text-sm">Loading debate...</span>
      </div>
    </div>
  {:else if showConfirm}
    <!-- Confirmation / Parameter Summary Page -->
    <div class="confirm-section">
      <h3 class="confirm-title">📋 Debate Parameter Review</h3>
      <p class="confirm-subtitle">Please review all parameters before starting the debate.</p>

      <div class="confirm-grid">
        <!-- Topic -->
        <div class="confirm-card">
          <span class="confirm-label">📝 Topic</span>
          <p class="confirm-value confirm-topic">{topic}</p>
        </div>

        <!-- Round & Threshold -->
        <div class="confirm-row">
          <div class="confirm-card">
            <span class="confirm-label">🔄 Max Rounds</span>
            <span class="confirm-value confirm-number">{maxRounds}</span>
          </div>
          <div class="confirm-card">
            <span class="confirm-label">🎯 Consensus Threshold</span>
            <span class="confirm-value confirm-number">{(threshold * 100).toFixed(0)}%</span>
          </div>
        </div>

        <!-- Agent → LLM Mapping -->
        <div class="confirm-card">
          <span class="confirm-label">🤖 Agent → LLM Mapping</span>
          {#each AGENTS as agent}
            {@const profile = llmProfiles.find(p => p.id === llmAssignments[agent.role])}
            <div class="confirm-row-item">
              <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
              {#if profile?.model}
                <span class="confirm-llm-name">{profile.name} ({profile.model})</span>
              {:else}
                <span class="confirm-llm-name dimmed">Will be auto-assigned</span>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Agent → Core Mapping -->
        <div class="confirm-card">
          <span class="confirm-label">🧠 Agent → Core Mapping</span>
          {#each AGENTS as agent}
            {@const coreId = agentCoreAssignments[agent.role]}
            {@const core = agentCores.find(c => c.id === coreId)}
            <div class="confirm-row-item">
              <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
              {#if core}
                <span class="confirm-llm-name">{core.name}</span>
              {:else}
                <span class="confirm-llm-name dimmed">Default (built-in)</span>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Argumentation Patterns -->
        <div class="confirm-card">
          <span class="confirm-label">📐 Argumentation Patterns</span>
          {#each AGENTS as agent}
            {@const patId = argumentationPatternAssignments[agent.role]}
            {@const pat = argumentationPatterns.find(p => p.id === patId)}
            <div class="confirm-row-item">
              <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
              {#if pat}
                <span class="confirm-llm-name">{pat.name}</span>
              {:else}
                <span class="confirm-llm-name dimmed">None (default)</span>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Tone Profiles -->
        <div class="confirm-card">
          <span class="confirm-label">🎭 Tone Profiles</span>
          {#each AGENTS as agent}
            {@const toneId = toneProfileAssignments[agent.role]}
            {@const tp = toneProfiles.find(p => p.id === toneId)}
            <div class="confirm-row-item">
              <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
              {#if tp}
                <span class="confirm-llm-name">{tp.name}</span>
              {:else}
                <span class="confirm-llm-name dimmed">None (default)</span>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Prompt Modifiers -->
        <div class="confirm-card">
          <span class="confirm-label">✏️ Prompt Modifiers</span>
          {#each AGENTS as agent}
            {@const modId = promptModifierAssignments[agent.role]}
            {@const mod = promptModifiers.find(p => p.id === modId)}
            <div class="confirm-row-item">
              <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
              {#if mod}
                <span class="confirm-llm-name">{mod.name}</span>
              {:else}
                <span class="confirm-llm-name dimmed">None (default)</span>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Web Search -->
        <div class="confirm-card">
          <span class="confirm-label">🔍 Web Search</span>
          <span class="confirm-value">
            {#if searchMode === 'required'}Required (auto-search before each agent)
            {:else if searchMode === 'optional'}Optional (agents may request)
            {:else}Off{/if}
          </span>
        </div>

        <!-- RAG / DMS Documents -->
        {#if selectedDocumentIds.length > 0}
          <div class="confirm-card">
            <span class="confirm-label">📚 RAG Context ({selectedDocumentIds.length} document{selectedDocumentIds.length > 1 ? 's' : ''})</span>
            <div class="confirm-value">
              {#each selectedDocumentIds as docId}
                {@const doc = availableDocuments.find(d => d.id === docId)}
                <span class="confirm-doc">{doc?.filename || docId}</span>
              {/each}
              {#if ragAutoRetrieve}<span class="confirm-badge">Auto-retrieve</span>{/if}
              {#if includeDebateResults}<span class="confirm-badge">Include debate results</span>{/if}
            </div>
          </div>
        {/if}

        <!-- Language & Project -->
        <div class="confirm-row">
          <div class="confirm-card">
            <span class="confirm-label">🌐 Debate Language</span>
            <span class="confirm-value">{($userLanguage || 'de').toUpperCase()}</span>
          </div>
          <div class="confirm-card">
            <span class="confirm-label">📁 Active Project</span>
            <span class="confirm-value">{$activeProject?.name || '—'}</span>
          </div>
        </div>
      </div>

      {#if error}
        <div class="error-box" role="alert">
          <span class="error-icon">⚠️</span>
          <span class="error-text">{error}</span>
        </div>
      {/if}

      <div class="actions-row" style="gap: 12px;">
        <button class="btn btn-cancel" onclick={() => { showConfirm = false; }}>
          ← Back to Edit
        </button>
        <button class="btn btn-start" onclick={() => { showConfirm = false; handleStart(); }}>
          ▶ Start Debate
        </button>
      </div>
    </div>

  {:else if status === 'idle'}
    <div class="config-section">
      <div class="form-group">
        <label for="mvp-topic" class="form-label">Debate Topic</label>
        <textarea
          id="mvp-topic"
          class="form-textarea"
          placeholder="Enter your debate topic..."
          bind:value={topic}
          disabled={isLoadingProfiles}
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

      <!-- Web Search Mode -->
      <div class="form-group">
        <label for="mvp-search-mode" class="form-label">Web Search</label>
        <select
          id="mvp-search-mode"
          class="form-select"
          bind:value={searchMode}
        >
          <option value="off">Off</option>
          <option value="optional">Optional (agents may request)</option>
          <option value="required">Required (auto-search before each agent)</option>
        </select>
      </div>

      <!-- DMS Document Selection -->
      {#if availableDocuments.length > 0}
        <div class="dms-section">
          <div class="flex items-center justify-between mb-2">
            <span class="form-label">DMS Documents (RAG Context)</span>
            <span class="text-xs text-gray-500">{selectedDocumentIds.length} selected</span>
          </div>
          <div class="dms-doc-list">
            {#each availableDocuments as doc (doc.id)}
              <label class="dms-doc-item">
                <input
                  type="checkbox"
                  checked={selectedDocumentIds.includes(doc.id)}
                  onchange={() => toggleDocumentSelection(doc.id)}
                  class="dms-checkbox"
                />
                <span class="dms-doc-name">{doc.filename}</span>
              </label>
            {/each}
          </div>
          <div class="dms-options">
            <label class="dms-option">
              <input type="checkbox" bind:checked={ragAutoRetrieve} class="dms-checkbox" />
              <span class="text-sm text-gray-700">Auto-retrieve relevant chunks</span>
            </label>
            <label class="dms-option">
              <input type="checkbox" bind:checked={includeDebateResults} class="dms-checkbox" />
              <span class="text-sm text-gray-700">Include previous debate results</span>
            </label>
          </div>
        </div>
      {/if}

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

            <div class="agent-core-select">
              <label for="core-{agent.role}" class="select-label">Agent Core (optional)</label>
              {#if isLoadingComponents}
                <div class="select-loading">Loading...</div>
              {:else}
                <select
                  id="core-{agent.role}"
                  class="form-select"
                  bind:value={agentCoreAssignments[agent.role]}
                >
                  <option value="">Default (built-in)</option>
                  {#each agentCores.filter(c => c.role === agent.role) as core}
                    <option value={core.id}>{core.name}</option>
                  {/each}
                </select>
              {/if}
            </div>

            <div class="agent-pat-select">
              <label for="pat-{agent.role}" class="select-label">Argumentation Pattern (optional)</label>
              {#if isLoadingComponents}
                <div class="select-loading">Loading...</div>
              {:else}
                <select
                  id="pat-{agent.role}"
                  class="form-select"
                  bind:value={argumentationPatternAssignments[agent.role]}
                >
                  <option value="">Default (none)</option>
                  {#each argumentationPatterns as pattern}
                    <option value={pattern.id}>{pattern.name}</option>
                  {/each}
                </select>
              {/if}
            </div>

            <div class="agent-tone-select">
              <label for="tone-{agent.role}" class="select-label">Tone Profile (optional)</label>
              {#if isLoadingComponents}
                <div class="select-loading">Loading...</div>
              {:else}
                <select
                  id="tone-{agent.role}"
                  class="form-select"
                  bind:value={toneProfileAssignments[agent.role]}
                >
                  <option value="">Default (none)</option>
                  {#each toneProfiles as profile}
                    <option value={profile.id}>{profile.name}</option>
                  {/each}
                </select>
              {/if}
            </div>

            <div class="agent-mod-select">
              <label for="mod-{agent.role}" class="select-label">Prompt Modifier (optional)</label>
              {#if isLoadingComponents}
                <div class="select-loading">Loading...</div>
              {:else}
                <select
                  id="mod-{agent.role}"
                  class="form-select"
                  bind:value={promptModifierAssignments[agent.role]}
                >
                  <option value="">Default (none)</option>
                  {#each promptModifiers as mod}
                    <option value={mod.id}>{mod.name}</option>
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
          onclick={() => { if (topic.trim() && !isLoadingProfiles) showConfirm = true; }}
          disabled={!topic.trim() || isLoadingProfiles}
        >
          ▶ Review & Start
        </button>
      </div>
    </div>

    {:else}
    <AgentQueryModal debateId={debateId || ''} />
    <div class="execution-section">
      <div class="status-bar status-{status}">
        <span class="status-dot"></span>
        <span class="status-text">{status}</span>
        {#if debateId}
          <span class="debate-id clickable" title="Debate ID: {debateId}" onclick={() => navigator.clipboard?.writeText(debateId)} role="button" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter') navigator.clipboard?.writeText(debateId); }}>ID: {debateId}</span>
        {/if}
        {#if sessionId}
          <span class="session-id">{sessionId}</span>
        {/if}
      </div>

      {#if activityText && status === 'running'}
        <div class="activity-bar">
          <span class="activity-spinner"></span>
          <span class="activity-text">{activityText}</span>
        </div>
      {/if}

      <div class="metrics-grid">
        <div class="metric">
          <span class="metric-label">Round</span>
          <span class="metric-value">{currentRound}/{maxRounds}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Consensus</span>
            <span class="metric-value">{#if hasReceivedConsensus}{(consensus * 100).toFixed(0)}%{:else}—{/if}</span>
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
                <span class="llm-role">{role}</span>: <span class="llm-profile">{getProfileName(profileId)}</span>
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

      {#if status === 'running' && debateId}
        <PauseControls {debateId} />
      {/if}

      {#if status === 'running' && debateId}
        <InjectPanel {debateId} agentRoles={['strategist', 'critic', 'optimizer', 'moderator']} />
      {/if}

      {#if status === 'running' || status === 'paused'}
        <div class="interjection-area">
          <div class="interjection-input-row">
            <input
              type="text"
              class="interjection-input"
              bind:value={interjectionText}
              placeholder="Send input to agents..."
              onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendInterjection(); } }}
              disabled={sendingInterjection}
            />
            <button
              class="btn btn-interject"
              onclick={handleSendInterjection}
              disabled={!interjectionText.trim() || sendingInterjection}
            >
              Send
            </button>
          </div>
          {#if interjectionFeedback}
            <div class="interjection-feedback" class:consumed={interjectionFeedback.startsWith('📨')}>
              {interjectionFeedback}
            </div>
          {/if}
        </div>
      {/if}

      {#if debateId}
        <InteractionTimeline {debateId} />
      {/if}

      {#if nodeOutputs.length > 0}
        <div class="outputs-section">
          <h4 class="outputs-title">Agent Outputs ({nodeOutputs.length})</h4>
          <div class="outputs-list">
            {#each nodeOutputs as output, idx}
              {@const key = `output-${idx}`}
              {@const isExpanded = expandedOutputs.has(key)}
              {@const isLong = output.content?.length > 400}
              <div class="output-item">
                <div class="output-header">
                  <span class="output-role">{output.role || output.nodeType}</span>
                  <span class="output-meta">
                    {#if output.round}Round {output.round} · {/if}
                    {formatDuration(output.durationMs)} ·
                    {output.tokensUsed || 0} tokens
                  </span>
                </div>
                <div class="output-content markdown-rendered">
                  {#if isLong && !isExpanded}
                    {@html renderMarkdown(output.content.substring(0, 400) + '…')}
                    <button class="expand-btn" onclick={() => expandedOutputs = new Set([...expandedOutputs, key])}>
                      ▼ Show full response ({output.content.length} chars)
                    </button>
                  {:else}
                    {@html renderMarkdown(output.content)}
                    {#if isLong}
                      <button class="expand-btn" onclick={() => { const next = new Set(expandedOutputs); next.delete(key); expandedOutputs = next; }}>
                        ▲ Collapse
                      </button>
                    {/if}
                  {/if}
                </div>
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
  :global(.dark) .status-bar { background: #1f2937; color: #e5e7eb; }
  .status-text { color: inherit; }
  .status-running .status-text { color: #3b82f6; }
  :global(.dark) .status-running .status-text { color: #60a5fa; }
  .status-completed .status-text { color: #16a34a; }
  :global(.dark) .status-completed .status-text { color: #4ade80; }
  .status-failed .status-text { color: #dc2626; }
  :global(.dark) .status-failed .status-text { color: #f87171; }
  .status-cancelled .status-text { color: #6b7280; }
  :global(.dark) .status-cancelled .status-text { color: #9ca3af; }
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
  .debate-id.clickable {
    cursor: pointer;
    text-decoration: underline dotted;
  }
  .debate-id.clickable:hover {
    color: #38bdf8;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .activity-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 16px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    font-size: 13px;
    color: #1e40af;
    animation: fadeIn 0.3s ease;
  }
  :global(.dark) .activity-bar {
    background: #1e3a5f;
    border-color: #2563eb;
    color: #93c5fd;
  }
  .activity-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid #bfdbfe;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    flex-shrink: 0;
  }
  :global(.dark) .activity-spinner {
    border-color: #1e3a5f;
    border-top-color: #60a5fa;
  }
  .activity-text {
    font-weight: 500;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
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
    max-height: 70vh;
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

  .expand-btn {
    display: block;
    margin-top: 6px;
    background: none;
    border: none;
    color: #3b82f6;
    font-size: 12px;
    cursor: pointer;
    padding: 2px 0;
    text-decoration: underline dotted;
  }
  :global(.dark) .expand-btn { color: #60a5fa; }
  .expand-btn:hover { color: #1d4ed8; }
  :global(.dark) .expand-btn:hover { color: #93c5fd; }

  .loading-section {
    padding: 24px;
  }
  .loading-spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 2px solid #e5e7eb;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* DMS Document Section */
  .dms-section {
    padding: 16px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  :global(.dark) .dms-section {
    background: #1f2937;
    border-color: #374151;
  }
  .dms-doc-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 140px;
    overflow-y: auto;
  }
  .dms-doc-item {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding: 4px 0;
  }
  .dms-checkbox {
    border-radius: 4px;
    border: 1px solid #d1d5db;
    accent-color: #3b82f6;
  }
  .dms-doc-name {
    font-size: 13px;
    color: #374151;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.dark) .dms-doc-name { color: #e5e7eb; }
  .dms-options {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 8px;
    border-top: 1px solid #e5e7eb;
  }
  :global(.dark) .dms-options { border-color: #374151; }
  .dms-option {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  /* Interjection area */
  .interjection-area {
    padding: 12px;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 8px;
  }
  :global(.dark) .interjection-area {
    background: #164e63;
    border-color: #155e75;
  }
  .interjection-input-row {
    display: flex;
    gap: 8px;
  }
  .interjection-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    outline: none;
    background: white;
    color: #1f2937;
  }
  :global(.dark) .interjection-input {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .interjection-input:focus { border-color: #3b82f6; }
  .btn-interject {
    background: #0ea5e9;
    color: white;
    padding: 8px 20px;
    border-radius: 8px;
    border: none;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-interject:hover { background: #0284c7; }
  .btn-interject:disabled { opacity: 0.5; cursor: not-allowed; }
  .interjection-feedback {
    margin-top: 8px;
    padding: 6px 12px;
    background: #dcfce7;
    border: 1px solid #86efac;
    border-radius: 6px;
    font-size: 13px;
    color: #166534;
    animation: fadeIn 0.3s ease-in;
  }
  .interjection-feedback.consumed {
    background: #dbeafe;
    border-color: #93c5fd;
    color: #1e40af;
  }
  :global(.dark) .interjection-feedback {
    background: #14532d;
    border-color: #22c55e;
    color: #bbf7d0;
  }
  :global(.dark) .interjection-feedback.consumed {
    background: #1e3a5f;
    border-color: #3b82f6;
    color: #bfdbfe;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Confirmation / Parameter Review */
  .confirm-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 24px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
  }
  :global(.dark) .confirm-section {
    background: #1f2937;
    border-color: #374151;
  }
  .confirm-title {
    font-size: 18px;
    font-weight: 700;
    color: #1f2937;
    margin: 0;
  }
  :global(.dark) .confirm-title { color: #e5e7eb; }
  .confirm-subtitle {
    font-size: 13px;
    color: #6b7280;
    margin: 0;
  }
  .confirm-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .confirm-row {
    display: flex;
    gap: 12px;
  }
  .confirm-row .confirm-card { flex: 1; }
  .confirm-card {
    padding: 12px 16px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }
  :global(.dark) .confirm-card {
    background: #111827;
    border-color: #374151;
  }
  .confirm-label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }
  .confirm-value {
    font-size: 14px;
    color: #1f2937;
    word-break: break-word;
  }
  :global(.dark) .confirm-value { color: #e5e7eb; }
  .confirm-topic {
    font-size: 14px;
    font-weight: 500;
    line-height: 1.5;
  }
  .confirm-number {
    font-size: 20px;
    font-weight: 700;
    color: #3b82f6;
  }
  .confirm-agent-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }
  .confirm-agent-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
  }
  .confirm-agent-icon { font-size: 16px; }
  .confirm-agent-name {
    font-weight: 600;
    color: #374151;
    min-width: 80px;
  }
  :global(.dark) .confirm-agent-name { color: #d1d5db; }
  .confirm-arrow { color: #9ca3af; }
  .confirm-llm-name {
    font-weight: 500;
    color: #3b82f6;
  }
  .confirm-llm-model {
    font-size: 11px;
    color: #9ca3af;
    font-family: monospace;
  }
  .confirm-doc {
    display: inline-block;
    padding: 2px 8px;
    margin: 2px 4px 2px 0;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    font-size: 12px;
    color: #1e40af;
  }
  :global(.dark) .confirm-doc {
    background: #1e3a5f;
    border-color: #2563eb;
    color: #93c5fd;
  }
  .confirm-badge {
    display: inline-block;
    padding: 2px 8px;
    margin-left: 6px;
    background: #dcfce7;
    border: 1px solid #86efac;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    color: #166534;
  }
  :global(.dark) .confirm-badge {
    background: #14532d;
    border-color: #16a34a;
    color: #4ade80;
  }
</style>
