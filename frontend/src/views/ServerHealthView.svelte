<!-- ServerHealthView.svelte — Detailed server health status -->

<script>
  import { onMount, onDestroy } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { getHealth } from '../lib/api.js';

  let t = $derived($tStore);

  let health = $state(null);
  let loading = $state(true);
  let error = $state('');

  const POLL_INTERVAL_MS = 30000;
  let pollTimer = null;

  async function refresh() {
    try {
      health = await getHealth();
      error = '';
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    await refresh();
    pollTimer = setInterval(refresh, POLL_INTERVAL_MS);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function statusColor(status) {
    if (status === 'ok') return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
    if (status === 'not_configured') return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
    return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
  }

  function statusIcon(status) {
    if (status === 'ok') return '✅';
    if (status === 'not_configured') return '⚠️';
    return '❌';
  }

  function statusLabel(status) {
    if (status === 'ok') return t('server.ok');
    if (status === 'not_configured') return t('server.notConfigured');
    return t('server.error');
  }
</script>

<div class="max-w-2xl mx-auto p-6 space-y-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{t('server.title')}</h1>

  {#if loading}
    <p class="text-gray-500 dark:text-gray-400">Loading…</p>
  {:else if error}
    <div class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300" role="alert">
      {error}
    </div>
  {:else if health}
    <!-- Overall status -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-sm text-gray-500 dark:text-gray-400">{t('server.status')}</span>
          <p class="text-lg font-semibold text-gray-900 dark:text-white">
            {statusIcon(health.status)} {statusLabel(health.status)}
          </p>
        </div>
        {#if health.version}
          <div class="text-right">
            <span class="text-sm text-gray-500 dark:text-gray-400">{t('server.version')}</span>
            <p class="text-gray-900 dark:text-white font-mono">{health.version}</p>
          </div>
        {/if}
      </div>
    </div>

    <!-- Component checks -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table class="w-full">
        <thead>
          <tr class="border-b border-gray-200 dark:border-gray-700">
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              {t('server.component')}
            </th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              {t('server.status')}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          {#each Object.entries(health.checks || {}) as [name, status]}
            <tr>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                {t(`server.${name}`) || name}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-right">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {statusColor(status)}">
                  {statusIcon(status)} {statusLabel(status)}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
