<script>
  import { i18n } from '../lib/i18n/index.js';
  import {
    listOutputPlugins,
    startRenderJob,
    searchSessions,
  } from '../lib/output/composerApi.js';
  import { createRenderJobTracker } from '../lib/output/renderJobStore.svelte.js';
  import PluginCard from '../components/output/PluginCard.svelte';
  import ConfigForm from '../components/output/ConfigForm.svelte';
  import RenderJobStatus from '../components/output/RenderJobStatus.svelte';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  // State
  let plugins = $state([]);
  let selectedPlugin = $state(null);
  let configValues = $state({});
  let sessionSearch = $state('');
  let selectedSessionId = $state('');
  let sessionResults = $state([]);
  let showDropdown = $state(false);
  let loading = $state(false);
  let error = $state(null);
  let activeJob = $state(null);
  let tracker = $state(null);
  let searchLoading = $state(false);

  let searchTimeout = null;

  // Load plugins on mount
  $effect(() => {
    listOutputPlugins()
      .then((p) => { plugins = p; })
      .catch((e) => { error = e.message; });
  });

  function onSearchInput(e) {
    sessionSearch = e.target.value;
    selectedSessionId = '';
    if (searchTimeout) clearTimeout(searchTimeout);
    if (sessionSearch.length < 1) {
      sessionResults = [];
      showDropdown = false;
      return;
    }
    searchLoading = true;
    searchTimeout = setTimeout(async () => {
      try {
        sessionResults = await searchSessions(sessionSearch);
        showDropdown = sessionResults.length > 0;
      } catch {
        sessionResults = [];
      } finally {
        searchLoading = false;
      }
    }, 300);
  }

  function selectSession(s) {
    selectedSessionId = s.session_id;
    sessionSearch = s.title;
    showDropdown = false;
  }

  function onSearchBlur() {
    // Delay to allow click on dropdown item
    setTimeout(() => { showDropdown = false; }, 200);
  }

  function selectPlugin(plugin) {
    selectedPlugin = plugin;
    configValues = {};
    error = null;
  }

  async function handleGenerate() {
    if (!selectedSessionId && !sessionSearch.trim()) {
      error = 'Please select or enter a Session ID.';
      return;
    }
    if (!selectedPlugin) {
      error = 'Please select a plugin.';
      return;
    }

    loading = true;
    error = null;

    try {
      const result = await startRenderJob(
        selectedSessionId || sessionSearch.trim(),
        selectedPlugin.plugin_key,
        configValues
      );
      activeJob = result;
      tracker = createRenderJobTracker(result.job_id);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="max-w-4xl mx-auto p-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">
    🖨️ Output Composer
  </h1>

  <!-- Session Search with Autocomplete -->
  <div class="mb-6 relative">
    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="session-search">
      Session / Debate
    </label>
    <input
      id="session-search"
      type="text"
      value={sessionSearch}
      oninput={onSearchInput}
      onfocus={() => { if (sessionResults.length > 0) showDropdown = true; }}
      onblur={onSearchBlur}
      placeholder="Search by debate title or session ID…"
      autocomplete="off"
      class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-3 py-2 text-sm"
    />
    {#if searchLoading}
      <span class="absolute right-3 top-8 text-xs text-gray-400">Searching…</span>
    {/if}

    <!-- Autocomplete Dropdown -->
    {#if showDropdown && sessionResults.length > 0}
      <ul class="absolute z-10 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg max-h-60 overflow-y-auto">
        {#each sessionResults as s}
          <li>
            <button
              type="button"
              class="w-full text-left px-3 py-2 hover:bg-blue-50 dark:hover:bg-blue-900/30 text-sm border-b border-gray-100 dark:border-gray-700 last:border-b-0"
              onclick={() => selectSession(s)}
            >
              <span class="font-medium text-gray-900 dark:text-white">{s.title}</span>
              <span class="ml-2 text-xs text-gray-500 font-mono">{s.session_id}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    {#if selectedSessionId}
      <p class="mt-1 text-xs text-green-600 dark:text-green-400">
        ✓ Selected: {selectedSessionId}
      </p>
    {/if}
  </div>

  <!-- Plugin Selection -->
  <div class="mb-6">
    <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
      Select Output Format
    </h2>
    {#if plugins.length === 0}
      <p class="text-sm text-gray-500 dark:text-gray-400 italic">Loading plugins…</p>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each plugins as plugin}
          <PluginCard
            {plugin}
            selected={selectedPlugin?.plugin_key === plugin.plugin_key}
            onclick={() => selectPlugin(plugin)}
          />
        {/each}
      </div>
    {/if}
  </div>

  <!-- Config Form -->
  {#if selectedPlugin}
    <div class="mb-6">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
        Configuration — {selectedPlugin.plugin_name}
      </h2>
      <div class="p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
        <ConfigForm
          schema={selectedPlugin.config_schema}
          bind:value={configValues}
        />
      </div>
    </div>
  {/if}

  <!-- Error -->
  {#if error}
    <div class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
      {error}
    </div>
  {/if}

  <!-- Generate Button -->
  <div class="mb-6">
    <button
      onclick={handleGenerate}
      disabled={loading || !selectedPlugin || (!selectedSessionId && !sessionSearch.trim())}
      class="px-6 py-2.5 rounded-lg bg-blue-600 text-white font-medium text-sm
        hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      {#if loading}
        🔄 Starting…
      {:else}
        🚀 Generate
      {/if}
    </button>
  </div>

  <!-- Job Status -->
  {#if tracker}
    <div class="mb-6">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
        Render Job
      </h2>
      <RenderJobStatus {tracker} />
    </div>
  {/if}
</div>
