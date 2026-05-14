<script>
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import {
    getSupportedLanguages,
    getModules,
    getModule,
    getTranslationStatus,
    getTranslationStatistics,
    translateModule,
    approveTranslation,
    invalidateTranslation,
    batchTranslate,
  } from '../lib/api.js';
  import {
    selectedModuleId,
    translationResults,
    supportedLanguages,
    translationStatistics,
  } from '../lib/stores.js';

  let { navigate } = $props();
  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  // --- State ---
  let modules = $state([]);
  let languages = $state([]);
  let loadingModules = $state(false);
  let loadingLanguages = $state(false);
  let translatingModules = $state(false);
  let activeTab = $state('modules');

  // Batch translate state
  let selectedTargetLang = $state('de');
  let batchForce = $state(false);
  let selectedForBatch = $state([]);
  let batchProgress = $state({});

  // Single module translate state
  let singleTranslateOpen = $state(false);
  let singleModuleId = $state('');
  let singleTargetLang = $state('de');
  let singleForce = $state(false);
  let singleSkipBackTranslation = $state(false);
  let singleInProgress = $state(false);

  onMount(async () => {
    await loadLanguages();
    await loadModules();
  });

  async function loadLanguages() {
    loadingLanguages = true;
    try {
      const data = await getSupportedLanguages();
      languages = data.supported_languages || [];
      supportedLanguages.set(languages);
    } catch (e) {
      console.error('Failed to load languages:', e);
    } finally {
      loadingLanguages = false;
    }
  }

  async function loadModules() {
    loadingModules = true;
    try {
      const data = await getModules();
      modules = data.modules || [];
      // Pre-select all modules for batch
      selectedForBatch = modules.map(m => m.id);
    } catch (e) {
      console.error('Failed to load modules:', e);
    } finally {
      loadingModules = false;
    }
  }

  async function loadModuleStatus(moduleId) {
    const results = $translationResults;
    try {
      const data = await getTranslationStatus(moduleId);
      results[moduleId] = data.translations || [];
      translationResults.set(results);
    } catch (e) {
      console.error(`Failed to load status for ${moduleId}:`, e);
    }
  }

  async function loadModuleStats(moduleId) {
    const stats = $translationStatistics;
    try {
      const data = await getTranslationStatistics(moduleId);
      stats[moduleId] = data.statistics || {};
      translationStatistics.set(stats);
    } catch (e) {
      console.error(`Failed to load stats for ${moduleId}:`, e);
    }
  }

  function handleSelectModule(moduleId) {
    selectedModuleId.set(moduleId);
    loadModuleStatus(moduleId);
    loadModuleStats(moduleId);
  }

  async function handleTranslateModule() {
    if (!singleModuleId) return;
    singleInProgress = true;
    try {
      const result = await translateModule(singleModuleId, {
        target_language: singleTargetLang,
        force: singleForce,
        skip_back_translation: singleSkipBackTranslation,
      });
      const results = $translationResults;
      results[singleModuleId] = result.translations || [];
      translationResults.set(results);
      singleTranslateOpen = false;
    } catch (e) {
      console.error('Translation failed:', e);
    } finally {
      singleInProgress = false;
    }
  }

  async function handleBatchTranslate() {
    if (selectedForBatch.length === 0) return;
    translatingModules = true;
    batchProgress = {};
    selectedForBatch.forEach(id => {
      batchProgress[id] = { status: 'pending', progress: 0 };
    });

    try {
      const result = await batchTranslate({
        module_ids: selectedForBatch,
        target_language: selectedTargetLang,
        force: batchForce,
      });
      // Update progress from result
      for (const r of result.results || []) {
        batchProgress[r.module_id] = {
          status: r.status,
          files_translated: r.files_translated,
          files_skipped: r.files_skipped,
          files_errored: r.files_errored,
        };
      }
    } catch (e) {
      console.error('Batch translation failed:', e);
    } finally {
      translatingModules = false;
    }
  }

  async function handleApprove(moduleId, filePath, approved) {
    try {
      await approveTranslation(moduleId, { file_path: filePath, approved });
      await loadModuleStatus(moduleId);
    } catch (e) {
      console.error('Failed to update approval:', e);
    }
  }

  async function handleInvalidate(moduleId, filePath) {
    try {
      await invalidateTranslation(moduleId, filePath ? { file_path: filePath } : {});
      const results = $translationResults;
      if (filePath) {
        results[moduleId] = (results[moduleId] || []).filter(t => t.file_path !== filePath);
      } else {
        delete results[moduleId];
      }
      translationResults.set(results);
      const stats = $translationStatistics;
      delete stats[moduleId];
      translationStatistics.set(stats);
    } catch (e) {
      console.error('Failed to invalidate:', e);
    }
  }

  function qualityColor(score) {
    if (score >= 0.8) return 'text-green-600 dark:text-green-400';
    if (score >= 0.6) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  }

  function qualityBg(score) {
    if (score >= 0.8) return 'bg-green-100 dark:bg-green-900/30';
    if (score >= 0.6) return 'bg-yellow-100 dark:bg-yellow-900/30';
    return 'bg-red-100 dark:bg-red-900/30';
  }

  function qualityBarWidth(score) {
    return `${Math.round((score || 0) * 100)}%`;
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="space-y-6" onclick={() => {}} onkeydown={() => {}}>
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
      {t('translation.title')}
    </h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-50"
      onclick={loadModules}
      disabled={loadingModules}
    >
      {loadingModules ? t('common.loading') : '🔄 ' + t('translation.refreshModules')}
    </button>
  </div>

  {#if $i18n['translation.noModules']}
  {/if}

  <!-- Tab Navigation -->
  <div class="border-b border-gray-200 dark:border-gray-700">
    <nav class="flex space-x-4" aria-label="Translation tabs">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
          {activeTab === 'modules'
            ? 'border-blue-500 text-blue-600 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
        onclick={() => { activeTab = 'modules'; }}
      >
        {t('translation.modules')}
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
          {activeTab === 'batch'
            ? 'border-blue-500 text-blue-600 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
        onclick={() => { activeTab = 'batch'; }}
      >
        {t('translation.batchTranslate')}
      </button>
    </nav>
  </div>

  <!-- Module Translation Status Tab -->
  {#if activeTab === 'modules'}
    {#if loadingModules && languages.length === 0}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
      </div>
    {:else if modules.length === 0}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 text-center">
        <p class="text-gray-500 dark:text-gray-400">{t('translation.noModules')}</p>
      </div>
    {:else}
      <!-- Language Selector -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4 mb-4">
        <div class="flex items-center gap-4">
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
            {t('translation.targetLanguage')}
          </label>
          <div class="flex-1 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
            {#each languages as lang}
              <button
                class="px-3 py-2 rounded-lg text-sm font-medium transition-colors
                  {selectedTargetLang === lang
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}"
                onclick={() => { selectedTargetLang = lang; }}
              >
                {lang.toUpperCase()}
              </button>
            {/each}
          </div>
        </div>
      </div>

      <!-- Module List -->
      <div class="space-y-4">
        {#each modules as module (module.id)}
          <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
            <!-- Module Header -->
            <div
              class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              onclick={() => handleSelectModule(module.id)}
            >
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold text-sm">
                  {module.id.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h3 class="text-sm font-semibold text-gray-800 dark:text-white">{module.id}</h3>
                  <p class="text-xs text-gray-500 dark:text-gray-400">v{module.version || '0.0.0'} · {module.manifest?.name || ''}</p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                {#if $translationStatistics[module.id]}
                  {@const stats = $translationStatistics[module.id]}
                  <span class="text-xs px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                    {stats.approved || 0}/{stats.total || 0} {t('translation.approved')}
                  </span>
                {/if}
                <button
                  class="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
                  disabled={singleInProgress}
                  onclick={(e) => { e.stopPropagation(); singleModuleId = module.id; singleTranslateOpen = true; }}
                >
                  {singleInProgress && singleModuleId === module.id ? t('translation.translating') : t('translation.translate')}
                </button>
              </div>
            </div>

            <!-- Translation Details (collapsible) -->
            {#if $selectedModuleId === module.id}
              <div class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
                {#if $translationResults[module.id]}
                  {@const files = $translationResults[module.id]}
                  {#if files.length === 0}
                    <p class="text-sm text-gray-500 dark:text-gray-400 py-2">{t('translation.noTranslations')}</p>
                  {:else}
                    <div class="space-y-2">
                      {#each files as file (file.file_path)}
                        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                          <div class="flex-1 min-w-0 mr-3">
                            <p class="text-sm font-medium text-gray-800 dark:text-white truncate">{file.file_path}</p>
                            <div class="flex items-center gap-2 mt-1">
                              {#if file.quality_score != null}
                                <span class={`text-xs font-medium ${qualityColor(file.quality_score)}`}>
                                  {t('translation.quality')}: {(file.quality_score * 100).toFixed(0)}%
                                </span>
                              {/if}
                              {#if file.approved !== undefined}
                                <span class="text-xs px-1.5 py-0.5 rounded-full text-xs
                                  {file.approved
                                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                    : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'}">
                                  {file.approved ? t('translation.approved') : t('translation.pending')}
                                </span>
                              {/if}
                            </div>
                            {#if file.quality_score != null}
                              <div class="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5 mt-1">
                                <div
                                  class="h-1.5 rounded-full transition-all duration-500 {qualityBarWidth(file.quality_score) === '0%' ? '' : 'bg-blue-600 dark:bg-blue-400'}"
                                  style="width: {qualityBarWidth(file.quality_score)}"
                                  role="progressbar"
                                  aria-valuenow={Math.round(file.quality_score * 100)}
                                  aria-valuemin="0"
                                  aria-valuemax="100"
                                ></div>
                              </div>
                            {/if}
                          </div>
                          <div class="flex gap-1 flex-shrink-0">
                            <button
                              class="p-1.5 text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 rounded transition-colors"
                              title={file.approved ? t('translation.reject') : t('translation.approve')}
                              onclick={() => handleApprove(module.id, file.file_path, !file.approved)}
                            >
                              {file.approved ? '✅' : '⏳'}
                            </button>
                            <button
                              class="p-1.5 text-gray-500 hover:text-red-600 dark:hover:text-red-400 rounded transition-colors"
                              title={t('translation.invalidate')}
                              onclick={() => handleInvalidate(module.id, file.file_path)}
                            >
                              🗑️
                            </button>
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                {:else}
                  <div class="flex items-center justify-center py-8">
                    <button
                      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                      onclick={() => handleTranslateModule()}
                      disabled={singleInProgress}
                    >
                      {singleInProgress ? t('translation.translating') : t('translation.translateModule')}
                    </button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Batch Translate Tab -->
  {:else if activeTab === 'batch'}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-6">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        {t('translation.batchTranslate')}
      </h3>

      <!-- Target Language -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {t('translation.targetLanguage')}
        </label>
        <div class="flex flex-wrap gap-2">
          {#each languages as lang}
            <button
              class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
                {selectedTargetLang === lang
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}"
              onclick={() => { selectedTargetLang = lang; }}
            >
              {lang.toUpperCase()}
            </button>
          {/each}
        </div>
      </div>

      <!-- Module Selection -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {t('translation.selectModules')}
        </label>
        {#if modules.length === 0}
          <p class="text-sm text-gray-500 dark:text-gray-400">{t('translation.noModules')}</p>
        {:else}
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 max-h-60 overflow-y-auto p-2 bg-gray-50 dark:bg-gray-700 rounded-lg">
            {#each modules as module (module.id)}
              <label class="flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors">
                <input
                  type="checkbox"
                  checked={selectedForBatch.includes(module.id)}
                  onchange={() => {
                    if (selectedForBatch.includes(module.id)) {
                      selectedForBatch = selectedForBatch.filter(id => id !== module.id);
                    } else {
                      selectedForBatch = [...selectedForBatch, module.id];
                    }
                  }}
                  class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span class="text-sm text-gray-700 dark:text-gray-300 truncate">{module.id}</span>
              </label>
            {/each}
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {selectedForBatch.length} / {modules.length} {t('translation.modulesSelected')}
          </p>
        {/if}
      </div>

      <!-- Options -->
      <div class="flex items-center gap-6 mb-4">
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" bind:checked={batchForce} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('translation.forceReTranslate')}</span>
        </label>
      </div>

      <!-- Progress -->
      {#if Object.keys(batchProgress).length > 0}
        <div class="mb-4 space-y-2">
          <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300">{t('translation.progress')}</h4>
          {#each modules as module (module.id)}
            {@const prog = batchProgress[module.id]}
            {#if prog}
              <div class="flex items-center gap-3">
                <span class="text-xs text-gray-600 dark:text-gray-400 w-32 truncate">{module.id}</span>
                <div class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-3">
                  <div
                    class="h-3 rounded-full transition-all duration-300
                      {prog.status === 'completed' ? 'bg-green-500' : prog.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'}"
                    style="width: {prog.status === 'completed' || prog.status === 'failed' ? '100%' : '30%'}"
                  ></div>
                </div>
                <span class="text-xs text-gray-500 dark:text-gray-400 w-20 text-right">
                  {#if prog.status === 'completed'}
                    ✅ ({prog.files_translated || 0}/{((prog.files_translated || 0) + (prog.files_skipped || 0) + (prog.files_errored || 0)) || '?'})
                  {:else if prog.status === 'failed'}
                    ❌
                  {:else}
                    ⏳ {t('common.loading')}...
                  {/if}
                </span>
              </div>
            {/if}
          {/each}
        </div>
      {/if}

      <!-- Start Batch -->
      <button
        class="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 font-medium"
        onclick={handleBatchTranslate}
        disabled={translatingModules || selectedForBatch.length === 0}
      >
        {translatingModules ? '⏳ ' + t('translation.translating') : '🚀 ' + t('translation.startBatch')}
        {#if selectedForBatch.length > 0}({selectedForBatch.length}){/if}
      </button>
    </div>
  {/if}
</div>

<!-- Single Module Translate Dialog -->
{#if singleTranslateOpen}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={() => { singleTranslateOpen = false; }} role="dialog" aria-modal="true" tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6" role="presentation" onclick={(e) => e.stopPropagation()}>
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {t('translation.translateModule')}
        </h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none" onclick={() => { singleTranslateOpen = false; }}>✕</button>
      </div>
      <div class="space-y-4">
        <div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">{t('translation.moduleLabel')}: <strong>{singleModuleId}</strong></p>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('translation.targetLanguage')}
          </label>
          <select
            bind:value={singleTargetLang}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          >
            {#each languages as lang}
              <option value={lang}>{lang.toUpperCase()}</option>
            {/each}
          </select>
        </div>
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" bind:checked={singleForce} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('translation.forceReTranslate')}</span>
        </label>
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" bind:checked={singleSkipBackTranslation} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('translation.skipBackTranslation')}</span>
        </label>
      </div>
      <div class="flex items-center justify-end gap-3 mt-6">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={() => { singleTranslateOpen = false; }}>
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          onclick={handleTranslateModule}
          disabled={singleInProgress}
        >
          {singleInProgress ? t('translation.translating') : t('translation.startTranslate')}
        </button>
      </div>
    </div>
  </div>
{/if}
