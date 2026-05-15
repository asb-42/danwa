<script>
  import { onMount } from 'svelte';
  import { activeProject, error } from '../lib/stores.js';
  import { getProject, getProjectConfig, updateProjectConfig, getSettings } from '../lib/api.js';
  import { i18n } from '../lib/i18n/index.js';

  let { projectId = '', navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let project = $state(null);
  let config = $state({
    language: null,
    default_max_rounds: null,
    default_consensus_threshold: null,
    search_mode: null,
    searxng_url: null,
  });
  let globalSettings = $state({});
  let isLoading = $state(false);
  let isSaving = $state(false);
  let statusMessage = $state('');

  // Search mode options
  const searchModes = ['off', 'optional', 'required'];

  onMount(async () => {
    await loadAll();
  });

  async function loadAll() {
    isLoading = true;
    error.set(null);
    try {
      const [proj, cfg, settings] = await Promise.all([
        getProject(projectId),
        getProjectConfig(projectId),
        getSettings(),
      ]);
      project = proj;
      globalSettings = settings || {};
      // Merge returned config with defaults (null = use global)
      config = {
        language: cfg.language ?? null,
        default_max_rounds: cfg.default_max_rounds ?? null,
        default_consensus_threshold: cfg.default_consensus_threshold ?? null,
        search_mode: cfg.search_mode ?? null,
        searxng_url: cfg.searxng_url ?? null,
      };
    } catch (err) {
      error.set(err.message);
    } finally {
      isLoading = false;
    }
  }

  function getGlobalLabel(field) {
    const val = globalSettings[field];
    if (val === undefined || val === null || val === '') return t('projects.globalDefault');
    return `${t('projects.globalDefault')}: ${val}`;
  }

  async function handleSave() {
    isSaving = true;
    error.set(null);
    statusMessage = '';
    try {
      // Build config payload — only include non-null/non-empty values
      const payload = {};
      if (config.language && config.language.trim()) payload.language = config.language.trim();
      if (config.default_max_rounds !== null && config.default_max_rounds !== '' && config.default_max_rounds !== undefined) {
        payload.default_max_rounds = Number(config.default_max_rounds);
      }
      if (config.default_consensus_threshold !== null && config.default_consensus_threshold !== '' && config.default_consensus_threshold !== undefined) {
        payload.default_consensus_threshold = Number(config.default_consensus_threshold);
      }
      if (config.search_mode) payload.search_mode = config.search_mode;
      if (config.searxng_url && config.searxng_url.trim()) payload.searxng_url = config.searxng_url.trim();

      await updateProjectConfig(projectId, payload);
      statusMessage = `✓ ${t('projects.projectUpdated')}`;
      // Update active project name if needed
      if ($activeProject?.id === projectId && project) {
        activeProject.set({ id: project.id, name: project.name });
      }
    } catch (err) {
      error.set(err.message);
    } finally {
      isSaving = false;
    }
  }

  function clearField(field) {
    config[field] = null;
  }
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex items-center gap-3">
    <button
      class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
      onclick={() => navigate('projects')}
      title={t('common.back')}
    >
      ←
    </button>
    <div class="flex-1 min-w-0">
      <h2 class="text-2xl font-bold text-gray-800 dark:text-white truncate">
        {project ? project.name : '...'}
      </h2>
      <p class="text-sm text-gray-500 dark:text-gray-400">{t('projects.config')}</p>
    </div>
  </div>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  {#if statusMessage}
    <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
      {statusMessage}
    </div>
  {/if}

  {#if isLoading}
    <div class="flex items-center justify-center h-32">
      <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
    </div>
  {:else}
    <!-- Hint -->
    <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 text-blue-700 dark:text-blue-300 text-sm">
      ℹ️ {t('projects.configHint')}
    </div>

    <!-- Config Form -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
      <div class="p-6 space-y-6">

        <!-- Language -->
        <div>
          <label for="cfg-language" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('projects.language')}
          </label>
          <div class="flex items-center gap-2">
            <select
              id="cfg-language"
              bind:value={config.language}
              class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={null}>{getGlobalLabel('language')}</option>
              <option value="de">Deutsch</option>
              <option value="en">English</option>
            </select>
            {#if config.language !== null}
              <button
                class="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                onclick={() => clearField('language')}
                title={t('projects.globalDefault')}
              >
                ✕
              </button>
            {/if}
          </div>
        </div>

        <!-- Default Max Rounds -->
        <div>
          <label for="cfg-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('projects.defaultMaxRounds')}
          </label>
          <div class="flex items-center gap-2">
            <input
              id="cfg-rounds"
              type="number"
              min="1"
              max="50"
              bind:value={config.default_max_rounds}
              placeholder={getGlobalLabel('default_max_rounds')}
              class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                     placeholder:text-gray-400 dark:placeholder:text-gray-500"
            />
            {#if config.default_max_rounds !== null && config.default_max_rounds !== ''}
              <button
                class="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                onclick={() => clearField('default_max_rounds')}
                title={t('projects.globalDefault')}
              >
                ✕
              </button>
            {/if}
          </div>
        </div>

        <!-- Default Consensus Threshold -->
        <div>
          <label for="cfg-threshold" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('projects.defaultConsensusThreshold')}
          </label>
          <div class="flex items-center gap-2">
            <input
              id="cfg-threshold"
              type="number"
              min="0"
              max="1"
              step="0.05"
              bind:value={config.default_consensus_threshold}
              placeholder={getGlobalLabel('default_consensus_threshold')}
              class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                     placeholder:text-gray-400 dark:placeholder:text-gray-500"
            />
            {#if config.default_consensus_threshold !== null && config.default_consensus_threshold !== ''}
              <button
                class="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                onclick={() => clearField('default_consensus_threshold')}
                title={t('projects.globalDefault')}
              >
                ✕
              </button>
            {/if}
          </div>
        </div>

        <!-- Search Mode -->
        <div>
          <label for="cfg-search" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('projects.searchMode')}
          </label>
          <div class="flex items-center gap-2">
            <select
              id="cfg-search"
              bind:value={config.search_mode}
              class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={null}>{getGlobalLabel('search_mode')}</option>
              {#each searchModes as mode}
                <option value={mode}>{mode}</option>
              {/each}
            </select>
            {#if config.search_mode !== null}
              <button
                class="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                onclick={() => clearField('search_mode')}
                title={t('projects.globalDefault')}
              >
                ✕
              </button>
            {/if}
          </div>
        </div>

        <!-- SearXNG URL -->
        <div>
          <label for="cfg-searxng" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('projects.searxngUrl')}
          </label>
          <div class="flex items-center gap-2">
            <input
              id="cfg-searxng"
              type="url"
              bind:value={config.searxng_url}
              placeholder={getGlobalLabel('searxng_url')}
              class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                     placeholder:text-gray-400 dark:placeholder:text-gray-500"
            />
            {#if config.searxng_url !== null && config.searxng_url !== ''}
              <button
                class="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
                onclick={() => clearField('searxng_url')}
                title={t('projects.globalDefault')}
              >
                ✕
              </button>
            {/if}
          </div>
        </div>

      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={() => navigate('projects')}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? '...' : t('common.save')}
        </button>
      </div>
    </div>
  {/if}
</div>
