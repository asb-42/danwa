<script>
  import { onMount, onDestroy } from 'svelte';
  import { healthStatus, loading, error, currentDebate, route } from '../lib/stores.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { getHealth, getTenantDebates, findRunningDebateAcrossProjects, request } from '../lib/api.js';
  
  import { formatNumber, formatDate, tStore, tn } from '../lib/i18n/index.js';
  import WorkflowPipeline from '../components/workflow/WorkflowPipeline.svelte';
  import { useLastCompletedDebatePipeline } from '../lib/workflowPipelineAdapter.svelte.js';
  import QuotaIndicator from '../components/QuotaIndicator.svelte';

  const lastCompleted = useLastCompletedDebatePipeline();

  let { navigate = () => {} } = $props();

  let t = $derived($tStore);

  let stats = $state({
    totalDebates: 0,
    running: 0,
    completed: 0,
    failed: 0,
  });

  let recentDebates = $state([]);
  let tenant = $state(null);

  let tenantId = $derived($currentTenant?.id);
  let runningDebatePoller = $state(null);

  onMount(async () => {
    await Promise.all([loadDebateStats(), loadTenant()]);
    startRunningDebatePoller();
  });

  // The cleanup function returned from onMount is not a Svelte lifecycle
  // hook — it only runs if onMount's promise chain rejects. Use onDestroy.
  onDestroy(stopRunningDebatePoller);

  async function loadTenant() {
    try {
      tenant = await request('/api/v1/tenants/current');
    } catch (e) { if (import.meta.env.DEV) console.warn('[Dashboard] tenant info load failed (optional):', e); }
  }

  // Reload when tenant changes
  $effect(() => {
    if (tenantId) {
      loadDebateStats();
    }
  });

  // Poll for externally-started debates (e.g. via A2A)
  function startRunningDebatePoller() {
    if (runningDebatePoller) clearInterval(runningDebatePoller);
    runningDebatePoller = setInterval(checkForRunningDebates, 5000);
  }

  function stopRunningDebatePoller() {
    if (runningDebatePoller) {
      clearInterval(runningDebatePoller);
      runningDebatePoller = null;
    }
  }

  async function checkForRunningDebates() {
    if ($route !== 'dashboard') return;
    if ($currentDebate?.status === 'running') return;
    try {
      const running = await findRunningDebateAcrossProjects();
      if (running && (!$currentDebate || $currentDebate.status !== 'running')) {
        currentDebate.set(running);
      }
    } catch (e) { if (import.meta.env.DEV) console.warn('[Dashboard] running-debate poll failed:', e); }
  }

  async function loadDebateStats() {
    if (!tenantId) return;
    try {
      const debates = await getTenantDebates(tenantId, { limit: 100 });
      recentDebates = debates.slice(0, 10);
      stats = {
        totalDebates: debates.length,
        running: debates.filter((d) => d.status === 'running').length,
        completed: debates.filter((d) => d.status === 'completed').length,
        failed: debates.filter((d) => d.status === 'failed').length,
      };
    } catch (err) {
      if (import.meta.env.DEV) console.warn('Could not load debate stats:', err);
    }
  }

  async function refreshHealth() {
    loading.set(true);
    error.set(null);
    try {
      const data = await getHealth();
      healthStatus.set({ status: data.status, version: data.version });
      await loadDebateStats();
    } catch (err) {
      healthStatus.set({ status: 'unreachable', version: '' });
      error.set(err.message);
    } finally {
      loading.set(false);
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

  let graphStatus = $derived($currentDebate?.status === 'running' ? 'running' : $currentDebate?.status === 'completed' ? 'completed' : 'idle');
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('dashboard.title')}</h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600 transition-colors text-sm disabled:opacity-50"
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
      <p class="mt-1 text-2xl font-semibold text-gray-800 dark:text-white">{tn(stats.totalDebates, { one: 'debate.count.one', other: 'debate.count.other' })}</p>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">{t('dashboard.running')}</p>
      <p class="mt-1 text-2xl font-semibold text-blue-600 dark:text-blue-400">{formatNumber(stats.running)}</p>
      {#if stats.running > 0 && $currentDebate?.status !== 'running'}
        <button
          class="mt-2 text-xs text-blue-600 dark:text-blue-400 hover:underline"
          onclick={() => {
            const running = recentDebates.find(d => d.status === 'running');
            if (running) navigate('debate/' + running.debate_id);
          }}
        >
          → {t('dashboard.viewRunning') || 'View running debate'}
        </button>
      {/if}
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">{t('dashboard.completed')}</p>
      <p class="mt-1 text-2xl font-semibold text-green-600 dark:text-green-400">{formatNumber(stats.completed)}</p>
    </div>
  </div>

  <!-- Tenant quotas -->
  {#if tenant}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">🏢 {tenant.name}</h3>
        <span class="px-2 py-0.5 text-xs rounded-full
          {tenant.plan === 'enterprise' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' :
           tenant.plan === 'pro' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
           'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}">
          {t(`tenant.plan.${tenant.plan}`) || tenant.plan}
        </span>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <QuotaIndicator label={t('tenant.debatesUsed', { used: '—', max: tenant.max_concurrent_debates })} max={tenant.max_concurrent_debates} icon="💬" />
        <QuotaIndicator label={t('tenant.documentsUsed', { used: '—', max: tenant.max_documents })} max={tenant.max_documents} icon="📄" />
        <QuotaIndicator label={t('tenant.storageUsed', { used: '—', max: tenant.max_storage_mb })} max={tenant.max_storage_mb} icon="💾" />
      </div>
    </div>
  {/if}

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
                {#if debate.title}
                  <p class="text-sm font-semibold text-gray-900 dark:text-white line-clamp-1">
                    {debate.title}
                  </p>
                  <p class="text-xs text-gray-500 dark:text-gray-400 line-clamp-1 mt-0.5">
                    {debate.case_preview || debate.debate_id.substring(0, 12)}
                  </p>
                {:else}
                  <p class="text-sm text-gray-800 dark:text-gray-200 line-clamp-2">
                    {debate.case_text || debate.case_preview || debate.debate_id.substring(0, 12)}
                  </p>
                {/if}
                <div class="flex items-center gap-3 mt-1">
                  {#if debate.case_title}
                    <span class="text-xs text-blue-600 dark:text-blue-400 font-medium">
                      📋 {debate.case_title}
                    </span>
                  {:else if debate.project_name}
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

  <!-- Workflow graph: last completed debate as an exemplar -->
  <WorkflowPipeline
    meta={lastCompleted.meta}
    nodes={lastCompleted.nodes}
    edges={lastCompleted.edges}
    activeNodeId={lastCompleted.activeNodeId}
    mode="replay"
    compact
  />
</div>


