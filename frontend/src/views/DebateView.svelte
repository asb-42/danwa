<script>
  import { onMount, onDestroy } from 'svelte';
  import { currentDebate, debates, loading, error, sseConnected } from '../lib/stores.js';
  import { createDebate, getDebate, startDebate } from '../lib/api.js';
  import { createSSE } from '../lib/sse.js';

  let caseText = '';
  let maxRounds = 3;
  let consensusThreshold = 0.8;
  let sseConnection = null;

  // Cleanup SSE on destroy
  onDestroy(() => {
    if (sseConnection) {
      sseConnection.close();
    }
  });

  async function handleCreateDebate() {
    if (!caseText.trim()) {
      $error = 'Please enter a case description';
      return;
    }

    $loading = true;
    $error = null;

    try {
      const response = await createDebate(caseText, {
        max_rounds: maxRounds,
        consensus_threshold: consensusThreshold,
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

    try {
      const result = await startDebate($currentDebate.debate_id);
      $currentDebate = { ...$currentDebate, ...result };

      // Connect SSE for real-time updates
      sseConnection = createSSE($currentDebate.debate_id, {
        onEvent: (event) => {
          console.log('SSE event:', event);
          // Update debate state from SSE events
          if (event.status) {
            $currentDebate = { ...$currentDebate, status: event.status };
          }
        },
        onOpen: () => { $sseConnected = true; },
        onClose: () => { $sseConnected = false; },
        onError: (err) => { console.error('SSE error:', err); },
      });
    } catch (err) {
      $error = err.message;
    } finally {
      $loading = false;
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
      case 'PENDING': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'RUNNING': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'COMPLETED': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'FAILED': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
    }
  })();
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">Debate</h2>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  <!-- Create debate form -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">New Debate</h3>

    <form on:submit|preventDefault={handleCreateDebate} class="space-y-4">
      <div>
        <label for="case-text" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Case Description
        </label>
        <textarea
          id="case-text"
          bind:value={caseText}
          rows="4"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder="Describe the case to be debated..."
        ></textarea>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="max-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Max Rounds
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
            Consensus Threshold
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
        {$loading ? 'Creating...' : 'Create Debate'}
      </button>
    </form>
  </div>

  <!-- Current debate status -->
  {#if $currentDebate}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">Current Debate</h3>
        <div class="flex items-center space-x-2">
          {#if $sseConnected}
            <span class="flex items-center text-xs text-green-600 dark:text-green-400">
              <span class="w-2 h-2 bg-green-500 rounded-full mr-1"></span>
              SSE Connected
            </span>
          {/if}
        </div>
      </div>

      <div class="space-y-3">
        <div class="flex items-center space-x-3">
          <span class="text-sm text-gray-500 dark:text-gray-400">ID:</span>
          <code class="text-sm font-mono text-gray-800 dark:text-gray-200">{$currentDebate.debate_id}</code>
        </div>

        <div class="flex items-center space-x-3">
          <span class="text-sm text-gray-500 dark:text-gray-400">Status:</span>
          <span class="px-2 py-1 text-xs font-medium rounded-full {statusBadgeClass}">
            {$currentDebate.status}
          </span>
        </div>

        {#if $currentDebate.current_round !== undefined}
          <div class="flex items-center space-x-3">
            <span class="text-sm text-gray-500 dark:text-gray-400">Round:</span>
            <span class="text-sm text-gray-800 dark:text-gray-200">
              {$currentDebate.current_round} / {$currentDebate.max_rounds || '?'}
            </span>
          </div>
        {/if}

        {#if $currentDebate.consensus_score !== undefined}
          <div class="flex items-center space-x-3">
            <span class="text-sm text-gray-500 dark:text-gray-400">Consensus:</span>
            <div class="flex-1 max-w-xs">
              <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  class="bg-blue-600 h-2 rounded-full transition-all"
                  style="width: {($currentDebate.consensus_score * 100)}%"
                ></div>
              </div>
            </div>
            <span class="text-sm text-gray-800 dark:text-gray-200">
              {($currentDebate.consensus_score * 100).toFixed(0)}%
            </span>
          </div>
        {/if}
      </div>

      <div class="mt-4 flex space-x-3">
        {#if $currentDebate.status === 'PENDING'}
          <button
            class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors
                   disabled:opacity-50"
            on:click={handleStartDebate}
            disabled={$loading}
          >
            {$loading ? 'Starting...' : 'Start Debate'}
          </button>
        {/if}

        <button
          class="px-4 py-2 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200
                 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
          on:click={handleRefreshStatus}
        >
          Refresh Status
        </button>
      </div>
    </div>

    <!-- Placeholder: Debate timeline -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">Debate Timeline</h3>
      <div class="flex items-center justify-center h-32 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
        <p class="text-gray-400 dark:text-gray-500">Debate timeline — coming in Sprint 4</p>
      </div>
    </div>
  {/if}
</div>
