<script>
  import { onMount } from 'svelte';
  import { loading, error, activeProject } from '../lib/stores.js';
  import { getDebates, listDebateForks, deleteDebate, softDeleteSession, restoreSession, getTrace } from '../lib/api.js';
  import { i18n, formatNumber, formatDate } from '../lib/i18n/index.js';

  let { navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const PAGE_SIZE = 20;

  let debates = $state([]);
  let totalCount = $state(0);
  let currentPage = $state(0);
  let searchQuery = $state('');
  let statusFilter = $state('');
  let searchTimeout = null;

  // Delete confirmation state
  let deleteConfirmId = $state(null);
  let isDeleting = $state(false);

  // Archive/Restore state
  let archiveConfirmId = $state(null);
  let isArchiving = $state(false);
  let restoringId = $state(null);

  // Trace state
  let traceData = $state(null);
  let traceSessionId = $state(null);
  
  // Fork state
  let forksByDebate = $state({});
  let isLoadingTrace = $state(false);
  let showTraceModal = $state(false);

  let projectId = $derived($activeProject?.id);

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

  // Reload when project changes
  $effect(() => {
    if (projectId) {
      loadDebates();
    }
  });

  async function loadDebates() {
    loading.set(true);
    error.set(null);
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
      error.set(err.message);
      debates = [];
    } finally {
      loading.set(false);
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

  function confirmDelete(debateId) {
    deleteConfirmId = debateId;
  }

  function cancelDelete() {
    deleteConfirmId = null;
  }

  function confirmArchive(debateId) {
    archiveConfirmId = debateId;
  }

  function cancelArchive() {
    archiveConfirmId = null;
  }

  async function handleArchive(debateId) {
    isArchiving = true;
    try {
      await softDeleteSession(debateId);
      // Update local state — mark as archived
      debates = debates.map(d =>
        d.debate_id === debateId ? { ...d, archived: true } : d
      );
      archiveConfirmId = null;
    } catch (err) {
      error.set(err.message);
    } finally {
      isArchiving = false;
    }
  }

  async function handleRestore(debateId) {
    restoringId = debateId;
    try {
      await restoreSession(debateId);
      // Update local state — unmark archived
      debates = debates.map(d =>
        d.debate_id === debateId ? { ...d, archived: false } : d
      );
    } catch (err) {
      error.set(err.message);
    } finally {
      restoringId = null;
    }
  }

  async function handleViewTrace(debateId) {
    isLoadingTrace = true;
    showTraceModal = true;
    traceSessionId = debateId;
    try {
      traceData = await getTrace(debateId);
    } catch (err) {
      traceData = { error: err.message };
    } finally {
      isLoadingTrace = false;
    }
  }

  function closeTraceModal() {
    showTraceModal = false;
    traceData = null;
    traceSessionId = null;
  }

  async function handleDelete(debateId) {
    isDeleting = true;
    try {
      await deleteDebate(debateId);
      // Remove from local list
      debates = debates.filter(d => d.debate_id !== debateId);
      deleteConfirmId = null;
    } catch (err) {
      error.set(err.message);
    } finally {
      isDeleting = false;
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
            oninput={handleSearch}
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
          onchange={handleFilterChange}
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
      <div class="hidden md:grid md:grid-cols-12 gap-2 px-4 py-3 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
        <div class="col-span-2">{t('debate.titleLabel')}</div>
        <div class="col-span-2">{t('archive.project')}</div>
        <div class="col-span-1">{t('archive.date')}</div>
        <div class="col-span-1">{t('debate.round')}</div>
        <div class="col-span-1">{t('debate.consensus')}</div>
        <div class="col-span-1">{t('archive.forks')}</div>
        <div class="col-span-1">{t('archive.parentDebate')}</div>
        <div class="col-span-1">{t('debate.status')}</div>
        <div class="col-span-2"></div>
      </div>

      <!-- Table rows -->
      <div class="divide-y divide-gray-200 dark:divide-gray-700">
        {#each debates as debate}
          <div
            class="w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors
                   md:grid md:grid-cols-12 md:gap-2 md:items-center cursor-pointer"
            onclick={() => navigate((debate.debate_id && debate.debate_id.startsWith('mvp-') ? 'mvp-debate' : 'debate') + '/' + debate.debate_id)}
            role="button"
            tabindex="0"
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate((debate.debate_id && debate.debate_id.startsWith('mvp-') ? 'mvp-debate' : 'debate') + '/' + debate.debate_id); } }}
          >
            <!-- Title / Case preview -->
            <div class="md:col-span-2 mb-2 md:mb-0">
              {#if debate.title}
                <p class="text-sm font-semibold text-gray-900 dark:text-white line-clamp-1">
                  {debate.title}
                </p>
                <p class="text-xs text-gray-500 dark:text-gray-400 line-clamp-1 mt-0.5">
                  {debate.case_preview || debate.debate_id.substring(0, 16)}
                </p>
              {:else}
                <p class="text-sm text-gray-800 dark:text-gray-200 line-clamp-2">
                  {debate.case_text || debate.case_preview || debate.debate_id.substring(0, 16)}
                </p>
              {/if}
              <p class="text-xs text-gray-400 dark:text-gray-500 font-mono mt-0.5">
                {debate.debate_id.substring(0, 12)}…
              </p>
              {#if debate.is_mvp}
                <span class="inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 mt-0.5">MVP</span>
              {/if}
            </div>

            <!-- Project -->
            <div class="md:col-span-2 text-xs text-blue-600 dark:text-blue-400 font-medium mb-1 md:mb-0">
              {#if debate.project_name}
                📁 {debate.project_name}
              {:else}
                <span class="text-gray-400 dark:text-gray-500">—</span>
              {/if}
            </div>

            <!-- Date -->
            <div class="md:col-span-1 text-xs text-gray-500 dark:text-gray-400 mb-1 md:mb-0">
              {formatDate(debate.created_at)}
            </div>

            <!-- Rounds -->
            <div class="md:col-span-1 text-sm text-gray-700 dark:text-gray-300 mb-1 md:mb-0">
              {debate.current_round}/{debate.max_rounds}
            </div>

            <!-- Consensus -->
            <div class="md:col-span-1 mb-1 md:mb-0">
              {#if debate.consensus_score !== null && debate.consensus_score !== undefined}
                <div class="flex items-center gap-2">
                  <div class="w-10 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 hidden md:block">
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
            <div class="md:col-span-1">
              <div class="flex items-center gap-2">
                <span class="px-2 py-1 text-xs font-medium rounded-full {statusBadgeClass(debate.status)}">
                  {t(`status.${debate.status}`)}
                </span>
                {#if debate.archived}
                  <span class="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-200 text-gray-600 dark:bg-gray-600 dark:text-gray-300">
                    📦 {t('session.archived')}
                  </span>
                {/if}
              </div>
            </div>

            <!-- Actions -->
            <div class="md:col-span-2 flex justify-end gap-1">
              <!-- Archive / Restore button -->
              {#if debate.archived}
                {#if restoringId === debate.debate_id}
                  <span class="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></span>
                {:else}
                  <button
                    class="p-1.5 rounded text-green-500 hover:text-green-600 dark:hover:text-green-400
                           hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors"
                    onclick={(e) => { e.stopPropagation(); handleRestore(debate.debate_id); }}
                    aria-label={t('session.restore')}
                    title={t('session.restore')}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                    </svg>
                  </button>
                {/if}
              {:else}
                {#if archiveConfirmId === debate.debate_id}
                  <div class="flex items-center gap-1">
                    <button
                      class="px-2 py-1 text-xs font-medium rounded bg-amber-600 text-white hover:bg-amber-700
                             disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      onclick={() => handleArchive(debate.debate_id)}
                      disabled={isArchiving}
                    >
                      {isArchiving ? '...' : t('common.yes')}
                    </button>
                    <button
                      class="px-2 py-1 text-xs font-medium rounded bg-gray-200 dark:bg-gray-600
                             text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500
                             transition-colors"
                      onclick={cancelArchive}
                      disabled={isArchiving}
                    >
                      {t('common.no')}
                    </button>
                  </div>
                {:else}
                  <button
                    class="p-1.5 rounded text-amber-400 hover:text-amber-600 dark:hover:text-amber-400
                           hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors"
                    onclick={(e) => { e.stopPropagation(); confirmArchive(debate.debate_id); }}
                    aria-label={t('session.softDelete')}
                    title={t('session.softDelete')}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                    </svg>
                  </button>
                {/if}
              {/if}

              <!-- Trace button -->
              <button
                class="p-1.5 rounded text-purple-400 hover:text-purple-600 dark:hover:text-purple-400
                       hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors"
                onclick={(e) => { e.stopPropagation(); handleViewTrace(debate.debate_id); }}
                aria-label={t('archive.viewTrace')}
                title={t('archive.viewTrace')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
              </button>

              <!-- Delete button -->
              {#if deleteConfirmId === debate.debate_id}
                <div class="flex items-center gap-1">
                  <button
                    class="px-2 py-1 text-xs font-medium rounded bg-red-600 text-white hover:bg-red-700
                           disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    onclick={() => handleDelete(debate.debate_id)}
                    disabled={isDeleting}
                    aria-label={t('archive.confirmDelete')}
                  >
                    {isDeleting ? '...' : t('common.yes')}
                  </button>
                  <button
                    class="px-2 py-1 text-xs font-medium rounded bg-gray-200 dark:bg-gray-600
                           text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500
                           transition-colors"
                    onclick={cancelDelete}
                    disabled={isDeleting}
                    aria-label={t('common.cancel')}
                  >
                    {t('common.no')}
                  </button>
                </div>
              {:else}
                <button
                  class="p-1.5 rounded text-gray-400 hover:text-red-600 dark:hover:text-red-400
                         hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  onclick={(e) => { e.stopPropagation(); confirmDelete(debate.debate_id); }}
                  aria-label={t('common.delete')}
                  title={t('common.delete')}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              {/if}
            </div>
          </div>
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
          onclick={() => goToPage(currentPage - 1)}
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
          onclick={() => goToPage(currentPage + 1)}
          disabled={debates.length < PAGE_SIZE || $loading}
        >
          {t('archive.nextPage')} →
        </button>
      </div>
    </div>
  {/if}
</div>

<!-- Trace Modal -->
{#if showTraceModal}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeTraceModal} role="dialog" aria-modal="true" tabindex="-1">
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-y-auto mx-4"
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    >
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {t('archive.traceTitle')} — {traceSessionId?.substring(0, 12)}…
        </h3>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none"
          onclick={closeTraceModal}
        >
          ✕
        </button>
      </div>
      <div class="px-6 py-4">
        {#if isLoadingTrace}
          <div class="flex items-center justify-center h-24">
            <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
          </div>
        {:else if traceData?.error}
          <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300">
            {traceData.error}
          </div>
        {:else if traceData}
          <pre class="text-xs text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-4 rounded-lg overflow-x-auto max-h-[60vh] whitespace-pre-wrap font-mono">{JSON.stringify(traceData, null, 2)}</pre>
        {/if}
      </div>
    </div>
  </div>
{/if}
