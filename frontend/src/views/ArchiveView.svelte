<script>
  import { onMount } from 'svelte';
  import { loading, error } from '../lib/stores.js';
  import { getDebates } from '../lib/api.js';
  import { i18n, formatNumber, formatDate } from '../lib/i18n/index.js';

  export let navigate = () => {};

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  const PAGE_SIZE = 20;

  let debates = [];
  let totalCount = 0;
  let currentPage = 0;
  let searchQuery = '';
  let statusFilter = '';
  let searchTimeout = null;

  const statusOptions = [
    { value: '', label: 'archive.filterAll' },
    { value: 'completed', label: 'status.completed' },
    { value: 'running', label: 'status.running' },
    { value: 'pending', label: 'status.pending' },
    { value: 'failed', label: 'status.failed' },
  ];

  onMount(() => {
    loadDebates();
  });

  async function loadDebates() {
    $loading = true;
    $error = null;
    try {
      const result = await getDebates(PAGE_SIZE, {
        status: statusFilter || null,
        search: searchQuery || null,
        offset: currentPage * PAGE_SIZE,
      });
      debates = result;
      // Backend doesn't return total count yet, so we estimate
      totalCount = result.length < PAGE_SIZE
        ? currentPage * PAGE_SIZE + result.length
        : (currentPage + 1) * PAGE_SIZE + 1;
    } catch (err) {
      $error = err.message;
      debates = [];
    } finally {
      $loading = false;
    }
  }

  function handleSearch() {
    // Debounce search input
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      currentPage = 0;
      loadDebates();
    }, 300);
  }

  function handleFilterChange() {
    currentPage = 0;
    loadDebates();
  }

  function goToPage(page) {
    if (page < 0) return;
    currentPage = page;
    loadDebates();
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
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('archive.title')}</h2>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  <!-- Search and filter bar -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
    <div class="flex flex-col sm:flex-row gap-3">
      <!-- Search input -->
      <div class="flex-1">
        <div class="relative">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">🔍</span>
          <input
            type="text"
            bind:value={searchQuery}
            on:input={handleSearch}
            placeholder={t('archive.searchPlaceholder')}
            class="w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>
      </div>

      <!-- Status filter -->
      <div class="sm:w-48">
        <select
          bind:value={statusFilter}
          on:change={handleFilterChange}
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
        >
          {#each statusOptions as opt}
            <option value={opt.value}>{t(opt.label)}</option>
          {/each}
        </select>
      </div>
    </div>
  </div>

  <!-- Results table -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
    {#if $loading}
      <div class="p-8 text-center">
        <div class="flex justify-center gap-1 mb-3">
          <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </div>
        <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
      </div>
    {:else if debates.length === 0}
      <div class="p-8 text-center">
        <p class="text-gray-500 dark:text-gray-400 text-lg mb-2">📭</p>
        <p class="text-gray-500 dark:text-gray-400">{t('archive.noResults')}</p>
      </div>
    {:else}
      <!-- Table header -->
      <div class="hidden md:grid md:grid-cols-12 gap-4 px-4 py-3 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
        <div class="col-span-5">{t('debate.caseLabel')}</div>
        <div class="col-span-2">{t('archive.date')}</div>
        <div class="col-span-1">{t('debate.round')}</div>
        <div class="col-span-2">{t('debate.consensus')}</div>
        <div class="col-span-2">{t('debate.status')}</div>
      </div>

      <!-- Table rows -->
      <div class="divide-y divide-gray-200 dark:divide-gray-700">
        {#each debates as debate}
          <button
            class="w-full text-left px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer
                   md:grid md:grid-cols-12 md:gap-4 md:items-center"
            on:click={() => navigate('debate/' + debate.debate_id)}
          >
            <!-- Case preview -->
            <div class="md:col-span-5 mb-2 md:mb-0">
              <p class="text-sm text-gray-800 dark:text-gray-200 truncate">
                {debate.case_preview || debate.debate_id.substring(0, 16)}
              </p>
              <p class="text-xs text-gray-400 dark:text-gray-500 font-mono md:hidden">
                {debate.debate_id.substring(0, 8)}…
              </p>
            </div>

            <!-- Date -->
            <div class="md:col-span-2 text-xs text-gray-500 dark:text-gray-400 mb-1 md:mb-0">
              {formatDate(debate.created_at)}
            </div>

            <!-- Rounds -->
            <div class="md:col-span-1 text-sm text-gray-700 dark:text-gray-300 mb-1 md:mb-0">
              {debate.current_round}/{debate.max_rounds}
            </div>

            <!-- Consensus -->
            <div class="md:col-span-2 mb-1 md:mb-0">
              {#if debate.consensus_score !== null && debate.consensus_score !== undefined}
                <div class="flex items-center gap-2">
                  <div class="w-16 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 hidden md:block">
                    <div
                      class="bg-blue-600 h-1.5 rounded-full"
                      style="width: {(debate.consensus_score * 100)}%"
                    ></div>
                  </div>
                  <span class="text-xs text-gray-600 dark:text-gray-400">
                    {(debate.consensus_score * 100).toFixed(0)}%
                  </span>
                </div>
              {:else}
                <span class="text-xs text-gray-400 dark:text-gray-500">—</span>
              {/if}
            </div>

            <!-- Status -->
            <div class="md:col-span-2">
              <div class="flex items-center gap-2">
                <span class="px-2 py-1 text-xs font-medium rounded-full {statusBadgeClass(debate.status)}">
                  {t(`status.${debate.status}`)}
                </span>
                <span class="text-xs text-gray-400 dark:text-gray-500 uppercase hidden md:inline">
                  {debate.language}
                </span>
              </div>
            </div>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Pagination -->
  {#if debates.length > 0}
    <div class="flex items-center justify-between">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {t('archive.showing', { from: currentPage * PAGE_SIZE + 1, to: currentPage * PAGE_SIZE + debates.length })}
      </p>
      <div class="flex gap-2">
        <button
          class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600
                 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700
                 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          on:click={() => goToPage(currentPage - 1)}
          disabled={currentPage === 0 || $loading}
        >
          ← {t('archive.prevPage')}
        </button>
        <span class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400">
          {t('archive.page')} {currentPage + 1}
        </span>
        <button
          class="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600
                 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700
                 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          on:click={() => goToPage(currentPage + 1)}
          disabled={debates.length < PAGE_SIZE || $loading}
        >
          {t('archive.nextPage')} →
        </button>
      </div>
    </div>
  {/if}
</div>
