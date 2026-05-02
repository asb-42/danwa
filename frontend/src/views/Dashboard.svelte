<script>
  import { onMount } from 'svelte';
  import { healthStatus, debates, loading, error } from '../lib/stores.js';
  import { getHealth } from '../lib/api.js';
  import { i18n, formatNumber } from '../lib/i18n/index.js';

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  let stats = {
    totalDebates: 0,
    running: 0,
    completed: 0,
    failed: 0,
  };

  onMount(() => {
    // Compute stats from debates store
    const unsubscribe = debates.subscribe((d) => {
      stats = {
        totalDebates: d.length,
        running: d.filter((deb) => deb.status === 'running').length,
        completed: d.filter((deb) => deb.status === 'completed').length,
        failed: d.filter((deb) => deb.status === 'failed').length,
      };
    });
    return unsubscribe;
  });

  async function refreshHealth() {
    $loading = true;
    $error = null;
    try {
      const data = await getHealth();
      $healthStatus = { status: data.status, version: data.version };
    } catch (err) {
      $healthStatus = { status: 'unreachable', version: '' };
      $error = err.message;
    } finally {
      $loading = false;
    }
  }
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('dashboard.title')}</h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-50"
      on:click={refreshHealth}
      disabled={$loading}
    >
      {$loading ? t('dashboard.checking') : t('dashboard.refreshHealth')}
    </button>
  </div>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  <!-- Stats cards -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">{t('dashboard.backendStatus')}</p>
      <p class="mt-1 text-2xl font-semibold
        {$healthStatus.status === 'ok' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}">
        {$healthStatus.status}
      </p>
      {#if $healthStatus.version}
        <p class="text-xs text-gray-500 mt-1">v{$healthStatus.version}</p>
      {/if}
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">{t('dashboard.totalDebates')}</p>
      <p class="mt-1 text-2xl font-semibold text-gray-800 dark:text-white">{formatNumber(stats.totalDebates)}</p>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">{t('dashboard.running')}</p>
      <p class="mt-1 text-2xl font-semibold text-blue-600 dark:text-blue-400">{formatNumber(stats.running)}</p>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">{t('dashboard.completed')}</p>
      <p class="mt-1 text-2xl font-semibold text-green-600 dark:text-green-400">{formatNumber(stats.completed)}</p>
    </div>
  </div>

  <!-- Placeholder for future workflow graph -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('dashboard.workflowTitle')}</h3>
    <div class="flex items-center justify-center h-48 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">{t('dashboard.workflowPlaceholder')}</p>
    </div>
  </div>
</div>
