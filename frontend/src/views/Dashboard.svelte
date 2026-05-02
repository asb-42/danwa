<script>
  import { onMount } from 'svelte';
  import { healthStatus, debates, loading, error } from '../lib/stores.js';
  import { getHealth } from '../lib/api.js';

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
        running: d.filter((deb) => deb.status === 'RUNNING').length,
        completed: d.filter((deb) => deb.status === 'COMPLETED').length,
        failed: d.filter((deb) => deb.status === 'FAILED').length,
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
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">Dashboard</h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-50"
      on:click={refreshHealth}
      disabled={$loading}
    >
      {$loading ? 'Checking...' : 'Refresh Health'}
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
      <p class="text-sm text-gray-500 dark:text-gray-400">Backend Status</p>
      <p class="mt-1 text-2xl font-semibold
        {$healthStatus.status === 'ok' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}">
        {$healthStatus.status}
      </p>
      {#if $healthStatus.version}
        <p class="text-xs text-gray-400 mt-1">v{$healthStatus.version}</p>
      {/if}
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">Total Debates</p>
      <p class="mt-1 text-2xl font-semibold text-gray-800 dark:text-white">{stats.totalDebates}</p>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">Running</p>
      <p class="mt-1 text-2xl font-semibold text-blue-600 dark:text-blue-400">{stats.running}</p>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">Completed</p>
      <p class="mt-1 text-2xl font-semibold text-green-600 dark:text-green-400">{stats.completed}</p>
    </div>
  </div>

  <!-- Placeholder for future workflow graph -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">Workflow Overview</h3>
    <div class="flex items-center justify-center h-48 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-400 dark:text-gray-500">Workflow graph visualization — coming in Sprint 4</p>
    </div>
  </div>
</div>
