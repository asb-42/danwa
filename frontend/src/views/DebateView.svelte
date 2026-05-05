<script>
  import { onMount, onDestroy } from 'svelte';
  import { currentDebate, debates, loading, error, sseConnected, selectedLLMProfile, selectedPromptVariant, selectedPersonas } from '../lib/stores.js';
  import { createDebate, getDebate, startDebate, cancelDebate } from '../lib/api.js';
  import { createSSE } from '../lib/sse.js';
  import { i18n, formatNumber, formatDate, locale } from '../lib/i18n/index.js';
  import MarkdownRenderer from '../components/MarkdownRenderer.svelte';

  /** @type {string|null} Debate ID from route — triggers archive/read-only mode */
  export let debateId = null;
  /** @type {function} Navigation helper from App.svelte */
  export let navigate = () => {};

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  /** True when viewing a past debate (read-only archive mode) */
  $: isArchiveMode = !!debateId;

  let caseText = '';
  let maxRounds = 3;
  let consensusThreshold = 0.8;
  let searchMode = 'off';
  let sseConnection = null;
  let archiveLoading = false;

  // Live web search results — stores search events as they arrive
  let liveSearchResults = []; // { round, role, query, results, timestamp }

  // Live activity log — stores full agent outputs as they arrive
  let liveOutputs = []; // { round, role, content, tokens, tokens_in, tokens_out, duration_ms, model, profile, timestamp }
  let currentActivity = null; // { round, role, profile, model, provider, agent_index, agent_total }
  let expandedOutputs = new Set(); // track which outputs are expanded

  // Activity Strip state
  let cumulativeTokens = 0;
  let processingStartTime = null;
  let processingElapsed = 0;
  let processingTimer = null;
  let lastRoundTokens = 0;

  // Workflow phase tracking — shows what's happening between debate start and first agent
  let workflowPhase = null; // { type, message, phase, role, model, provider, elapsed }
  let workflowStartTime = null;
  let workflowElapsed = 0;
  let workflowTimer = null;

  // Load debate from archive when debateId is provided
  onMount(async () => {
    if (debateId) {
      archiveLoading = true;
      $error = null;
      try {
        const debate = await getDebate(debateId);
        $currentDebate = debate;
      } catch (err) {
        $error = err.message || t('error.debateNotFound');
      } finally {
        archiveLoading = false;
      }
    }
  });

  // Cleanup SSE and timers on destroy
  onDestroy(() => {
    if (sseConnection) {
      sseConnection.close();
    }
    if (processingTimer) {
      clearInterval(processingTimer);
    }
    if (workflowTimer) {
      clearInterval(workflowTimer);
    }
  });

  async function handleCreateDebate() {
    if (!caseText.trim()) {
      $error = t('debate.enterCase');
      return;
    }

    $loading = true;
    $error = null;
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
    if (processingTimer) { clearInterval(processingTimer); processingTimer = null; }
    if (workflowTimer) { clearInterval(workflowTimer); workflowTimer = null; }

    try {
      const response = await createDebate(caseText, {
        max_rounds: maxRounds,
        consensus_threshold: consensusThreshold,
        search_mode: searchMode,
        llm_profile_id: $selectedLLMProfile,
        prompt_variant: $selectedPromptVariant,
        agent_persona_ids: $selectedPersonas,
        language: $locale || 'de',
      });
      $currentDebate = response;
      $debates = [...$debates, response];
      caseText = '';
    } catch (err) {
      $error = err.message;
    } finally {
      $loading = false;
    }
  }

  async function handleStartDebate() {
    if (!$currentDebate) return;

    $loading = true;
    $error = null;
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
    if (processingTimer) { clearInterval(processingTimer); processingTimer = null; }
    if (workflowTimer) { clearInterval(workflowTimer); workflowTimer = null; }

    // Connect SSE FIRST so we receive all events from the start
    sseConnection = createSSE($currentDebate.debate_id, {
      onEvent: (event) => {
        handleSSEEvent(event);
      },
      onOpen: () => { $sseConnected = true; },
      onClose: () => { $sseConnected = false; },
      onError: (err) => { console.error('SSE error:', err); },
    });

    try {
      const result = await startDebate($currentDebate.debate_id);
      $currentDebate = { ...$currentDebate, ...result };
    } catch (err) {
      $error = err.message;
    } finally {
      $loading = false;
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
    if (processingTimer) {
      clearInterval(processingTimer);
      processingTimer = null;
    }
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
    if (workflowTimer) {
      clearInterval(workflowTimer);
      workflowTimer = null;
    }
  }

  function handleSSEEvent(event) {
    console.log('SSE event:', event);

    // status_change: completed or failed
    if (event.status === 'completed' || event.status === 'failed') {
      $currentDebate = { ...$currentDebate, status: event.status };
      currentActivity = null;
      workflowPhase = null;
      stopProcessingTimer();
      stopWorkflowTimer();
      handleRefreshStatus();
      return;
    }

    // round_update
    if (event.round !== undefined && event.consensus !== undefined) {
      $currentDebate = {
        ...$currentDebate,
        current_round: event.round + 1,
        consensus_score: event.consensus,
      };
      if (event.total_tokens) {
        lastRoundTokens = event.total_tokens;
      }
      currentActivity = null;
      workflowPhase = null;
      stopProcessingTimer();
      stopWorkflowTimer();
      return;
    }

    // workflow_started — debate workflow engine has begun
    if (event.type === 'workflow_started') {
      workflowPhase = {
        type: 'workflow_started',
        message: event.message,
      };
      startWorkflowTimer();
      return;
    }

    // agent_preparing — agent is resolving profile or prompts
    if (event.type === 'agent_preparing') {
      workflowPhase = {
        type: 'agent_preparing',
        phase: event.phase,
        role: event.role,
        round: event.round,
        agent_index: event.agent_index,
        agent_total: event.agent_total,
      };
      if (!workflowTimer) startWorkflowTimer();
      return;
    }

    // llm_call_started — LLM API call is about to be made
    if (event.type === 'llm_call_started') {
      workflowPhase = {
        type: 'llm_call_started',
        role: event.role,
        model: event.model,
        provider: event.provider,
        round: event.round,
        agent_index: event.agent_index,
        agent_total: event.agent_total,
      };
      if (!workflowTimer) startWorkflowTimer();
      return;
    }

    // agent_started — enriched with model, provider, agent_index, agent_total
    if (event.role && event.round && event.profile && !event.content) {
      currentActivity = {
        round: event.round,
        role: event.role,
        profile: event.profile,
        model: event.model || '',
        provider: event.provider || '',
        agent_index: event.agent_index ?? 0,
        agent_total: event.agent_total ?? 0,
      };
      workflowPhase = null;
      stopWorkflowTimer();
      startProcessingTimer();
      return;
    }

    // agent_output — full content arrives here (enriched with real tokens + duration)
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
      liveOutputs = [...liveOutputs, {
        round: event.round,
        role: event.role,
        content: event.content,
        tokens: event.tokens_used,
        tokens_in: tokensIn,
        tokens_out: tokensOut,
        duration_ms: event.duration_ms || 0,
        model: model,
        profile: profile,
        timestamp: new Date(),
      }];
    }

    // web_search — search activity feedback
    if (event.type === 'web_search' || event.event === 'web_search') {
      liveSearchResults = [...liveSearchResults, {
        round: event.round || 0,
        role: event.role || '',
        query: event.query || '',
        results: event.results || [],
        result_count: event.result_count || 0,
        timestamp: new Date(),
      }];
      return;
    }
  }

  async function handleRefreshStatus() {
    if (!$currentDebate) return;

    try {
      const status = await getDebate($currentDebate.debate_id);
      $currentDebate = { ...$currentDebate, ...status };
    } catch (err) {
      $error = err.message;
    }
  }

  let isCancelling = false;
  async function handleCancelDebate() {
    if (!$currentDebate) return;
    isCancelling = true;
    try {
      const result = await cancelDebate($currentDebate.debate_id);
      // If debate already completed/failed (race condition), update UI immediately
      if (result.status === 'completed' || result.status === 'failed') {
        $currentDebate = { ...$currentDebate, status: result.status };
        currentActivity = null;
        workflowPhase = null;
        stopProcessingTimer();
        stopWorkflowTimer();
        handleRefreshStatus();
      }
      // Otherwise the SSE stream will deliver the failed status_change event
    } catch (err) {
      $error = err.message;
    } finally {
      isCancelling = false;
    }
  }

  function toggleExpand(key) {
    if (expandedOutputs.has(key)) {
      expandedOutputs.delete(key);
      expandedOutputs = expandedOutputs; // trigger reactivity
    } else {
      expandedOutputs.add(key);
      expandedOutputs = expandedOutputs;
    }
  }

  $: statusBadgeClass = (() => {
    switch ($currentDebate?.status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'running': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'completed': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'failed': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
    }
  })();

  $: statusLabel = $currentDebate?.status ? t(`status.${$currentDebate.status}`) : '';

  // Group live outputs by round
  $: liveOutputsByRound = liveOutputs.reduce((acc, output) => {
    if (!acc[output.round]) acc[output.round] = [];
    acc[output.round].push(output);
    return acc;
  }, {});

  // Determine which data source to show for completed/failed debates
  $: displayRounds = ($currentDebate?.status === 'completed' || $currentDebate?.status === 'failed') && $currentDebate?.rounds?.length > 0
    ? $currentDebate.rounds
    : null;

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

  // Activity Strip helpers
  function roleDotColor(role) {
    switch (role) {
      case 'strategist': return 'bg-blue-500';
      case 'critic': return 'bg-red-500';
      case 'optimizer': return 'bg-amber-500';
      case 'moderator': return 'bg-violet-500';
      default: return 'bg-zinc-500';
    }
  }

  function roleTextColor(role) {
    switch (role) {
      case 'strategist': return 'text-blue-400';
      case 'critic': return 'text-red-400';
      case 'optimizer': return 'text-amber-400';
      case 'moderator': return 'text-violet-400';
      default: return 'text-zinc-400';
    }
  }

  function roleVerbKey(role) {
    switch (role) {
      case 'strategist': return 'feedback.analysing';
      case 'critic': return 'feedback.checking';
      case 'optimizer': return 'feedback.optimizing';
      case 'moderator': return 'feedback.evaluating';
      default: return 'feedback.analysing';
    }
  }

  function formatElapsed(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function formatTokens(n) {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
  }

  // Number of agents in the current round (from agent_started events)
  $: agentCount = currentActivity?.agent_total || $currentDebate?.agent_profile?.length || 0;
  // Index of the currently active agent (0-based)
  $: activeAgentIndex = currentActivity?.agent_index ?? -1;
  // How many agents have completed so far in the current round
  $: completedInRound = liveOutputs.filter(o => o.round === ($currentDebate?.current_round || 0)).length;
  // Whether the debate is actively running with an agent processing
  $: isProcessing = $currentDebate?.status === 'running' && currentActivity !== null;
  // Whether the debate is running but between agents
  $: isBetweenAgents = $currentDebate?.status === 'running' && currentActivity === null && liveOutputs.length > 0;
  // Show the strip only during active debate
  $: showActivityStrip = $currentDebate?.status === 'running' || (isBetweenAgents && $currentDebate?.status === 'running');
</script>

<div class="space-y-6">
  <!-- Header with optional back button for archive mode -->
  <div class="flex items-center gap-3">
    {#if isArchiveMode}
      <button
        class="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
        on:click={() => navigate('dashboard')}
      >
        ← {t('debate.backToOverview')}
      </button>
      <span class="text-gray-300 dark:text-gray-600">|</span>
    {/if}
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
      {isArchiveMode ? t('debate.archiveTitle') : t('debate.title')}
    </h2>
    {#if $currentDebate?.project_name}
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

  <!-- Create debate form (hidden in archive mode) -->
  {#if !isArchiveMode}
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('debate.newDebate')}</h3>

    <form on:submit|preventDefault={handleCreateDebate} class="space-y-4">
      <div>
        <label for="case-text" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('debate.caseLabel')}
        </label>
        <textarea
          id="case-text"
          bind:value={caseText}
          rows="4"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder={t('debate.casePlaceholder')}
        ></textarea>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="max-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('debate.maxRounds')}
          </label>
          <input
            id="max-rounds"
            type="number"
            bind:value={maxRounds}
            min="1"
            max="10"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label for="consensus-threshold" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('debate.consensusThreshold')}
          </label>
          <input
            id="consensus-threshold"
            type="number"
            bind:value={consensusThreshold}
            min="0"
            max="1"
            step="0.1"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <div>
        <label for="search-mode" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('debate.searchMode')}
        </label>
        <select
          id="search-mode"
          bind:value={searchMode}
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="off">{t('debate.searchOff')}</option>
          <option value="optional">{t('debate.searchOptional')}</option>
          <option value="required">{t('debate.searchRequired')}</option>
        </select>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          {t(`debate.searchModeHint.${searchMode}`)}
        </p>
      </div>

      <button
        type="submit"
        class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors
               disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={$loading || !caseText.trim()}
      >
        {$loading ? t('debate.creating') : t('debate.createButton')}
      </button>
    </form>
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
          <code class="font-mono text-gray-800 dark:text-gray-200 text-xs">{$currentDebate.debate_id?.substring(0, 8)}…</code>
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
            <span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{$currentDebate.llm_profile_id}</span>
          </div>
        {/if}

        {#if $currentDebate.language}
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('config.language') || 'Sprache'}: </span>
            <span class="text-gray-800 dark:text-gray-200 uppercase">{$currentDebate.language}</span>
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

      <!-- LLM failure / anomaly warnings -->
      {#if $currentDebate.anomalies?.length > 0}
        <div class="mt-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
          <p class="text-sm font-medium text-amber-800 dark:text-amber-200 mb-1">
            {t('debate.llmFailureWarning')}
          </p>
          <p class="text-xs text-amber-700 dark:text-amber-300">
            {t('debate.degradedConsensus')}
          </p>
          <ul class="mt-2 space-y-1">
            {#each $currentDebate.anomalies as anomaly}
              <li class="text-xs text-amber-600 dark:text-amber-400 font-mono">• {anomaly}</li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if !isArchiveMode}
      <div class="mt-4 flex space-x-3">
        {#if $currentDebate.status === 'pending'}
          <button
            class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors
                   disabled:opacity-50"
            on:click={handleStartDebate}
            disabled={$loading}
          >
            {$loading ? t('debate.starting') : t('debate.startButton')}
          </button>
        {/if}

        {#if $currentDebate.status === 'running'}
          <button
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors
                   disabled:opacity-50 disabled:cursor-not-allowed"
            on:click={handleCancelDebate}
            disabled={isCancelling}
          >
            {isCancelling ? t('debate.cancelling') : t('debate.cancelButton')}
          </button>
        {/if}

        <button
          class="px-4 py-2 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200
                 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
          on:click={handleRefreshStatus}
        >
          {t('debate.refreshStatus')}
        </button>
      </div>
      {/if}
    </div>

    <!-- Activity Strip — compact feedback during running debate -->
    {#if $currentDebate.status === 'running'}
      <div class="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
        <!-- Row 1: Progress dots + role verb -->
        <div class="flex items-center gap-3 mb-2">
          <!-- Progress dots -->
          <div class="flex items-center gap-1.5">
            {#if workflowPhase && !currentActivity && liveOutputs.length === 0}
              <!-- Workflow phase indicator (before first agent) -->
              <span class="relative flex h-2.5 w-2.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
              </span>
            {:else}
              {#each Array(agentCount) as _, i}
                {#if i < completedInRound}
                  <!-- Completed dot -->
                  <span class="w-2.5 h-2.5 rounded-full {roleDotColor(liveOutputs.filter(o => o.round === ($currentDebate?.current_round || 0))[i]?.role || 'default')}"></span>
                {:else if i === activeAgentIndex && isProcessing}
                  <!-- Active dot with ping -->
                  <span class="relative flex h-2.5 w-2.5">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full {roleDotColor(currentActivity?.role || 'default')} opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2.5 w-2.5 {roleDotColor(currentActivity?.role || 'default')}"></span>
                  </span>
                {:else}
                  <!-- Pending dot -->
                  <span class="w-2.5 h-2.5 rounded-full bg-zinc-700"></span>
                {/if}
              {/each}
            {/if}
          </div>

          <!-- Status text -->
          {#if isProcessing && currentActivity}
            <span class="text-sm font-medium {roleTextColor(currentActivity.role)}">
              {t(roleVerbKey(currentActivity.role), { role: t(`agent.${currentActivity.role}`) })}
            </span>
          {:else if workflowPhase}
            <!-- Workflow phase status messages -->
            {#if workflowPhase.type === 'workflow_started'}
              <span class="text-sm font-medium text-cyan-400">
                {t('feedback.workflowStarted')}
              </span>
            {:else if workflowPhase.type === 'agent_preparing' && workflowPhase.phase === 'resolving_profile'}
              <span class="text-sm font-medium text-cyan-400">
                {t('feedback.resolvingProfile', { role: t(`agent.${workflowPhase.role}`) })}
              </span>
            {:else if workflowPhase.type === 'agent_preparing' && workflowPhase.phase === 'resolving_prompts'}
              <span class="text-sm font-medium text-cyan-400">
                {t('feedback.resolvingPrompts', { role: t(`agent.${workflowPhase.role}`) })}
              </span>
            {:else if workflowPhase.type === 'llm_call_started'}
              <span class="text-sm font-medium text-amber-400">
                {t('feedback.llmCalling', { model: workflowPhase.model || '...' })}
              </span>
            {:else}
              <span class="text-sm font-medium text-zinc-500">
                {t('feedback.waiting')}
              </span>
            {/if}
          {:else if isBetweenAgents}
            <span class="text-sm font-medium text-zinc-400">
              {t('feedback.completed', { role: t(`agent.${liveOutputs[liveOutputs.length - 1]?.role || 'strategist'}`) })}
            </span>
          {:else}
            <span class="text-sm font-medium text-zinc-500">
              {t('feedback.waiting')}
            </span>
          {/if}
        </div>

        <!-- Row 2: Model name + timer + token counter -->
        {#if isProcessing || isBetweenAgents || workflowPhase}
          <div class="flex items-center gap-3">
            <!-- Model name -->
            {#if workflowPhase?.model}
              <span class="text-xs text-zinc-500 font-mono truncate max-w-[200px]">
                {workflowPhase.model}
              </span>
            {:else if currentActivity?.model || liveOutputs[liveOutputs.length - 1]?.model}
              <span class="text-xs text-zinc-500 font-mono truncate max-w-[200px]">
                {currentActivity?.model || liveOutputs[liveOutputs.length - 1]?.model}
              </span>
            {/if}

            <!-- Provider badge -->
            {#if workflowPhase?.provider}
              <span class="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-zinc-500 font-mono uppercase">
                {workflowPhase.provider}
              </span>
            {:else if currentActivity?.provider}
              <span class="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-zinc-500 font-mono uppercase">
                {currentActivity.provider}
              </span>
            {/if}

            <div class="flex-1"></div>

            <!-- Timer pill -->
            {#if isProcessing}
              <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
                ⏱ {formatElapsed(processingElapsed)}
              </span>
            {:else if workflowPhase && workflowElapsed > 0}
              <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
                ⏱ {formatElapsed(workflowElapsed)}
              </span>
            {:else if liveOutputs.length > 0}
              {@const lastOutput = liveOutputs[liveOutputs.length - 1]}
              {#if lastOutput.duration_ms}
                <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
                  ⏱ {formatElapsed(lastOutput.duration_ms)}
                </span>
              {/if}
            {/if}

            <!-- Stuck warning — if workflow phase takes > 30s -->
            {#if workflowPhase && workflowElapsed > 30000}
              <span class="px-2 py-0.5 rounded-full bg-amber-900/50 text-xs text-amber-400 font-mono">
                ⚠ {t('feedback.slowResponse')}
              </span>
            {/if}

            <!-- Token counter pill -->
            {#if cumulativeTokens > 0}
              <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
                📊 {formatTokens(cumulativeTokens)} {t('feedback.tokens')}
              </span>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Live debate view (during running) -->
    {#if $currentDebate.status === 'running'}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        <div class="p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white flex items-center gap-2">
            <span class="animate-pulse w-3 h-3 bg-blue-500 rounded-full"></span>
            {t('debate.timelineTitle')}
          </h3>
        </div>

        <div class="p-4 space-y-6 max-h-[70vh] overflow-y-auto">
          <!-- Show completed agent outputs as chat bubbles -->
          {#each Object.entries(liveOutputsByRound) as [round, outputs]}
            <div>
              <div class="flex items-center gap-2 mb-3">
                <span class="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                  Round {round}
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
                          <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">
                            ⏱ {formatElapsed(output.duration_ms)}
                          </span>
                        {/if}
                        <span class="text-xs text-gray-400 dark:text-gray-500">
                          {output.tokens_out || output.tokens} tokens
                        </span>
                      </div>
                    </div>
                    <div class="text-sm text-gray-700 dark:text-gray-300">
                      {#if isLong && !isExpanded}
                        <MarkdownRenderer content={output.content.substring(0, 400) + '…'} />
                        <button
                          class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block"
                          on:click={() => toggleExpand(key)}
                        >
                          ▼ Show full response ({output.content.length} chars)
                        </button>
                      {:else}
                        <MarkdownRenderer content={output.content} />
                        {#if isLong}
                          <button
                            class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block"
                            on:click={() => toggleExpand(key)}
                          >
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
                    <span class="font-semibold text-sm text-teal-700 dark:text-teal-300">
                      🔍 {t('search.webResearch')}
                    </span>
                    {#if search.role}
                      <span class="text-xs text-teal-500 dark:text-teal-400">
                        — {search.role} — Round {search.round}
                      </span>
                    {/if}
                  </div>
                  <span class="text-xs text-gray-400 dark:text-gray-500">
                    {search.result_count || search.results?.length || 0} {t('search.source')}{(search.result_count || search.results?.length || 0) !== 1 ? 's' : ''}
                  </span>
                </div>
                {#if search.query}
                  <p class="text-xs text-teal-600 dark:text-teal-400 mb-2 font-mono">
                    {t('search.resultsFor')}: "{search.query}"
                  </p>
                {/if}
                {#if search.results?.length > 0}
                  <div class="space-y-1">
                    {#each (isSearchExpanded ? search.results : search.results.slice(0, 3)) as result}
                      <div class="flex items-start gap-2 text-xs">
                        <span class="text-teal-500 mt-0.5">•</span>
                        <div>
                          {#if result.url}
                            <a href={result.url} target="_blank" rel="noopener noreferrer"
                               class="text-teal-700 dark:text-teal-300 hover:underline font-medium">
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
                    <button
                      class="text-teal-600 dark:text-teal-400 hover:underline text-xs mt-2 inline-block"
                      on:click={() => toggleExpand(searchKey)}
                    >
                      ▼ {t('timeline.expand', { count: search.results.length })}
                    </button>
                  {:else if search.results.length > 3 && isSearchExpanded}
                    <button
                      class="text-teal-600 dark:text-teal-400 hover:underline text-xs mt-2 inline-block"
                      on:click={() => toggleExpand(searchKey)}
                    >
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
                <span class="text-xs text-blue-500 dark:text-blue-400">
                  — Round {currentActivity.round} — thinking…
                </span>
              </div>
              <div class="mt-2 flex gap-1">
                <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
              </div>
            </div>
          {/if}

          {#if liveOutputs.length === 0 && !currentActivity}
            <p class="text-gray-500 dark:text-gray-400 text-sm text-center py-8">
              {t('debate.timelinePlaceholder')}
            </p>
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
                  Round {round.round}
                </span>
                <div class="flex items-center gap-2">
                  <div class="w-20 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                    <div
                      class="bg-blue-600 h-1.5 rounded-full transition-all"
                      style="width: {(round.consensus * 100)}%"
                    ></div>
                  </div>
                  <span class="text-xs text-gray-500 dark:text-gray-400">
                    {(round.consensus * 100).toFixed(1)}%
                  </span>
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
                        <span class="text-xs text-gray-400 dark:text-gray-500">
                          {output.tokens_used || 0} tokens
                        </span>
                      </div>
                      <div class="text-sm text-gray-700 dark:text-gray-300">
                        {#if isLong && !isExpanded}
                          <MarkdownRenderer content={output.content.substring(0, 400) + '…'} />
                          <button
                            class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block"
                            on:click={() => toggleExpand(key)}
                          >
                            ▼ Show full response ({output.content.length} chars)
                          </button>
                        {:else}
                          <MarkdownRenderer content={output.content} />
                          {#if isLong}
                            <button
                              class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block"
                              on:click={() => toggleExpand(key)}
                            >
                              ▲ Collapse
                            </button>
                          {/if}
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="text-sm text-gray-400 dark:text-gray-500 italic">No agent outputs recorded for this round.</p>
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
                  {hasAnomalies ? '⚠️' : '🏁'} Final Consensus
                  {#if hasAnomalies}
                    <span class="text-sm font-normal text-amber-600 dark:text-amber-400">(degraded)</span>
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
                    The debate concluded after {displayRounds.length} round{displayRounds.length !== 1 ? 's' : ''}
                    with a consensus score of {($currentDebate.consensus_score * 100).toFixed(1)}%.
                    {#if $currentDebate.consensus_score >= 0.9}
                      <span class="text-green-600 dark:text-green-400 font-medium">Strong consensus reached.</span>
                    {:else if $currentDebate.consensus_score >= 0.7}
                      <span class="text-yellow-600 dark:text-yellow-400 font-medium">Moderate consensus — further rounds may help.</span>
                    {:else}
                      <span class="text-red-600 dark:text-red-400 font-medium">Low consensus — agents remain divided.</span>
                    {/if}
                  {/if}
                </p>
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- No rounds fallback (archive mode) -->
    {#if isArchiveMode && ($currentDebate.status === 'completed' || $currentDebate.status === 'failed') && !displayRounds}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 border border-gray-200 dark:border-gray-700 text-center">
        <p class="text-gray-500 dark:text-gray-400">{t('debate.noRounds')}</p>
      </div>
    {/if}
  {/if}
</div>
