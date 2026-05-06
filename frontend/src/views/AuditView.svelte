<script>
  import { onMount } from 'svelte';
  import { auditEvents, currentDebate, loading, error } from '../lib/stores.js';
  import { getAuditEvents } from '../lib/api.js';
  import { i18n, formatDate } from '../lib/i18n/index.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let debateIdInput = $state('');

  async function loadAuditEvents() {
    const id = debateIdInput.trim() || $currentDebate?.debate_id;
    if (!id) {
      $error = t('audit.enterDebateId');
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
    return formatDate(ts, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('audit.title')}</h2>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  <!-- Search form -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <form onsubmit={(e) => { e.preventDefault(); loadAuditEvents(); }} class="flex items-end space-x-4">
      <div class="flex-1">
        <label for="debate-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('audit.debateId')}
        </label>
        <input
          id="debate-id"
          type="text"
          bind:value={debateIdInput}
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                 font-mono text-sm"
          placeholder={t('audit.debateIdPlaceholder')}
        />
      </div>
      <button
        type="submit"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors
               disabled:opacity-50"
        disabled={$loading}
      >
        {$loading ? t('audit.loading') : t('audit.loadEvents')}
      </button>
    </form>
  </div>

  <!-- Audit events table -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
    {#if $auditEvents.length === 0}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">
          {$loading ? t('audit.loadingEvents') : t('audit.noEvents')}
        </p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm" aria-label={t('audit.title')}>
          <thead>
            <tr class="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">#</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">{t('audit.round')}</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">{t('audit.agent')}</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">{t('audit.action')}</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">{t('audit.timestamp')}</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">{t('audit.model')}</th>
              <th scope="col" class="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-300">{t('audit.tokens')}</th>
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
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('audit.visualizationTitle')}</h3>
    <div class="flex items-center justify-center h-32 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">{t('audit.visualizationPlaceholder')}</p>
    </div>
  </div>
</div>
