<script>
  import { onMount, onDestroy } from 'svelte';
  import { currentDebate, debates, loading, error, sseConnected, selectedLLMProfile, selectedPromptVariant, selectedPersonas } from '../lib/stores.js';
  import { createDebate, getDebate, startDebate } from '../lib/api.js';
  import { createSSE } from '../lib/sse.js';
  import { i18n, formatNumber } from '../lib/i18n/index.js';

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  let caseText = '';
  let maxRounds = 3;
  let consensusThreshold = 0.8;
  let sseConnection = null;

  // Live activity log
  let activityLog = [];
  let currentActivity = null; // { round, role, status }

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
    activityLog = [];
    currentActivity = null;

    try {
      const response = await createDebate(caseText, {
        max_rounds: maxRounds,
        consensus_threshold: consensusThreshold,
        llm_profile_id: $selectedLLMProfile,
        prompt_variant: $selectedPromptVariant,
        agent_persona_ids: $selectedPersonas,
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
    activityLog = [];
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
      // startDebate now returns immediately with status=running
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

    if (event.status === 'completed' || event.status === 'failed') {
      $currentDebate = { ...$currentDebate, status: event.status };
      currentActivity = null;
      // Refresh full debate data
      handleRefreshStatus();
      return;
    }

    if (event.round !== undefined && event.consensus !== undefined) {
      // round_update event
      $currentDebate = {
        ...$currentDebate,
        current_round: event.round,
        consensus_score: event.consensus,
      };
      activityLog = [...activityLog, {
        type: 'round',
        round: event.round,
        consensus: event.consensus,
        timestamp: new Date(),
      }];
      currentActivity = null;
      return;
    }

    if (event.role && event.round) {
      if (event.content) {
        // agent_output event
        currentActivity = null;
        activityLog = [...activityLog, {
          type: 'output',
          round: event.round,
          role: event.role,
          content: event.content,
          tokens: event.tokens_used,
          timestamp: new Date(),
        }];
      } else if (event.profile) {
        // agent_started event
        currentActivity = { round: event.round, role: event.role, profile: event.profile };
        activityLog = [...activityLog, {
          type: 'started',
          round: event.round,
          role: event.role,
          profile: event.profile,
          timestamp: new Date(),
        }];
      }
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

  function roleEmoji(role) {
    switch (role) {
      case 'strategist': return '🎯';
      case 'critic': return '🔍';
      case 'optimizer': return '⚡';
      case 'moderator': return '⚖️';
      default: return '🤖';
    }
  }
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('debate.title')}</h2>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  <!-- Create debate form -->
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

  <!-- Current debate status -->
  {#if $currentDebate}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">{t('debate.currentDebate')}</h3>
        <div class="flex items-center space-x-2">
          {#if $sseConnected}
            <span class="flex items-center text-xs text-green-600 dark:text-green-400">
              <span class="w-2 h-2 bg-green-500 rounded-full mr-1"></span>
              {t('debate.sseConnected')}
            </span>
          {/if}
        </div>
      </div>

      <div class="space-y-3" aria-live="polite" aria-atomic="true">
        <div class="flex items-center space-x-3">
          <span class="text-sm text-gray-500 dark:text-gray-400">{t('debate.id')}</span>
          <code class="text-sm font-mono text-gray-800 dark:text-gray-200">{$currentDebate.debate_id}</code>
        </div>

        <div class="flex items-center space-x-3">
          <span class="text-sm text-gray-500 dark:text-gray-400">{t('debate.status')}</span>
          <span class="px-2 py-1 text-xs font-medium rounded-full {statusBadgeClass}">
            {statusLabel}
          </span>
        </div>

        {#if $currentDebate.current_round !== undefined}
          <div class="flex items-center space-x-3">
            <span class="text-sm text-gray-500 dark:text-gray-400">{t('debate.round')}</span>
            <span class="text-sm text-gray-800 dark:text-gray-200">
              {formatNumber($currentDebate.current_round)} / {formatNumber($currentDebate.max_rounds || '?')}
            </span>
          </div>
        {/if}

        {#if $currentDebate.consensus_score !== undefined && $currentDebate.consensus_score !== null}
          <div class="flex items-center space-x-3">
            <span class="text-sm text-gray-500 dark:text-gray-400">{t('debate.consensus')}</span>
            <div class="flex-1 max-w-xs">
              <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  class="bg-blue-600 h-2 rounded-full transition-all"
                  style="width: {($currentDebate.consensus_score * 100)}%"
                ></div>
              </div>
            </div>
            <span class="text-sm text-gray-800 dark:text-gray-200">
              {formatNumber($currentDebate.consensus_score, { style: 'percent' })}
            </span>
          </div>
        {/if}
      </div>

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
    </div>

    <!-- Live activity during debate -->
    {#if $currentDebate.status === 'running'}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">
          🔄 {t('debate.timelineTitle')}
        </h3>

        {#if currentActivity}
          <div class="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <div class="flex items-center space-x-2">
              <span class="animate-pulse w-3 h-3 bg-blue-500 rounded-full"></span>
              <span class="text-sm font-medium text-blue-800 dark:text-blue-200">
                {roleEmoji(currentActivity.role)} {currentActivity.role}
                — Round {currentActivity.round}
                — LLM: {currentActivity.profile}
              </span>
            </div>
          </div>
        {/if}

        {#if activityLog.length > 0}
          <div class="space-y-2 max-h-96 overflow-y-auto">
            {#each activityLog as entry}
              {#if entry.type === 'started'}
                <div class="flex items-start space-x-2 text-sm">
                  <span class="text-blue-500">▶</span>
                  <span class="text-gray-500 dark:text-gray-400">R{entry.round}</span>
                  <span class="text-gray-800 dark:text-gray-200">
                    {roleEmoji(entry.role)} {entry.role} started ({entry.profile})
                  </span>
                </div>
              {:else if entry.type === 'output'}
                <div class="flex items-start space-x-2 text-sm">
                  <span class="text-green-500">✓</span>
                  <span class="text-gray-500 dark:text-gray-400">R{entry.round}</span>
                  <span class="text-gray-800 dark:text-gray-200">
                    {roleEmoji(entry.role)} {entry.role} — {entry.tokens} tokens
                  </span>
                </div>
              {:else if entry.type === 'round'}
                <div class="flex items-start space-x-2 text-sm font-medium">
                  <span class="text-purple-500">●</span>
                  <span class="text-gray-800 dark:text-gray-200">
                    Round {entry.round} complete — Consensus: {(entry.consensus * 100).toFixed(1)}%
                  </span>
                </div>
              {/if}
            {/each}
          </div>
        {:else}
          <p class="text-gray-500 dark:text-gray-400 text-sm">{t('debate.timelinePlaceholder')}</p>
        {/if}
      </div>
    {/if}

    <!-- Completed debate results -->
    {#if $currentDebate.status === 'completed' && $currentDebate.rounds?.length > 0}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">
          📊 {t('debate.timelineTitle')}
        </h3>

        <div class="space-y-4">
          {#each $currentDebate.rounds as round}
            <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
              <div class="flex items-center justify-between mb-2">
                <span class="font-medium text-gray-800 dark:text-white">Round {round.round}</span>
                <span class="text-sm text-gray-500 dark:text-gray-400">
                  Consensus: {(round.consensus * 100).toFixed(1)}%
                </span>
              </div>
              {#if round.agent_outputs?.length > 0}
                <div class="space-y-2">
                  {#each round.agent_outputs as output}
                    <div class="text-sm">
                      <span class="font-medium text-gray-700 dark:text-gray-300">
                        {roleEmoji(output.role)} {output.role}:
                      </span>
                      <span class="text-gray-600 dark:text-gray-400 ml-1">
                        {output.content?.substring(0, 200)}{output.content?.length > 200 ? '...' : ''}
                      </span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>
