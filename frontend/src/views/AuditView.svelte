<script>
  import { onMount } from 'svelte';
  import { auditEvents, currentDebate, loading, error } from '../lib/stores.js';
  import { getAuditEvents } from '../lib/api.js';

  let debateIdInput = '';

  async function loadAuditEvents() {
    const id = debateIdInput.trim() || $currentDebate?.debate_id;
    if (!id) {
      $error = 'Please enter a debate ID or create a debate first';
      return;
    }

    $loading = true;
    $error = null;

    try {
      const events = await getAuditEvents(id);
      $auditEvents = events;
    } catch (err) {
      $error = err.message;
      $auditEvents = [];
    } finally {
      $loading = false;
    }
  }

  // Auto-load if current debate exists
  onMount(() => {
    if ($currentDebate?.debate_id) {
      debateIdInput = $currentDebate.debate_id;
      loadAuditEvents();
    }
  });

  function formatTimestamp(ts) {
    if (!ts) return '—';
    return new Date(ts).toLocaleString();
  }
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">Audit Trail</h2>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  <!-- Search form -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <form on:submit|preventDefault={loadAuditEvents} class="flex items-end space-x-4">
      <div class="flex-1">
        <label for="debate-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Debate ID
        </label>
        <input
          id="debate-id"
          type="text"
          bind:value={debateIdInput}
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                 font-mono text-sm"
          placeholder="Enter debate ID..."
        />
      </div>
      <button
        type="submit"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors
               disabled:opacity-50"
        disabled={$loading}
      >
        {$loading ? 'Loading...' : 'Load Events'}
      </button>
    </form>
  </div>

  <!-- Audit events table -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
    {#if $auditEvents.length === 0}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">
          {$loading ? 'Loading events...' : 'No audit events found. Run a debate first.'}
        </p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm" aria-label="Audit events">
          <thead>
            <tr class="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">#</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">Round</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">Agent</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">Action</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">Timestamp</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">Model</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">Tokens</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
            {#each $auditEvents as event, i}
              <tr class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                <td class="px-4 py-3 text-gray-500 dark:text-gray-400">{i + 1}</td>
                <td class="px-4 py-3 text-gray-800 dark:text-gray-200">{event.round ?? '—'}</td>
                <td class="px-4 py-3">
                  <span class="px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                    {event.agent || '—'}
                  </span>
                </td>
                <td class="px-4 py-3 text-gray-800 dark:text-gray-200">{event.action || '—'}</td>
                <td class="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs font-mono">
                  {formatTimestamp(event.timestamp)}
                </td>
                <td class="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">
                  {event.llm_model || '—'}
                </td>
                <td class="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">
                  {event.tokens_used ?? '—'}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>

  <!-- Placeholder: Audit trail visualization -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">Audit Visualization</h3>
    <div class="flex items-center justify-center h-32 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">Audit trail visualization — coming in Sprint 4</p>
    </div>
  </div>
</div>
