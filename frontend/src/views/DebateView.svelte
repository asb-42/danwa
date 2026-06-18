<script>
  import { onMount, onDestroy } from 'svelte';
  import { currentDebate, debates, loading, error, sseConnected, activeCase, autoStartDebate, addToast } from '../lib/stores.js';
  import { getDebate, startDebate, cancelDebate } from '../lib/api.js';
  import { createSSE } from '../lib/sse.js';
  import { tStore, formatNumber, formatDate, tn } from '../lib/i18n/index.js';
  import MarkdownRenderer from '../components/MarkdownRenderer.svelte';
  import WorkflowGraph from '../components/WorkflowGraph.svelte';
  import { handleWorkflowSSE } from '../lib/workflow/mapper.js';
  import { resetWorkflow } from '../lib/workflow/store.svelte.js';
  import { feedbackStore } from '../lib/stores/feedback.svelte.js';
  // HITL components
  import InjectPanel from '../components/hitl/InjectPanel.svelte';
  import PauseControls from '../components/hitl/PauseControls.svelte';
  import AgentQueryModal from '../components/hitl/AgentQueryModal.svelte';
  import InteractionTimeline from '../components/hitl/InteractionTimeline.svelte';
  import { getHITLStatus, getInteractions } from '../lib/hitl.js';
  import { hitlStatus, hitlInteractions, showAgentQueryModal, currentAgentQuery } from '../lib/stores/hitl.svelte.js';
  // Extracted sub-components
  import DebateActivityStrip from '../components/debate/DebateActivityStrip.svelte';
  import DebateReportPanel from '../components/debate/DebateReportPanel.svelte';
  // Plan 19: Follow-up / Fork Modals
  import ContinueDebateModal from '../components/debate/ContinueDebateModal.svelte';
  import ForkDebateModal from '../components/debate/ForkDebateModal.svelte';

  /** @type {function} Navigation helper from App.svelte */
  let { debateId = null, navigate = () => {} } = $props();

  let t = $derived($tStore);

  /** True when viewing a past debate (read-only archive mode) */
  let isArchiveMode = $derived(!!debateId);

  let sseConnection = $state(null);
  let archiveLoading = $state(false);

  // Debate title state
  let debateTitle = $state('');
  let titleGenerating = $state(false);
  let titleFadedIn = $state(false);
  let titleError = $state('');

  let projectId = $derived($activeCase?.id);

  // Live web search results
  let liveSearchResults = $state([]);

  // Live activity log
  let liveOutputs = $state([]);
  let currentActivity = $state(null);
  let expandedOutputs = $state(new Set());

  // Activity Strip state
  let cumulativeTokens = $state(0);
  let processingStartTime = $state(null);
  let processingElapsed = $state(0);
  // NOTE: timer IDs are plain variables (not $state) on purpose.
  // They are setInterval handles, not UI state. Declaring them as
  // $state would make the HITL-polling $effect (which both reads and
  // writes hitlPollTimer) re-run on every assignment → effect_update_depth_exceeded.
  let processingTimer;
  let lastRoundTokens = $state(0);

  // Workflow phase tracking
  let workflowPhase = $state(null);
  let workflowStartTime = $state(null);
  let workflowElapsed = $state(0);
  let workflowTimer;

  // RAG context preview toggle
  let showRAGContextPreview = $state(false);

  // Plan 19: Modals state
  let showContinueModal = $state(false);
  let showForkModal = $state(false);
  let isContinueSubmitting = $state(false);
  let isForkSubmitting = $state(false);

  // Load debate from archive when debateId is provided
  onMount(async () => {
    if (debateId) {
      archiveLoading = true;
      error.set(null);
      try {
        const debate = await getDebate(debateId);
        currentDebate.set(debate);
        if (debate.title) {
          debateTitle = debate.title;
          titleFadedIn = true;
        }
      } catch (err) {
        error.set(err.message || t('error.debateNotFound'));
      } finally {
        archiveLoading = false;
      }
    }
  });

  // Auto-start debate when navigated from "Neue Debatte" page
  $effect(() => {
    if ($autoStartDebate && $currentDebate && $currentDebate.status === 'pending') {
      autoStartDebate.set(false);
      setTimeout(() => {
        handleStartDebate();
      }, 200);
    }
  });

  // Reconnect SSE for running debates, or when loading a debate from archive
  $effect(() => {
    if ($currentDebate && (isArchiveMode || $currentDebate.status === 'running') && !sseConnection && !archiveLoading) {
      sseConnection = createSSE($currentDebate.debate_id, {
        onEvent: (event) => { handleSSEEvent(event); },
        onOpen: () => { sseConnected.set(true); },
        onClose: () => { sseConnected.set(false); },
        onError: (err) => { if (import.meta.env.DEV) console.error('SSE error:', err); },
      });
    }
  });

  // Clear stale debate when project changes
  let lastProjectId = $state(null);
  $effect(() => {
    if (projectId && projectId !== lastProjectId) {
      if (lastProjectId !== null) {
        currentDebate.set(null);
        liveOutputs = [];
        liveSearchResults = [];
        currentActivity = null;
        expandedOutputs = new Set();
      }
      lastProjectId = projectId;
    }
  });

  // Cleanup SSE, timers, and workflow state on destroy
  onDestroy(() => {
    if (sseConnection) sseConnection.close();
    sseConnection = null;
    if (processingTimer) clearInterval(processingTimer);
    if (workflowTimer) clearInterval(workflowTimer);
    if (hitlPollTimer) clearInterval(hitlPollTimer);
    resetWorkflow();
    currentDebate.set(null);
  });

  async function handleStartDebate() {
    if (!$currentDebate) return;

    loading.set(true);
    error.set(null);
    liveOutputs = [];
    liveSearchResults = [];
    currentActivity = null;
    expandedOutputs = new Set();
    cumulativeTokens = 0;
    processingStartTime = null;
    processingElapsed = 0;
    lastRoundTokens = 0;
    workflowPhase = null;
    workflowStartTime = null;
    workflowElapsed = 0;
    debateTitle = '';
    titleGenerating = false;
    titleFadedIn = false;
    if (processingTimer) { clearInterval(processingTimer); processingTimer = null; }
    if (workflowTimer) { clearInterval(workflowTimer); workflowTimer = null; }
    resetWorkflow();

    sseConnection = createSSE($currentDebate.debate_id, {
      onEvent: (event) => { handleSSEEvent(event); },
      onOpen: () => { sseConnected.set(true); },
      onClose: () => { sseConnected.set(false); },
      onError: (err) => { if (import.meta.env.DEV) console.error('SSE error:', err); },
    });

    try {
      const result = await startDebate($currentDebate.debate_id);
      currentDebate.set({ ...$currentDebate, ...result });
    } catch (err) {
      error.set(err.message);
    } finally {
      loading.set(false);
    }
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

  function handleSSEEvent(event) {
    if (import.meta.env.DEV) console.log('SSE event:', event);

    try { handleWorkflowSSE(event); } catch (e) {
      if (import.meta.env.DEV) console.warn('Workflow SSE mapping error:', e);
    }

    // T-11: Wire SSE events to feedback store
    if (event.type === 'workflow_started' && event.request_id) {
      feedbackStore.setRequestId(event.request_id);
      feedbackStore.logActivity('workflow', 'system', 'Workflow started', { request_id: event.request_id });
    }
    if (event.type === 'llm.call_started') {
      feedbackStore.setLlmState('calling', event.model || null, event.provider || null);
      feedbackStore.logActivity('llm', event.role || 'system', `LLM calling ${event.model || '…'} (${event.provider || ''})`, {
        node_id: event.node_id, role: event.role, round: event.round, model: event.model,
      });
    }
    if (event.type === 'llm.error') {
      feedbackStore.setLlmState('error');
      feedbackStore.reportError(event.error_class || 'unknown', event.message || 'LLM error', event.raw_error, event.node_id);
    }

    if (event.type === 'title_generating') {
      titleGenerating = true;
      titleFadedIn = false;
      titleError = '';
      return;
    }

    if (event.type === 'title_ready' && event.title) {
      debateTitle = event.title;
      titleGenerating = false;
      titleError = '';
      setTimeout(() => { titleFadedIn = true; }, 50);
      if ($currentDebate) {
        currentDebate.set({ ...$currentDebate, title: event.title });
      }
      addToast({ message: t('toast.titleGenerated') || 'Titel generiert', type: 'success', timeout: 3000 });
      return;
    }

    if (event.type === 'title_error') {
      titleGenerating = false;
      titleError = event.message || t('toast.titleError') || 'Titelgenerierung fehlgeschlagen';
      addToast({ message: titleError, type: 'error', timeout: 5000 });
      return;
    }

    if (event.type === 'status_change' && event.status) {
      currentDebate.set({ ...$currentDebate, status: event.status });
      if (event.status === 'completed' || event.status === 'failed') {
        currentActivity = null;
        workflowPhase = null;
        stopProcessingTimer();
        stopWorkflowTimer();
        // T-11: Clear feedback LLM state on debate completion
        feedbackStore.setLlmState('idle');
        feedbackStore.clearStatus();
        feedbackStore.logActivity('workflow', 'system',
          event.status === 'completed' ? 'Debate completed' : 'Debate failed',
        );
        handleRefreshStatus();
      }
      return;
    }

    if (event.type === 'round_update' && event.data) {
      // Handle round_update events from SSE (for completed debates)
      const roundData = event.data;
      const roundNum = event.round;
      if (roundData.consensus !== undefined) {
        currentDebate.set({
          ...$currentDebate,
          current_round: roundNum,
          consensus_score: roundData.consensus,
        });
      }
      // Trigger a full status refresh to populate rounds array
      handleRefreshStatus();
      return;
    }

    if (event.status === 'completed' || event.status === 'failed') {
      currentDebate.set({ ...$currentDebate, status: event.status });
      currentActivity = null;
      workflowPhase = null;
      stopProcessingTimer();
      stopWorkflowTimer();
      handleRefreshStatus();
      return;
    }

    if (event.round !== undefined && event.consensus !== undefined) {
      currentDebate.set({
        ...$currentDebate,
        current_round: event.round + 1,
        consensus_score: event.consensus,
      });
      if (event.total_tokens) lastRoundTokens = event.total_tokens;
      currentActivity = null;
      workflowPhase = null;
      stopProcessingTimer();
      stopWorkflowTimer();
      return;
    }

    if (event.type === 'workflow_started') {
      workflowPhase = { type: 'workflow_started', message: event.message };
      startWorkflowTimer();
      return;
    }

    if (event.type === 'agent_preparing') {
      workflowPhase = {
        type: 'agent_preparing', phase: event.phase, role: event.role,
        round: event.round, agent_index: event.agent_index, agent_total: event.agent_total,
      };
      if (!workflowTimer) startWorkflowTimer();
      return;
    }

    if (event.type === 'llm_call_started') {
      workflowPhase = {
        type: 'llm_call_started', role: event.role, model: event.model,
        provider: event.provider, round: event.round,
        agent_index: event.agent_index, agent_total: event.agent_total,
      };
      if (!workflowTimer) startWorkflowTimer();
      return;
    }

    if (event.role && event.round && event.profile && !event.content) {
      currentActivity = {
        round: event.round, role: event.role, profile: event.profile,
        model: event.model || '', provider: event.provider || '',
        agent_index: event.agent_index ?? 0, agent_total: event.agent_total ?? 0,
      };
      workflowPhase = null;
      stopWorkflowTimer();
      startProcessingTimer();
      return;
    }

    if (event.role && event.round && event.content) {
      const profile = currentActivity?.profile || '';
      const model = currentActivity?.model || event.model || '';
      const tokensOut = event.tokens_out || event.tokens_used || 0;
      const tokensIn = event.tokens_in || 0;
      cumulativeTokens += tokensOut;
      stopProcessingTimer();
      currentActivity = null;
      workflowPhase = null;
      stopWorkflowTimer();
      // T-11: Clear LLM calling state and log agent completion
      feedbackStore.setLlmState('idle');
      feedbackStore.logActivity('node', event.role,
        `${event.role} completed (Round ${event.round}, ${tokensOut} tokens, ${event.duration_ms || 0}ms)`,
        { round: event.round, tokens_out: tokensOut, duration_ms: event.duration_ms },
      );
      liveOutputs = [...liveOutputs, {
        round: event.round, role: event.role, content: event.content,
        tokens: event.tokens_used, tokens_in: tokensIn, tokens_out: tokensOut,
        duration_ms: event.duration_ms || 0, model, profile, timestamp: new Date(),
      }];
    }

    if (event.type === 'web_search' || event.event === 'web_search') {
      liveSearchResults = [...liveSearchResults, {
        round: event.round || 0, role: event.role || '',
        query: event.query || '', results: event.results || [],
        result_count: event.result_count || 0, timestamp: new Date(),
      }];
      return;
    }

    // HITL events
    if (event.type === 'hitl_query') {
      currentAgentQuery.set({
        interrupt_id: event.interrupt_id, agent_role: event.agent_role,
        question: event.question, context: event.context || '',
        confidence: event.confidence, reason: event.reason, round: event.round,
      });
      // Update hitlStatus immediately so modal has active_interrupt before polling completes
      hitlStatus.update(status => ({
        ...status,
        active_interrupt: {
          interrupt_id: event.interrupt_id,
          agent_role: event.agent_role,
          question: event.question,
          context: event.context || '',
          round: event.round,
          created_at: new Date().toISOString(),
          timeout_seconds: 300,
          status: 'waiting',
          elapsed_seconds: 0,
        },
      }));
      showAgentQueryModal.set(true);
      // Poll to get server-side elapsed_seconds and confirm state
      refreshHITLStatus();
      return;
    }

    if (event.type === 'hitl_response') {
      showAgentQueryModal.set(false);
      currentAgentQuery.set(null);
      refreshHITLStatus();
      refreshHITLInteractions();
      return;
    }

    if (event.type === 'hitl_inject' || event.type === 'hitl_inject_consumed') {
      refreshHITLStatus();
      refreshHITLInteractions();
      return;
    }

    if (event.type === 'hitl_pause' || event.type === 'hitl_paused' || event.type === 'hitl_resumed') {
      refreshHITLStatus();
      return;
    }

    if (event.type === 'hitl_timeout') {
      showAgentQueryModal.set(false);
      currentAgentQuery.set(null);
      refreshHITLStatus();
      return;
    }
  }

  // HITL status refresh
  let hitlPollTimer;

  async function refreshHITLStatus() {
    if (!$currentDebate) return;
    try {
      const status = await getHITLStatus($currentDebate.debate_id);
      hitlStatus.set(status);
    } catch (e) { if (import.meta.env.DEV) console.warn('[DebateView] HITL status refresh failed:', e); }
    // Workflow-state poll: only meaningful for workflow-driven
    // debates (session ids start with 'wf-').  Legacy debates
    // live in the project-scoped debate store, not the workflow
    // state backend, so polling them just produces a 404 in the
    // console (issue 2026-06-18).
    const id = $currentDebate.debate_id;
    if (typeof id === 'string' && id.startsWith('wf-')) {
      try {
        const { getWorkflowState } = await import('../lib/workflowExec.js');
        const state = await getWorkflowState(id);
        // local poll result is consumed by HITL-pause UI;
        // no global store needed for the poll result itself.
      } catch (e) { if (import.meta.env.DEV) console.warn('[DebateView] workflow state refresh failed:', e); }
    }
  }

  async function refreshHITLInteractions() {
    if (!$currentDebate) return;
    try {
      const result = await getInteractions($currentDebate.debate_id, { limit: 100 });
      hitlInteractions.set(result.interactions || []);
    } catch (e) { if (import.meta.env.DEV) console.warn('[DebateView] HITL interactions refresh failed:', e); }
  }

  $effect(() => {
    if ($currentDebate?.status === 'running' && $currentDebate?.hitl_enabled) {
      if (hitlPollTimer) clearInterval(hitlPollTimer);
      refreshHITLStatus();
      refreshHITLInteractions();
      hitlPollTimer = setInterval(() => {
        refreshHITLStatus();
        refreshHITLInteractions();
      }, 5000);
    } else {
      if (hitlPollTimer) { clearInterval(hitlPollTimer); hitlPollTimer = null; }
    }
  });

  async function handleRefreshStatus() {
    if (!$currentDebate) return;
    error.set(null);
    try {
      const status = await getDebate($currentDebate.debate_id);
      currentDebate.set({ ...$currentDebate, ...status });
      if (status.title && !debateTitle) {
        debateTitle = status.title;
        titleGenerating = false;
        titleFadedIn = true;
      }
    } catch (err) {
      error.set(err.message);
    }
  }

  let isCancelling = $state(false);
  async function handleCancelDebate() {
    if (!$currentDebate) return;
    isCancelling = true;
    error.set(null);
    try {
      const result = await cancelDebate($currentDebate.debate_id);
      if (result.status === 'completed' || result.status === 'failed') {
        currentDebate.set({ ...$currentDebate, status: result.status });
        currentActivity = null;
        workflowPhase = null;
        stopProcessingTimer();
        stopWorkflowTimer();
        handleRefreshStatus();
      }
    } catch (err) {
      error.set(err.message);
    } finally {
      isCancelling = false;
    }
  }

  function toggleExpand(key) {
    const next = new Set(expandedOutputs);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    expandedOutputs = next;
  }

  let statusBadgeClass = $derived((() => {
    switch ($currentDebate?.status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'running': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'completed': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'failed': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
    }
  })());

  let statusLabel = $derived($currentDebate?.status ? t(`status.${$currentDebate.status}`) : '');

  let liveOutputsByRound = $derived(liveOutputs.reduce((acc, output) => {
    if (!acc[output.round]) acc[output.round] = [];
    acc[output.round].push(output);
    return acc;
  }, {}));

  let displayRounds = $derived(($currentDebate?.status === 'completed' || $currentDebate?.status === 'failed') && $currentDebate?.rounds?.length > 0
    ? $currentDebate.rounds
    : null);

  function roleEmoji(role) {
    switch (role) {
      case 'strategist': return '🎯';
      case 'critic': return '🔍';
      case 'optimizer': return '⚡';
      case 'moderator': return '⚖️';
      default: return '🤖';
    }
  }

  function roleColor(role) {
    switch (role) {
      case 'strategist': return 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-600';
      case 'critic': return 'border-red-400 bg-red-50 dark:bg-red-900/20 dark:border-red-600';
      case 'optimizer': return 'border-amber-400 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-600';
      case 'moderator': return 'border-purple-400 bg-purple-50 dark:bg-purple-900/20 dark:border-purple-600';
      default: return 'border-gray-400 bg-gray-50 dark:bg-gray-800 dark:border-gray-600';
    }
  }

  function roleHeaderColor(role) {
    switch (role) {
      case 'strategist': return 'text-blue-700 dark:text-blue-300';
      case 'critic': return 'text-red-700 dark:text-red-300';
      case 'optimizer': return 'text-amber-700 dark:text-amber-300';
      case 'moderator': return 'text-purple-700 dark:text-purple-300';
      default: return 'text-gray-700 dark:text-gray-300';
    }
  }

  function formatElapsed(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  // Derived state for ActivityStrip
  let agentCount = $derived(currentActivity?.agent_total || $currentDebate?.agent_profile?.length || 0);
  let activeAgentIndex = $derived(currentActivity?.agent_index ?? -1);
  let completedInRound = $derived(liveOutputs.filter(o => o.round === ($currentDebate?.current_round || 0)).length);
  let isProcessing = $derived($currentDebate?.status === 'running' && currentActivity !== null);
  let isBetweenAgents = $derived($currentDebate?.status === 'running' && currentActivity === null && liveOutputs.length > 0);

  // Plan 19: Check for parent debate (fork info)
  let parentDebateId = $derived($currentDebate?.parent_debate_id || $currentDebate?.fork_info?.parent_debate_id || null);
  let isCompleted = $derived($currentDebate?.status === 'completed' || $currentDebate?.status === 'failed');
</script>

<div class="space-y-6">
  <!-- Plan 19: Continue Debate Modal -->
  {#if showContinueModal}
    <ContinueDebateModal
      debateId={$currentDebate?.debate_id}
      debateTitle={debateTitle}
      onClose={() => showContinueModal = false}
      onCreated={(result) => {
        currentDebate.set(result);
        showContinueModal = false;
        navigate(`debate/${result.debate_id}`);
      }}
    />
  {/if}

  <!-- Plan 19: Fork Debate Modal -->
  {#if showForkModal}
    <ForkDebateModal
      debateId={$currentDebate?.debate_id}
      debateTitle={debateTitle}
      onClose={() => showForkModal = false}
      onCreated={(result) => {
        showForkModal = false;
        navigate(`debate/${result.debate_id}`);
      }}
    />
  {/if}

  <!-- Agent Query Modal (overlay) -->
  <AgentQueryModal debateId={$currentDebate?.debate_id} />

  <!-- Header with optional back button for archive mode -->
  <div class="flex items-center gap-3">
    {#if isArchiveMode}
      <button
        class="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
        onclick={() => navigate('dashboard')}
      >
        ← {t('debate.backToOverview')}
      </button>
      <span class="text-gray-400 dark:text-gray-500" aria-hidden="true">|</span>
    {/if}
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
      {isArchiveMode ? t('debate.archiveTitle') : t('debate.title')}
    </h2>
    {#if $currentDebate?.case_title}
      <span class="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
        📋 {$currentDebate.case_title}
      </span>
    {:else if $currentDebate?.project_name}
      <span class="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
        📁 {$currentDebate.project_name}
      </span>
    {/if}
    {#if $currentDebate?.created_at}
      <span class="text-sm text-gray-500 dark:text-gray-400 ml-auto">
        {formatDate($currentDebate.created_at)}
      </span>
    {/if}
  </div>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  <!-- Archive loading indicator -->
  {#if archiveLoading}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 border border-gray-200 dark:border-gray-700 text-center">
      <div class="flex justify-center gap-1 mb-3">
        <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
        <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
        <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
      </div>
      <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
    </div>
  {/if}

  <!-- Debate title -->
  {#if $currentDebate && (titleGenerating || debateTitle || titleError)}
    <div class="transition-all duration-500 ease-out"
         class:opacity-0={!titleFadedIn && !titleGenerating && !titleError}
         class:opacity-100={titleFadedIn || titleGenerating || titleError}
         class:translate-y-0={titleFadedIn || titleGenerating || titleError}
         class:-translate-y-2={!titleFadedIn && !titleGenerating && !titleError}>
      {#if titleGenerating}
        <div class="px-4 py-3 rounded-xl bg-gradient-to-r from-gray-100 to-gray-50 dark:from-gray-800 dark:to-gray-700/80
                    border border-gray-200 dark:border-gray-600 shadow-sm">
          <span class="text-lg font-semibold text-gray-400 dark:text-gray-500 animate-pulse tracking-wide">
            {t('debate.titlePlaceholder')}
          </span>
        </div>
      {:else if titleError}
        <div class="px-4 py-3 rounded-xl bg-gradient-to-r from-red-50 to-amber-50 dark:from-red-900/20 dark:to-amber-900/10
                    border border-red-200 dark:border-red-800 shadow-sm">
          <span class="text-lg font-semibold text-red-500 dark:text-red-400">
            ⚠️ {titleError}
          </span>
        </div>
      {:else if debateTitle}
        <div class="px-4 py-3 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/20
                    border border-blue-200 dark:border-blue-700 shadow-sm">
          <h3 class="text-xl font-bold text-gray-900 dark:text-white leading-snug tracking-tight">
            {debateTitle}
          </h3>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Plan 19: Parent debate link -->
  {#if parentDebateId}
    <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-3 text-sm">
      <span class="text-blue-700 dark:text-blue-300">
        🔗 {t('debate.forkedFrom')}:
        <a href="#/debate/{parentDebateId}" class="font-medium underline hover:text-blue-800 dark:hover:text-blue-200">
          {parentDebateId.slice(0, 8)}...
        </a>
      </span>
    </div>
  {/if}

  <!-- Current debate status -->
  {#if $currentDebate}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {isArchiveMode ? t('debate.archiveTitle') : t('debate.currentDebate')}
        </h3>
        <div class="flex items-center space-x-3">
          {#if $sseConnected}
            <span class="flex items-center text-xs text-green-600 dark:text-green-400">
              <span class="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></span>
              {t('debate.sseConnected')}
            </span>
          {/if}
          <span class="px-2 py-1 text-xs font-medium rounded-full {statusBadgeClass}">
            {statusLabel}
          </span>
        </div>
      </div>

      <!-- Meta information row -->
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm mb-3">
        <div>
          <span class="text-gray-500 dark:text-gray-400">{t('debate.id')}: </span>
          <code class="font-mono text-gray-800 dark:text-gray-200 text-xs">{$currentDebate.debate_id}</code>
        </div>
        {#if $currentDebate.created_at}
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('debate.date')}: </span>
            <span class="text-gray-800 dark:text-gray-200">{formatDate($currentDebate.created_at)}</span>
          </div>
        {/if}
        {#if $currentDebate.llm_profile_id}
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('debate.model')}: </span>
            <span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{$currentDebate.llm_profile_model || $currentDebate.llm_profile_id}</span>
          </div>
        {/if}
        {#if $currentDebate.language}
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('debate.language')}: </span>
            <span class="text-gray-800 dark:text-gray-200 uppercase">{$currentDebate.language}</span>
          </div>
        {/if}
        {#if $currentDebate.rag_enabled}
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('documents.ragContext')}: </span>
            <span class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-full bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
              📚 {$currentDebate.rag_document_count} {t('documents.ragEnabled')}
            </span>
          </div>
        {/if}
      </div>

      <!-- Round and consensus row -->
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        {#if $currentDebate.current_round !== undefined}
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('debate.round')}: </span>
            <span class="text-gray-800 dark:text-gray-200 font-medium">
              {#if $currentDebate.current_round > ($currentDebate.max_rounds || 0)}
                {t('debate.roundOverMax', { current: $currentDebate.current_round, max: $currentDebate.max_rounds })}
              {:else}
                {t('debate.roundInfo', { current: $currentDebate.current_round, max: $currentDebate.max_rounds || '?' })}
              {/if}
            </span>
          </div>
        {/if}
        {#if $currentDebate.consensus_score !== undefined && $currentDebate.consensus_score !== null}
          <div class="flex items-center gap-2">
            <span class="text-gray-500 dark:text-gray-400">{t('debate.consensus')}:</span>
            <div class="w-24 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                class="h-2 rounded-full transition-all duration-500 {$currentDebate.consensus_score === 0 ? 'bg-red-500' : 'bg-blue-600'}"
                style="width: {Math.max(2, $currentDebate.consensus_score * 100)}%"
              ></div>
            </div>
            <span class="text-gray-800 dark:text-gray-200 font-medium">
              {formatNumber($currentDebate.consensus_score, { style: 'percent' })}
            </span>
          </div>
        {/if}
      </div>

      <!-- Anomaly warnings -->
      {#if $currentDebate.anomalies?.length > 0}
        <div class="mt-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
          <p class="text-sm font-medium text-amber-800 dark:text-amber-200 mb-1">{t('debate.llmFailureWarning')}</p>
          <p class="text-xs text-amber-700 dark:text-amber-300">{t('debate.degradedConsensus')}</p>
          <ul class="mt-2 space-y-1">
            {#each $currentDebate.anomalies as anomaly}
              <li class="text-xs text-amber-600 dark:text-amber-400 font-mono">• {anomaly}</li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- RAG Context Preview -->
      {#if $currentDebate.rag_enabled && $currentDebate.rag_context_preview}
        <div class="mt-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg p-3">
          <button
            class="flex items-center justify-between w-full text-left"
            onclick={() => showRAGContextPreview = !showRAGContextPreview}
          >
            <span class="text-sm font-medium text-purple-800 dark:text-purple-200 flex items-center gap-2">
              📚 {t('documents.ragPreview')}
              <span class="text-xs font-normal text-purple-600 dark:text-purple-400">
                ({$currentDebate.rag_document_count} {t('documents.ragEnabled')})
              </span>
            </span>
            <span class="text-purple-600 dark:text-purple-400 text-xs">
              {showRAGContextPreview ? '▲' : '▼'}
            </span>
          </button>
          {#if showRAGContextPreview}
            <pre class="mt-2 text-xs text-purple-700 dark:text-purple-300 whitespace-pre-wrap font-mono bg-purple-100/50 dark:bg-purple-900/30 rounded p-2 max-h-60 overflow-y-auto">{$currentDebate.rag_context_preview}</pre>
          {/if}
        </div>
      {/if}

      <!-- Plan 19: Action buttons for completed debates -->
      {#if !isArchiveMode}
      <div class="mt-4 flex space-x-3">
        {#if $currentDebate.status === 'pending'}
          <button
            class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:hover:bg-green-600 transition-colors disabled:opacity-50"
            onclick={handleStartDebate}
            disabled={$loading}
          >
            {$loading ? t('debate.starting') : t('debate.startButton')}
          </button>
        {/if}
        {#if $currentDebate.status === 'running'}
          <PauseControls debateId={$currentDebate.debate_id} />
          <button
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onclick={handleCancelDebate}
            disabled={isCancelling}
          >
            {isCancelling ? t('debate.cancelling') : t('debate.cancelButton')}
          </button>
        {/if}
        {#if isCompleted}
          <!-- Plan 19: Continue & Fork buttons for completed debates -->
          <button
            class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:hover:bg-indigo-600 transition-colors disabled:opacity-50 text-sm"
            onclick={() => showContinueModal = true}
          >
            🔄 {t('debate.continueButton')}
          </button>
          <button
            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:hover:bg-purple-600 transition-colors disabled:opacity-50 text-sm"
            onclick={() => showForkModal = true}
          >
            🍴 {t('debate.forkButton')}
          </button>
        {/if}
        <button
          class="px-4 py-2 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
          onclick={handleRefreshStatus}
        >
          {t('debate.refreshStatus')}
        </button>
      </div>
      {/if}
    </div>

    <!-- Activity Strip -->
    <DebateActivityStrip
      currentDebate={$currentDebate}
      {currentActivity}
      {workflowPhase}
      {liveOutputs}
      {isProcessing}
      {isBetweenAgents}
      {processingElapsed}
      {workflowElapsed}
      {cumulativeTokens}
      {agentCount}
      {activeAgentIndex}
      {completedInRound}
    />

    <!-- Workflow Visualization Graph -->
    {#if $currentDebate.status === 'running' || $currentDebate.status === 'completed' || $currentDebate.status === 'failed'}
      <WorkflowGraph debateId={$currentDebate.debate_id} isRunning={$currentDebate.status === 'running'} />
    {/if}

    <!-- HITL Inject Panel -->
    {#if $currentDebate.status === 'running' && $currentDebate.hitl_enabled}
      <InjectPanel debateId={$currentDebate.debate_id} />
    {/if}

    <!-- Live debate view -->
    {#if $currentDebate.status === 'running'}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        <div class="p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white flex items-center gap-2">
            <span class="animate-pulse w-3 h-3 bg-blue-500 rounded-full"></span>
            {t('debate.timelineTitle')}
          </h3>
        </div>
        <div class="p-4 space-y-6 max-h-[70vh] overflow-y-auto">
          {#each Object.entries(liveOutputsByRound) as [round, outputs]}
            <div>
              <div class="flex items-center gap-2 mb-3">
                <span class="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                  {t('timeline.round', { num: round })}
                </span>
              </div>
              <div class="space-y-3">
                {#each outputs as output, i}
                  {@const key = `live-r${output.round}-${output.role}-${i}`}
                  {@const isExpanded = expandedOutputs.has(key)}
                  {@const isLong = output.content?.length > 400}
                  <div class="border-l-4 rounded-lg {roleColor(output.role)} p-4">
                    <div class="flex items-center justify-between mb-2">
                      <div class="flex items-center gap-2">
                        <span class="font-semibold text-sm {roleHeaderColor(output.role)}">
                          {roleEmoji(output.role)} {output.role}
                        </span>
                        {#if output.model}
                          <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">{output.model}</span>
                        {:else if output.profile}
                          <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">{output.profile}</span>
                        {/if}
                      </div>
                      <div class="flex items-center gap-2">
                        {#if output.duration_ms}
                          <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">⏱ {formatElapsed(output.duration_ms)}</span>
                        {/if}
                        <span class="text-xs text-gray-400 dark:text-gray-500">{tn(output.tokens_out || output.tokens, { one: 'audit.tokens.one', other: 'audit.tokens.other' })}</span>
                      </div>
                    </div>
                    <div class="text-sm text-gray-700 dark:text-gray-300">
                      {#if isLong && !isExpanded}
                        <MarkdownRenderer content={output.content.substring(0, 400) + '…'} />
                        <button class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block" onclick={() => toggleExpand(key)}>
                          ▼ Show full response ({output.content.length} chars)
                        </button>
                      {:else}
                        <MarkdownRenderer content={output.content} />
                        {#if isLong}
                          <button class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block" onclick={() => toggleExpand(key)}>
                            ▲ Collapse
                          </button>
                        {/if}
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/each}

          <!-- Web search results -->
          {#if liveSearchResults.length > 0}
            {#each liveSearchResults as search, i}
              {@const searchKey = `search-${i}`}
              {@const isSearchExpanded = expandedOutputs.has(searchKey)}
              <div class="border-l-4 border-teal-400 bg-teal-50 dark:bg-teal-900/20 dark:border-teal-600 rounded-lg p-4">
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-2">
                    <span class="font-semibold text-sm text-teal-700 dark:text-teal-300">🔍 {t('search.webResearch')}</span>
                    {#if search.role}
                      <span class="text-xs text-teal-500 dark:text-teal-400">— {search.role} — {t('timeline.round', { num: search.round })}</span>
                    {/if}
                  </div>
                  <span class="text-xs text-gray-400 dark:text-gray-500">
                    {search.result_count || search.results?.length || 0} {t('search.source')}{(search.result_count || search.results?.length || 0) !== 1 ? 's' : ''}
                  </span>
                </div>
                {#if search.query}
                  <p class="text-xs text-teal-600 dark:text-teal-400 mb-2 font-mono">{t('search.resultsFor')}: "{search.query}"</p>
                {/if}
                {#if search.results?.length > 0}
                  <div class="space-y-1">
                    {#each (isSearchExpanded ? search.results : search.results.slice(0, 3)) as result}
                      <div class="flex items-start gap-2 text-xs">
                        <span class="text-teal-500 mt-0.5">•</span>
                        <div>
                          {#if result.url}
                            <a href={result.url} target="_blank" rel="noopener noreferrer" class="text-teal-700 dark:text-teal-300 hover:underline font-medium">
                              {result.title || result.url}
                            </a>
                          {:else}
                            <span class="text-gray-700 dark:text-gray-300 font-medium">{result.title || '—'}</span>
                          {/if}
                          {#if result.snippet}
                            <p class="text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{result.snippet}</p>
                          {/if}
                        </div>
                      </div>
                    {/each}
                  </div>
                  {#if search.results.length > 3 && !isSearchExpanded}
                    <button class="text-teal-600 dark:text-teal-400 hover:underline text-xs mt-2 inline-block" onclick={() => toggleExpand(searchKey)}>
                      ▼ {t('timeline.expand', { count: search.results.length })}
                    </button>
                  {:else if search.results.length > 3 && isSearchExpanded}
                    <button class="text-teal-600 dark:text-teal-400 hover:underline text-xs mt-2 inline-block" onclick={() => toggleExpand(searchKey)}>
                      ▲ {t('timeline.collapse')}
                    </button>
                  {/if}
                {:else}
                  <p class="text-xs text-gray-500 dark:text-gray-400 italic">{t('search.noResults')}</p>
                {/if}
              </div>
            {/each}
          {/if}

          <!-- Current agent being processed -->
          {#if currentActivity}
            <div class="border-l-4 border-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
              <div class="flex items-center gap-2">
                <span class="animate-pulse w-3 h-3 bg-blue-500 rounded-full"></span>
                <span class="font-semibold text-sm text-blue-700 dark:text-blue-300">
                  {roleEmoji(currentActivity.role)} {currentActivity.role}
                </span>
                <span class="text-xs text-blue-500 dark:text-blue-400">— {t('timeline.round', { num: currentActivity.round })} — {t('timeline.thinking')}</span>
              </div>
              <div class="mt-2 flex gap-1">
                <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
              </div>
            </div>
          {/if}

          {#if liveOutputs.length === 0 && !currentActivity}
            <p class="text-gray-500 dark:text-gray-400 text-sm text-center py-8">{t('debate.timelinePlaceholder')}</p>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Metadata -->
    {#if displayRounds && displayRounds.length}
      {@const roleSet = new Set(displayRounds.flatMap(r => (r.agent_outputs || []).map(a => a.role_type || a.role)))}
      {@const roles = [...roleSet].filter(Boolean)}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 mb-4">
        <div class="grid grid-cols-1 gap-2 text-sm text-gray-700 dark:text-gray-300">
          <div><span class="font-semibold">Anzahl Runden:</span> {displayRounds.length}</div>
          {#if roles.length}
            <div><span class="font-semibold">Agenten-Rollen:</span> {roles.join(' · ')}</div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Case text display -->
    {#if $currentDebate.case_text || $currentDebate.case?.text}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-3">{t('debate.caseLabel')}</h3>
        <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{$currentDebate.case_text || $currentDebate.case?.text}</p>
      </div>
    {/if}

    <!-- HITL Interaction Timeline -->
    {#if $currentDebate?.hitl_enabled}
      <InteractionTimeline />
    {/if}

    <!-- Completed/Failed debate results -->
    {#if ($currentDebate.status === 'completed' || $currentDebate.status === 'failed') && displayRounds}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        <div class="p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white flex items-center gap-2">
            📊 {t('debate.timelineTitle')}
          </h3>
        </div>
        <div class="p-4 space-y-8 max-h-[80vh] overflow-y-auto">
          {#each displayRounds as round}
            <div>
              <div class="flex items-center gap-3 mb-4">
                <span class="text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-3 py-1 rounded">
                  {t('timeline.round', { num: round.round })}
                </span>
                <div class="flex items-center gap-2">
                  <div class="w-20 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                    <div class="bg-blue-600 h-1.5 rounded-full transition-all" style="width: {(round.consensus * 100)}%"></div>
                  </div>
                  <span class="text-xs text-gray-500 dark:text-gray-400">{(round.consensus * 100).toFixed(1)}%</span>
                </div>
              </div>
              {#if round.agent_outputs?.length > 0}
                <div class="space-y-3">
                  {#each round.agent_outputs as output, i}
                    {@const key = `done-r${round.round}-${output.role}-${i}`}
                    {@const isExpanded = expandedOutputs.has(key)}
                    {@const isLong = output.content?.length > 400}
                    <div class="border-l-4 rounded-lg {roleColor(output.role)} p-4">
                      <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                          <span class="font-semibold text-sm {roleHeaderColor(output.role)}">
                            {roleEmoji(output.role)} {output.role}
                          </span>
                          {#if output.model}
                            <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">{output.model}</span>
                          {/if}
                        </div>
                        <span class="text-xs text-gray-400 dark:text-gray-500">{tn(output.tokens_used || 0, { one: 'audit.tokens.one', other: 'audit.tokens.other' })}</span>
                      </div>
                      <div class="text-sm text-gray-700 dark:text-gray-300">
                        {#if isLong && !isExpanded}
                          <MarkdownRenderer content={output.content.substring(0, 400) + '…'} />
                          <button class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block" onclick={() => toggleExpand(key)}>
                            ▼ Show full response ({output.content.length} chars)
                          </button>
                        {:else}
                          <MarkdownRenderer content={output.content} />
                          {#if isLong}
                            <button class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block" onclick={() => toggleExpand(key)}>
                              ▲ Collapse
                            </button>
                          {/if}
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="text-sm text-gray-400 dark:text-gray-500 italic">{t('timeline.noOutputs')}</p>
              {/if}
            </div>
          {/each}

          <!-- Final verdict -->
          {#if $currentDebate.consensus_score !== undefined && $currentDebate.consensus_score !== null}
            {@const hasAnomalies = $currentDebate.anomalies?.length > 0}
            <div class="border-t-2 border-gray-200 dark:border-gray-600 pt-6">
              <div class="border rounded-lg p-6 {hasAnomalies
                ? 'bg-gradient-to-r from-amber-50 to-red-50 dark:from-amber-900/20 dark:to-red-900/20 border-amber-200 dark:border-amber-800'
                : 'bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 border-green-200 dark:border-green-800'}">
                <h4 class="text-lg font-bold text-gray-800 dark:text-white mb-3 flex items-center gap-2">
                  {hasAnomalies ? '⚠️' : '🏁'} {t('timeline.finalConsensus')}
                  {#if hasAnomalies}
                    <span class="text-sm font-normal text-amber-600 dark:text-amber-400">{t('timeline.degraded')}</span>
                  {/if}
                </h4>
                <div class="flex items-center gap-4 mb-3">
                  <div class="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-4">
                    <div
                      class="h-4 rounded-full transition-all duration-1000 {hasAnomalies
                        ? 'bg-gradient-to-r from-amber-500 to-red-500'
                        : 'bg-gradient-to-r from-blue-500 to-green-500'}"
                      style="width: {Math.max(2, $currentDebate.consensus_score * 100)}%"
                    ></div>
                  </div>
                  <span class="text-2xl font-bold text-gray-800 dark:text-white">
                    {($currentDebate.consensus_score * 100).toFixed(1)}%
                  </span>
                </div>
                <p class="text-sm text-gray-600 dark:text-gray-400">
                  {#if hasAnomalies}
                    {t('debate.degradedConsensus')}
                  {:else}
                    {t('timeline.concludedAfter', { rounds: displayRounds.length, plural: displayRounds.length !== 1 ? 's' : '', percent: ($currentDebate.consensus_score * 100).toFixed(1) })}
                    {#if $currentDebate.consensus_score >= 0.9}
                      <span class="text-green-600 dark:text-green-400 font-medium">{t('timeline.strongConsensus')}</span>
                    {:else if $currentDebate.consensus_score >= 0.7}
                      <span class="text-yellow-600 dark:text-yellow-400 font-medium">{t('timeline.moderateConsensus')}</span>
                    {:else}
                      <span class="text-red-600 dark:text-red-400 font-medium">{t('timeline.lowConsensus')}</span>
                    {/if}
                  {/if}
                </p>

                <!-- Report Generation -->
                <DebateReportPanel debateId={$currentDebate.debate_id} />
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- No rounds fallback -->
    {#if isArchiveMode && ($currentDebate.status === 'completed' || $currentDebate.status === 'failed') && !displayRounds}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 border border-gray-200 dark:border-gray-700 text-center">
        <p class="text-gray-500 dark:text-gray-400">{t('debate.noRounds')}</p>
      </div>
    {/if}
  {/if}
</div>
