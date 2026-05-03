<script>
  import { onMount, onDestroy } from 'svelte';
  import { currentDebate, debates, loading, error, sseConnected, selectedLLMProfile, selectedPromptVariant, selectedPersonas } from '../lib/stores.js';
  import { createDebate, getDebate, startDebate, cancelDebate } from '../lib/api.js';
  import { createSSE } from '../lib/sse.js';
  import { i18n, formatNumber, formatDate, locale } from '../lib/i18n/index.js';
  import DebateTimeline from '../components/DebateTimeline.svelte';

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
  let sseConnection = null;
  let archiveLoading = false;

  // Live activity log — stores full agent outputs as they arrive
  let liveOutputs = []; // { round, role, content, tokens, timestamp }
  let currentActivity = null; // { round, role, profile }

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

  // Cleanup SSE on destroy
  onDestroy(() => {
    if (sseConnection) {
      sseConnection.close();
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
    currentActivity = null;

    try {
      const response = await createDebate(caseText, {
        max_rounds: maxRounds,
        consensus_threshold: consensusThreshold,
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
    currentActivity = null;

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

  function handleSSEEvent(event) {
    console.log('SSE event:', event);

    // status_change: completed or failed
    if (event.status === 'completed' || event.status === 'failed') {
      $currentDebate = { ...$currentDebate, status: event.status };
      currentActivity = null;
      handleRefreshStatus();
      return;
    }

    // round_update
    if (event.round !== undefined && event.consensus !== undefined) {
      $currentDebate = {
        ...$currentDebate,
        current_round: event.round,
        consensus_score: event.consensus,
      };
      currentActivity = null;
      return;
    }

    // agent_started
    if (event.role && event.round && event.profile && !event.content) {
      currentActivity = { round: event.round, role: event.role, profile: event.profile };
      return;
    }

    // agent_output — full content arrives here
    if (event.role && event.round && event.content) {
      currentActivity = null;
      liveOutputs = [...liveOutputs, {
        round: event.round,
        role: event.role,
        content: event.content,
        tokens: event.tokens_used,
        timestamp: new Date(),
      }];
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
      await cancelDebate($currentDebate.debate_id);
      // The SSE stream will deliver the failed status_change event
    } catch (err) {
      $error = err.message;
    } finally {
      isCancelling = false;
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

  // Determine which data source to show for completed debates
  $: displayRounds = $currentDebate?.status === 'completed' && $currentDebate?.rounds?.length > 0
    ? $currentDebate.rounds
    : null;
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

    <!-- Case text display -->
    {#if $currentDebate.case_text || $currentDebate.case?.text}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-3">{t('debate.caseLabel')}</h3>
        <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{$currentDebate.case_text || $currentDebate.case?.text}</p>
      </div>
    {/if}

    <!-- DebateTimeline 2.0 — unified component for running and completed debates -->
    {#if $currentDebate.status === 'running' || ($currentDebate.status === 'completed' && displayRounds)}
      <DebateTimeline
        rounds={displayRounds || []}
        {liveOutputs}
        {currentActivity}
        maxRounds={$currentDebate.max_rounds || 0}
        consensus={$currentDebate.consensus_score || 0}
        status={$currentDebate.status}
        anomalies={$currentDebate.anomalies || []}
      />
    {/if}

    <!-- No rounds fallback (archive mode) -->
    {#if isArchiveMode && $currentDebate.status === 'completed' && !displayRounds}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 border border-gray-200 dark:border-gray-700 text-center">
        <p class="text-gray-500 dark:text-gray-400">{t('debate.noRounds')}</p>
      </div>
    {/if}
  {/if}
</div>
