<script>
  import { onMount, onDestroy } from 'svelte';
  import { currentDebate, debates, loading, error, sseConnected, selectedLLMProfile, selectedPromptVariant, selectedPersonas } from '../lib/stores.js';
  import { createDebate, getDebate, startDebate } from '../lib/api.js';
  import { createSSE } from '../lib/sse.js';
  import { i18n, formatNumber, locale } from '../lib/i18n/index.js';
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
  let sseConnection = null;
  let archiveLoading = false;

  // Live activity log — stores full agent outputs as they arrive
  let liveOutputs = []; // { round, role, content, tokens, timestamp }
  let currentActivity = null; // { round, role, profile }
  let expandedOutputs = new Set(); // track which outputs are expanded

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
    expandedOutputs = new Set();

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
    expandedOutputs = new Set();

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

  // Determine which data source to show for completed debates
  $: displayRounds = $currentDebate?.status === 'completed' && $currentDebate?.rounds?.length > 0
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
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">{t('debate.currentDebate')}</h3>
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

      <div class="flex items-center gap-6 text-sm">
        <div>
          <span class="text-gray-500 dark:text-gray-400">{t('debate.id')}: </span>
          <code class="font-mono text-gray-800 dark:text-gray-200 text-xs">{$currentDebate.debate_id?.substring(0, 8)}…</code>
        </div>

        {#if $currentDebate.current_round !== undefined}
          <div>
            <span class="text-gray-500 dark:text-gray-400">{t('debate.round')}: </span>
            <span class="text-gray-800 dark:text-gray-200 font-medium">
              {formatNumber($currentDebate.current_round)} / {formatNumber($currentDebate.max_rounds || '?')}
            </span>
          </div>
        {/if}

        {#if $currentDebate.consensus_score !== undefined && $currentDebate.consensus_score !== null}
          <div class="flex items-center gap-2">
            <span class="text-gray-500 dark:text-gray-400">{t('debate.consensus')}:</span>
            <div class="w-24 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                class="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style="width: {($currentDebate.consensus_score * 100)}%"
              ></div>
            </div>
            <span class="text-gray-800 dark:text-gray-200 font-medium">
              {formatNumber($currentDebate.consensus_score, { style: 'percent' })}
            </span>
          </div>
        {/if}
      </div>

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
                      <span class="font-semibold text-sm {roleHeaderColor(output.role)}">
                        {roleEmoji(output.role)} {output.role}
                      </span>
                      <span class="text-xs text-gray-400 dark:text-gray-500">
                        {output.tokens} tokens
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
            </div>
          {/each}

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

    <!-- Case text display (archive mode only) -->
    {#if isArchiveMode && $currentDebate.case?.text}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-3">{t('debate.caseLabel')}</h3>
        <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{$currentDebate.case.text}</p>
      </div>
    {/if}

    <!-- Completed debate results -->
    {#if $currentDebate.status === 'completed' && displayRounds}
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
                        <span class="font-semibold text-sm {roleHeaderColor(output.role)}">
                          {roleEmoji(output.role)} {output.role}
                        </span>
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
            <div class="border-t-2 border-gray-200 dark:border-gray-600 pt-6">
              <div class="bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 border border-green-200 dark:border-green-800 rounded-lg p-6">
                <h4 class="text-lg font-bold text-gray-800 dark:text-white mb-3 flex items-center gap-2">
                  🏁 Final Consensus
                </h4>
                <div class="flex items-center gap-4 mb-3">
                  <div class="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-4">
                    <div
                      class="bg-gradient-to-r from-blue-500 to-green-500 h-4 rounded-full transition-all duration-1000"
                      style="width: {($currentDebate.consensus_score * 100)}%"
                    ></div>
                  </div>
                  <span class="text-2xl font-bold text-gray-800 dark:text-white">
                    {($currentDebate.consensus_score * 100).toFixed(1)}%
                  </span>
                </div>
                <p class="text-sm text-gray-600 dark:text-gray-400">
                  The debate concluded after {displayRounds.length} round{displayRounds.length !== 1 ? 's' : ''}
                  with a consensus score of {($currentDebate.consensus_score * 100).toFixed(1)}%.
                  {#if $currentDebate.consensus_score >= 0.9}
                    <span class="text-green-600 dark:text-green-400 font-medium">Strong consensus reached.</span>
                  {:else if $currentDebate.consensus_score >= 0.7}
                    <span class="text-yellow-600 dark:text-yellow-400 font-medium">Moderate consensus — further rounds may help.</span>
                  {:else}
                    <span class="text-red-600 dark:text-red-400 font-medium">Low consensus — agents remain divided.</span>
                  {/if}
                </p>
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- No rounds fallback (archive mode) -->
    {#if isArchiveMode && $currentDebate.status === 'completed' && !displayRounds}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 border border-gray-200 dark:border-gray-700 text-center">
        <p class="text-gray-500 dark:text-gray-400">{t('debate.noRounds')}</p>
      </div>
    {/if}
  {/if}
</div>
