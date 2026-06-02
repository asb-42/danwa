<script>
  import { i18n, formatNumber } from '../lib/i18n/index.js';
  import { getLLMProfiles, getDebate, getDocuments } from '../lib/api.js';
  import { startMvpDebate, submitInterjection, getCompositionComponents } from '../lib/workflowExec.js';
  import { createWorkflowSSE } from '../lib/workflowSSE.js';
  import { activeProject, userLanguage } from '../lib/stores.js';

  import { getHITLStatus, getInteractions } from '../lib/hitl.js';
  import { hitlStatus, hitlInteractions, showAgentQueryModal, currentAgentQuery } from '../lib/stores/hitl.svelte.js';
  import InjectPanel from '../components/hitl/InjectPanel.svelte';
  import PauseControls from '../components/hitl/PauseControls.svelte';
  import AgentQueryModal from '../components/hitl/AgentQueryModal.svelte';
  import InteractionTimeline from '../components/hitl/InteractionTimeline.svelte';
  import DebateActivityStrip from '../components/debate/DebateActivityStrip.svelte';
  import DebateSetupForm from '../components/debate/DebateSetupForm.svelte';
  import DebateReviewPanel from '../components/debate/DebateReviewPanel.svelte';
  import DebateTranscript from '../components/debate/DebateTranscript.svelte';
  import DebateInterjection from '../components/debate/DebateInterjection.svelte';
  import DebateActivityLog from '../components/debate/DebateActivityLog.svelte';

  let { debateId: externalDebateId = null, navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const AGENTS = [
    { role: 'strategist', label: t('mvpDebate.agent.strategist'), icon: '🧠', color: '#3b82f6', desc: t('mvpDebate.agentDesc.strategist') },
    { role: 'critic', label: t('mvpDebate.agent.critic'), icon: '🔍', color: '#ef4444', desc: t('mvpDebate.agentDesc.critic') },
    { role: 'optimizer', label: t('mvpDebate.agent.optimizer'), icon: '⚡', color: '#10b981', desc: t('mvpDebate.agentDesc.optimizer') },
    { role: 'moderator', label: t('mvpDebate.agent.moderator'), icon: '🎯', color: '#8b5cf6', desc: t('mvpDebate.agentDesc.moderator') },
  ];

  let config = $state({
    topic: '',
    maxRounds: 5,
    threshold: 0.9,
    searchMode: 'off',
    selectedDocumentIds: [],
    ragAutoRetrieve: false,
    includeDebateResults: false,
    includeDocumentAnalysis: false,
    selectedDebateIds: [],
    enableExtraRounds: false,
    llmAssignments: {},
    agentCoreAssignments: {},
    argumentationPatternAssignments: {},
    toneProfileAssignments: {},
    promptModifierAssignments: {},
  });

  let llmProfiles = $state([]);
  let isLoadingProfiles = $state(true);
  let isLoadingDebate = $state(false);

  let agentCores = $state([]);
  let argumentationPatterns = $state([]);
  let toneProfiles = $state([]);
  let promptModifiers = $state([]);
  let isLoadingComponents = $state(true);

  let availableDocuments = $state([]);

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

  let interjectionFeedback = $state('');
  let sendingInterjection = $state(false);
  let consumedInterjections = $state([]);

  let currentActivity = $state(null);
  let isConnected = $state(false);
  let cumulativeTokens = $state(0);
  let processingStartTime = $state(null);
  let processingElapsed = $state(0);
  let processingTimer = $state(null);
  let workflowPhase = $state(null);
  let workflowStartTime = $state(null);
  let workflowElapsed = $state(0);
  let workflowTimer = $state(null);

  let startTime = null;
  let timerInterval = null;
  let hitlPollTimer = null;

  $effect(() => {
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
        config.llmAssignments = defaults;

        agentCores = components.agent_cores || [];
        argumentationPatterns = components.argumentation_patterns || [];
        toneProfiles = components.tone_profiles || [];
        promptModifiers = components.prompt_modifiers || [];

        const emptyDefaults = {};
        for (const agent of AGENTS) {
          emptyDefaults[agent.role] = '';
        }
        config.agentCoreAssignments = { ...emptyDefaults };
        config.argumentationPatternAssignments = { ...emptyDefaults };
        config.toneProfileAssignments = { ...emptyDefaults };
        config.promptModifierAssignments = { ...emptyDefaults };
      })
      .catch((err) => {
        error = t('mvpDebate.error.loadProfiles', { error: err.message });
      })
      .finally(() => {
        isLoadingProfiles = false;
        isLoadingComponents = false;
      });
  });

  $effect(() => {
    getDocuments()
      .then((docs) => { availableDocuments = docs; })
      .catch(() => { availableDocuments = []; });
  });

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
        config.topic = debate.case_text || '';
        config.maxRounds = debate.max_rounds || 5;
        config.threshold = debate.consensus_score ?? 0.9;
        status = debate.status;
        currentRound = debate.current_round || 0;
        if (debate.consensus_score !== null && debate.consensus_score !== undefined) {
          consensus = debate.consensus_score;
          hasReceivedConsensus = true;
        }

        if (debate.session_id) {
          sessionId = debate.session_id;

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
        error = t('mvpDebate.error.loadDebate', { error: err.message });
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

  function formatElapsed(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function startProcessingTimer() {
    processingStartTime = Date.now();
    processingElapsed = 0;
    if (processingTimer) clearInterval(processingTimer);
    processingTimer = setInterval(() => {
      processingElapsed = Date.now() - processingStartTime;
    }, 100);
  }

  function stopProcessingTimer() {
    if (processingTimer) { clearInterval(processingTimer); processingTimer = null; }
  }

  function startWorkflowTimer() {
    workflowStartTime = Date.now();
    workflowElapsed = 0;
    if (workflowTimer) clearInterval(workflowTimer);
    workflowTimer = setInterval(() => {
      workflowElapsed = Date.now() - workflowStartTime;
    }, 200);
  }

  function stopWorkflowTimer() {
    if (workflowTimer) { clearInterval(workflowTimer); workflowTimer = null; }
  }

  let agentCount = $derived(currentActivity?.agent_total || 4);
  let activeAgentIndex = $derived(currentActivity?.agent_index ?? -1);
  let completedInRound = $derived(nodeOutputs.filter(o => o.round === currentRound).length);
  let isProcessing = $derived(status === 'running' && currentActivity !== null);
  let isBetweenAgents = $derived(status === 'running' && currentActivity === null && nodeOutputs.length > 0);
  let debateForStrip = $derived({ status, current_round: currentRound });

  function connectSSE(sid) {
    cleanupSSE = createWorkflowSSE(sid, {
      onOpen: () => { isConnected = true; },
      onClose: () => { isConnected = false; },
      onWorkflowStarted: () => {
        status = 'running';
        workflowPhase = { type: 'workflow_started' };
        startWorkflowTimer();
      },
      onNodeStart: (data) => {
        try {
          currentNodeId = data.node_id || '';
          const agentLabel = AGENTS.find(a => a.role === data.role)?.label || data.role;
          currentActivity = null;
          workflowPhase = {
            type: 'agent_preparing',
            phase: 'resolving_profile',
            role: data.role,
            round: data.round || currentRound,
            agent_index: data.agent_index ?? 0,
            agent_total: data.agent_total ?? 4,
          };
          nodeStatuses = { ...nodeStatuses, [currentNodeId]: 'running' };
          if (!workflowTimer) startWorkflowTimer();
        } catch (e) { console.warn('[MvpDebateView] onNodeStart error:', e); }
      },
      onLLMCallStarted: (data) => {
        try {
          const agentLabel = AGENTS.find(a => a.role === data.role)?.label || data.role;
          const llmName = getProfileName(data.llm_profile_id);
          currentActivity = {
            role: data.role,
            round: data.round || currentRound,
            llm_profile_id: data.llm_profile_id,
            model: data.model || '',
            provider: data.provider || '',
            agent_index: data.agent_index ?? 0,
            agent_total: data.agent_total ?? 4,
          };
          workflowPhase = {
            type: 'llm_call_started',
            role: data.role,
            model: data.model || '',
            provider: data.provider || '',
            round: data.round || currentRound,
            agent_index: data.agent_index ?? 0,
            agent_total: data.agent_total ?? 4,
          };
          stopWorkflowTimer();
          startProcessingTimer();
        } catch (e) { console.warn('[MvpDebateView] onLLMCallStarted error:', e); }
      },
      onWebSearch: (data) => {
        try {
          // activity text tracked via workflowPhase
        } catch (e) { console.warn('[MvpDebateView] onWebSearch error:', e); }
      },
      onNodeComplete: (data) => {
        try {
          const tokensUsed = data.tokens_used || 0;
          const model = currentActivity?.model || data.model || '';
          const profile = currentActivity?.llm_profile_id || '';
          nodeOutputs = [...nodeOutputs, {
            nodeId: data.node_id,
            nodeType: data.node_type,
            role: data.role,
            content: data.content,
            durationMs: data.duration_ms,
            round: data.round,
            tokensUsed,
            model,
            profile,
          }];
          nodeStatuses = { ...nodeStatuses, [data.node_id]: 'completed' };
          if (data.consensus !== undefined) { consensus = data.consensus; hasReceivedConsensus = true; }
          if (data.round !== undefined) currentRound = data.round;
          cumulativeTokens += tokensUsed;
          totalTokens = nodeOutputs.reduce((sum, o) => sum + (o.tokensUsed || 0), 0);
          currentActivity = null;
          workflowPhase = null;
          stopProcessingTimer();
          stopWorkflowTimer();
        } catch (e) { console.warn('[MvpDebateView] onNodeComplete error:', e); }
      },
      onRoundUpdate: (data) => {
        currentRound = data.round || currentRound;
        if (data.consensus !== undefined && data.consensus !== null) {
          consensus = data.consensus;
          hasReceivedConsensus = true;
        }
        totalTokens = data.total_tokens ?? totalTokens;
        currentActivity = null;
        workflowPhase = null;
        stopProcessingTimer();
        stopWorkflowTimer();
      },
      onConsensusReached: (data) => {
        if (data.score !== undefined && data.score !== null) {
          consensus = data.score;
          hasReceivedConsensus = true;
        }
      },
      onNodeError: (data) => {
        error = data.error || t('mvpDebate.error.unknown');
        status = 'failed';
        stopTimer();
        currentActivity = null;
        workflowPhase = null;
        stopProcessingTimer();
        stopWorkflowTimer();
        nodeStatuses = { ...nodeStatuses, [data.node_id]: 'failed' };
      },
      onWorkflowComplete: (data) => {
        status = 'completed';
        stopTimer();
        currentActivity = null;
        workflowPhase = null;
        stopProcessingTimer();
        stopWorkflowTimer();
        if (data.final_consensus !== undefined) { consensus = data.final_consensus; hasReceivedConsensus = true; }
        if (cleanupSSE) { cleanupSSE(); cleanupSSE = null; }
      },
      onWorkflowPaused: () => { status = 'paused'; },
      onWorkflowResumed: () => { status = 'running'; },
      onError: (err) => { console.error('[MvpDebateView] SSE error:', err); },
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
          interjectionFeedback = t('mvpDebate.interjection.sent', { preview: `${(data.content || '').substring(0, 60)}${(data.content || '').length > 60 ? '…' : ''}` });
          setTimeout(() => { if (interjectionFeedback.startsWith('✓ Sent:')) interjectionFeedback = ''; }, 5000);
        } catch (e) { console.warn('[MvpDebateView] onInterjectionReceived error:', e); }
      },
      onInterjectionConsumed: (data) => {
        try {
          const agentLabel = AGENTS.find(a => a.role === data.role)?.label || data.role;
          const contents = data.contents || [];
          const preview = contents.length > 0 ? `"${contents[0].substring(0, 80)}${contents[0].length > 80 ? '…' : ''}"` : '';
          interjectionFeedback = t('mvpDebate.interjection.received', { agent: agentLabel, round: data.round || '?', preview });
          consumedInterjections = [...consumedInterjections, {
            role: data.role,
            round: data.round,
            count: data.interjection_count,
            contents: data.contents,
            timestamp: Date.now(),
          }];
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
      const s = await getHITLStatus(debateId);
      hitlStatus.set(s);
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
    if (!config.topic.trim()) return;
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
    currentActivity = null;
    isConnected = false;
    cumulativeTokens = 0;
    processingStartTime = null;
    processingElapsed = 0;
    if (processingTimer) { clearInterval(processingTimer); processingTimer = null; }
    workflowPhase = null;
    workflowStartTime = null;
    workflowElapsed = 0;
    if (workflowTimer) { clearInterval(workflowTimer); workflowTimer = null; }
    debateId = null;

    const profileMap = {};
    for (const agent of AGENTS) {
      profileMap[agent.role] = config.llmAssignments[agent.role] || '';
    }

    const coreMap = {};
    const argPatternMap = {};
    const toneMap = {};
    const modifierMap = {};
    for (const agent of AGENTS) {
      if (config.agentCoreAssignments[agent.role]) coreMap[agent.role] = config.agentCoreAssignments[agent.role];
      if (config.argumentationPatternAssignments[agent.role]) argPatternMap[agent.role] = config.argumentationPatternAssignments[agent.role];
      if (config.toneProfileAssignments[agent.role]) toneMap[agent.role] = config.toneProfileAssignments[agent.role];
      if (config.promptModifierAssignments[agent.role]) modifierMap[agent.role] = config.promptModifierAssignments[agent.role];
    }

    try {
      const result = await startMvpDebate({
        context: config.topic.trim(),
        language: $userLanguage || 'de',
        maxRounds: config.maxRounds,
        threshold: config.threshold,
        llmProfileIds: profileMap,
        agentCoreIds: coreMap,
        argumentationPatternIds: argPatternMap,
        toneProfileIds: toneMap,
        promptModifierIds: modifierMap,
        projectId: $activeProject?.id,
        searchMode: config.searchMode,
        documentIds: config.selectedDocumentIds,
        ragAutoRetrieve: config.ragAutoRetrieve,
        includeDebateResults: config.includeDebateResults,
        includeDocumentAnalysis: config.includeDocumentAnalysis,
        debateResultIds: config.selectedDebateIds,
        enableExtraRounds: config.enableExtraRounds,
      });
      sessionId = result.session_id;
      debateId = result.debate_id;
      debateTitle = result.title || '';
      llmAssignmentsResult = result.llm_assignments || {};
      startTimer();
      connectSSE(sessionId);
    } catch (err) {
      error = err.message || t('mvpDebate.error.startFailed');
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
      error = err.message || t('mvpDebate.error.cancelFailed');
    }
  }

  async function handleSendInterjection(text) {
    if (!text || !sessionId) return;
    sendingInterjection = true;
    try {
      await submitInterjection(sessionId, text);
    } catch (err) {
      console.error('Failed to send interjection:', err);
    } finally {
      sendingInterjection = false;
    }
  }

  function handleReset() {
    if (externalDebateId) {
      navigate('mvp-debate');
      return;
    }
    if (cleanupSSE) cleanupSSE();
    config.topic = '';
    config.maxRounds = 5;
    config.threshold = 0.9;
    config.searchMode = 'off';
    config.selectedDocumentIds = [];
    config.ragAutoRetrieve = false;
    config.includeDebateResults = false;
    config.includeDocumentAnalysis = false;
    config.selectedDebateIds = [];
    config.enableExtraRounds = false;
    const emptyDefaults = {};
    for (const agent of AGENTS) {
      emptyDefaults[agent.role] = '';
    }
    config.agentCoreAssignments = { ...emptyDefaults };
    config.argumentationPatternAssignments = { ...emptyDefaults };
    config.toneProfileAssignments = { ...emptyDefaults };
    config.promptModifierAssignments = { ...emptyDefaults };
    if (llmProfiles.length > 0) {
      const defaults = {};
      for (const agent of AGENTS) {
        defaults[agent.role] = llmProfiles[0]?.id || '';
      }
      config.llmAssignments = defaults;
    }
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
    currentActivity = null;
    isConnected = false;
    cumulativeTokens = 0;
    processingStartTime = null;
    processingElapsed = 0;
    if (processingTimer) { clearInterval(processingTimer); processingTimer = null; }
    workflowPhase = null;
    workflowStartTime = null;
    workflowElapsed = 0;
    if (workflowTimer) { clearInterval(workflowTimer); workflowTimer = null; }
    interjectionFeedback = '';
    consumedInterjections = [];
    sendingInterjection = false;
    stopTimer();
  }

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
      if (processingTimer) clearInterval(processingTimer);
      if (workflowTimer) clearInterval(workflowTimer);
      if (cleanupSSE) cleanupSSE();
      if (hitlPollTimer) clearInterval(hitlPollTimer);
    };
  });
</script>

<div class="mvp-debate-view" data-testid="mvp-debate-view">
  <div class="view-header">
    <h1 class="view-title">
      <span class="title-icon">🏛️</span>
      {debateTitle || t('mvpDebate.titleFallback')}
    </h1>
    <p class="view-subtitle">
      {#if debateTitle}
        MVP Debate · 4-agent debate with per-agent LLM profiles
      {:else}
        4-agent debate with per-agent LLM profiles
      {/if}
    </p>
  </div>

  {#if debateId}
    <!-- Metadata -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 mb-4">
      <div class="grid grid-cols-1 gap-2 text-sm text-gray-700 dark:text-gray-300">
        {#if currentRound}
          <div><span class="font-semibold">Anzahl Runden:</span> {currentRound}</div>
        {/if}
        {#if nodeOutputs.length}
          {@const roles = [...new Set(nodeOutputs.map(n => n.role).filter(Boolean))]}
          {#if roles.length}
            <div><span class="font-semibold">Agenten-Rollen:</span> {roles.join(' · ')}</div>
          {/if}
        {/if}
      </div>
    </div>

    <!-- Case text (without Title tags) -->
    {#if config.topic}
      <div class="case-text-section">
        <h4 class="case-text-heading">📋 {t('debate.caseLabel')}</h4>
        <p class="case-text-content">{config.topic}</p>
      </div>
    {/if}
  {/if}

  {#if isLoadingDebate}
    <div class="loading-section">
      <div class="flex items-center justify-center py-12">
        <span class="loading-spinner"></span>
        <span class="ml-3 text-gray-500 dark:text-gray-400 text-sm">{t('mvpDebate.loadingDebate')}</span>
      </div>
    </div>
  {:else if showConfirm}
    <DebateReviewPanel
      {config}
      agents={AGENTS}
      profiles={llmProfiles}
      {agentCores}
      {argumentationPatterns}
      {toneProfiles}
      {promptModifiers}
      documents={availableDocuments}
      {error}
      onBack={() => { showConfirm = false; }}
      onStart={() => { showConfirm = false; handleStart(); }}
    />

  {:else if status === 'idle'}
    <DebateSetupForm
      bind:config
      agents={AGENTS}
      profiles={llmProfiles}
      {agentCores}
      {argumentationPatterns}
      {toneProfiles}
      {promptModifiers}
      documents={availableDocuments}
      {isLoadingProfiles}
      {isLoadingComponents}
      {error}
      onReview={() => { showConfirm = true; }}
    />

  {:else}
    <AgentQueryModal debateId={debateId || ''} />
    <div class="execution-section">
      <div class="status-bar status-{status}">
        <span class="status-dot"></span>
        <span class="status-text">{status}</span>
        {#if isConnected}
          <span class="sse-badge" title="SSE connected">
            <span class="sse-dot"></span>
            <span class="sse-label">SSE</span>
          </span>
        {/if}
        {#if debateId}
          <span class="debate-id clickable" title="Debate ID: {debateId}" onclick={() => navigator.clipboard?.writeText(debateId)} role="button" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter') navigator.clipboard?.writeText(debateId); }}>ID: {debateId}</span>
        {/if}
        {#if sessionId}
          <span class="session-id">{sessionId}</span>
        {/if}
      </div>

      {#if status === 'running'}
        <DebateActivityStrip
          currentDebate={debateForStrip}
          {currentActivity}
          {workflowPhase}
          liveOutputs={nodeOutputs}
          {isProcessing}
          {isBetweenAgents}
          {processingElapsed}
          {workflowElapsed}
          {cumulativeTokens}
          {agentCount}
          {activeAgentIndex}
          {completedInRound}
        />
      {/if}

      {#if status === 'running' || status === 'paused'}
        <DebateActivityLog
          activityText={currentActivity ? t('mvpDebate.activity.agentCalling', { agent: AGENTS.find(a => a.role === currentActivity.role)?.label || currentActivity.role, llm: getProfileName(currentActivity.llm_profile_id), round: currentActivity.round }) : ''}
          {consumedInterjections}
          {isConnected}
          isVisible={status === 'running' || status === 'paused'}
        />
      {/if}

      <div class="metrics-grid">
        <div class="metric">
          <span class="metric-label">Round</span>
          <span class="metric-value">{currentRound}/{config.maxRounds}</span>
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
        <DebateInterjection
          disabled={status !== 'running' && status !== 'paused'}
          sending={sendingInterjection}
          feedback={interjectionFeedback}
          onSend={handleSendInterjection}
        />
      {/if}

      {#if debateId}
        <InteractionTimeline {debateId} />
      {/if}

      {#if nodeOutputs.length > 0 || status === 'running'}
        <DebateTranscript
          agentOutputs={nodeOutputs}
          agents={AGENTS}
          {currentRound}
          {currentActivity}
          bind:expandedOutputs
          {llmProfiles}
        />
      {/if}

      {#if hasReceivedConsensus}
        <div class="consensus-bar-wrapper">
          <div class="flex items-center justify-between mb-1">
            <span class="consensus-label">Consensus</span>
            <span class="consensus-pct">{(consensus * 100).toFixed(1)}%</span>
          </div>
          <div class="consensus-track">
            <div
              class="consensus-fill"
              class:consensus-low={consensus < 0.5}
              class:consensus-mid={consensus >= 0.5 && consensus < 0.8}
              class:consensus-high={consensus >= 0.8}
              style="width: {Math.max(2, consensus * 100)}%"
            ></div>
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

  .case-text-section {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }
  :global(.dark) .case-text-section {
    background: #1f2937;
    border-color: #374151;
  }
  .case-text-heading {
    font-size: 13px;
    font-weight: 600;
    color: #6b7280;
    margin: 0 0 8px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  :global(.dark) .case-text-heading { color: #9ca3af; }
  .case-text-content {
    font-size: 14px;
    color: #374151;
    line-height: 1.6;
    white-space: pre-wrap;
    margin: 0;
    max-height: 200px;
    overflow-y: auto;
  }
  :global(.dark) .case-text-content { color: #d1d5db; }

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

  .sse-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: #dcfce7;
    border: 1px solid #86efac;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    color: #166534;
    margin-left: 8px;
  }
  :global(.dark) .sse-badge {
    background: #14532d;
    border-color: #22c55e;
    color: #bbf7d0;
  }
  .sse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #22c55e;
    animation: pulse 1.5s infinite;
  }
  .sse-label {
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .consensus-bar-wrapper {
    padding: 12px 16px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }
  :global(.dark) .consensus-bar-wrapper {
    background: #1f2937;
    border-color: #374151;
  }
  .consensus-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #6b7280;
  }
  :global(.dark) .consensus-label { color: #9ca3af; }
  .consensus-pct {
    font-size: 13px;
    font-weight: 700;
    color: #374151;
    font-variant-numeric: tabular-nums;
  }
  :global(.dark) .consensus-pct { color: #e5e7eb; }
  .consensus-track {
    width: 100%;
    height: 8px;
    background: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
  }
  :global(.dark) .consensus-track { background: #374151; }
  .consensus-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
  }
  .consensus-low { background: #ef4444; }
  .consensus-mid { background: #f59e0b; }
  .consensus-high { background: #22c55e; }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
</style>
