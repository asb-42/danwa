<script>
  import { onMount } from 'svelte';
  import { healthStatus, loading, error, activeProject } from '../lib/stores.js';
  import { getHealth, getDebates } from '../lib/api.js';
  import { i18n, formatNumber, formatDate } from '../lib/i18n/index.js';

  let { navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let stats = $state({
    totalDebates: 0,
    running: 0,
    completed: 0,
    failed: 0,
  });

  let recentDebates = $state([]);

  let projectId = $derived($activeProject?.id);

  onMount(async () => {
    await loadDebateStats();
  });

  // Reload when project changes
  $effect(() => {
    if (projectId) {
      loadDebateStats();
    }
  });

  async function loadDebateStats() {
    try {
      const debates = await getDebates(100);
      recentDebates = debates.slice(0, 10);
      stats = {
        totalDebates: debates.length,
        running: debates.filter((d) => d.status === 'running').length,
        completed: debates.filter((d) => d.status === 'completed').length,
        failed: debates.filter((d) => d.status === 'failed').length,
      };
    } catch (err) {
      console.warn('Could not load debate stats:', err);
    }
  }

  async function refreshHealth() {
    $loading = true;
    $error = null;
    try {
      const data = await getHealth();
      $healthStatus = { status: data.status, version: data.version };
      await loadDebateStats();
    } catch (err) {
      $healthStatus = { status: 'unreachable', version: '' };
      $error = err.message;
    } finally {
      $loading = false;
    }
  }

  function statusBadgeClass(status) {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'running': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'completed': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'failed': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
    }
  }
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('dashboard.title')}</h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-50"
      onclick={refreshHealth}
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

  <!-- Recent debates -->
  {#if recentDebates.length > 0}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
      <div class="p-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">{t('dashboard.recentDebates')}</h3>
      </div>
      <div class="divide-y divide-gray-200 dark:divide-gray-700">
        {#each recentDebates as debate}
          <button
            class="w-full text-left p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer"
            onclick={() => navigate('debate/' + debate.debate_id)}
          >
            <div class="flex items-center justify-between">
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-800 dark:text-gray-200 line-clamp-2">
                  {debate.case_text || debate.case_preview || debate.debate_id.substring(0, 12)}
                </p>
                <div class="flex items-center gap-3 mt-1">
                  {#if debate.project_name}
                    <span class="text-xs text-blue-600 dark:text-blue-400 font-medium">
                      📁 {debate.project_name}
                    </span>
                  {/if}
                  <span class="text-xs text-gray-500 dark:text-gray-400">
                    {formatDate(debate.created_at)}
                  </span>
                  <span class="text-xs text-gray-500 dark:text-gray-400">
                    {debate.language?.toUpperCase() || 'DE'}
                  </span>
                  {#if debate.consensus_score !== null && debate.consensus_score !== undefined}
                    <span class="text-xs text-gray-500 dark:text-gray-400">
                      {t('debate.consensus')}: {(debate.consensus_score * 100).toFixed(0)}%
                    </span>
                  {/if}
                </div>
              </div>
              <span class="px-2 py-1 text-xs font-medium rounded-full {statusBadgeClass(debate.status)}">
                {t(`status.${debate.status}`)}
              </span>
            </div>
          </button>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Placeholder for future workflow graph -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('dashboard.workflowTitle')}</h3>
    <div class="flex items-center justify-center h-48 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">{t('dashboard.workflowPlaceholder')}</p>
    </div>
  </div>
</div>
