<script>
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import ModuleManager from '../components/ModuleManager.svelte';
  import {
    listComposerBundles,
    createComposerBundle,
    getComposerBundle,
    exportComposerBundle,
    importComposerBundle,
  } from '../lib/blueprint/api.js';

  let { navigate } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const TABS = [
    { id: 'llm-profiles', label: 'LLM Profiles' },
    { id: 'role-types', label: 'Agent Cores' },
    { id: 'prompts', label: 'Argumentation Patterns' },
    { id: 'tone-profiles', label: 'Tone Profiles' },
    { id: 'prompt-modifiers', label: 'Prompt Modifiers' },
    { id: 'agent-bundles', label: 'Agent Bundles' },
    { id: 'workflows', label: 'Workflows' },
    { id: 'kitsune', label: 'Kitsune' },
    { id: 'translations', label: '🌐 Translations' },
  ];

  let activeTab = $state('llm-profiles');
  let statusMessage = $state('');

  // Agent Bundles tab state
  let bundles = $state([]);
  let isLoadingBundles = $state(false);
  let bundleError = $state('');
  let bundleName = $state('');
  let bundleDescription = $state('');
  let isSavingBundle = $state(false);
  let selectedBundleId = $state('');

  onMount(async () => {
    // No initial load needed — ModuleManager fetches on mount
  });

  // --- Agent Bundles handlers ---

  async function loadBundles() {
    isLoadingBundles = true;
    bundleError = '';
    try {
      bundles = await listComposerBundles({ limit: 100 });
    } catch (e) {
      bundleError = e.message;
    } finally {
      isLoadingBundles = false;
    }
  }

  async function handleCreateBundle() {
    if (!bundleName.trim()) return;
    isSavingBundle = true;
    bundleError = '';
    try {
      const bundle = await createComposerBundle({
        name: bundleName.trim(),
        description: bundleDescription.trim(),
        composition: {},
      });
      statusMessage = `Bundle "${bundle.name}" created (${bundle.id})`;
      bundleName = '';
      bundleDescription = '';
      await loadBundles();
    } catch (e) {
      bundleError = e.message;
    } finally {
      isSavingBundle = false;
    }
  }

  async function handleLoadBundle() {
    if (!selectedBundleId) return;
    bundleError = '';
    try {
      const bundle = await getComposerBundle(selectedBundleId);
      bundleName = bundle.name || '';
      bundleDescription = bundle.description || '';
      statusMessage = `Loaded bundle "${bundle.name}"`;
    } catch (e) {
      bundleError = e.message;
    }
  }

  async function handleExportBundle() {
    if (!selectedBundleId) return;
    bundleError = '';
    try {
      const result = await exportComposerBundle(selectedBundleId, true);
      statusMessage = `Bundle exported to ${result.path}`;
    } catch (e) {
      bundleError = e.message;
    }
  }

  async function handleImportBundle() {
    const moduleId = prompt('Enter module directory name (under modules/agent-bundles/):');
    if (!moduleId) return;
    bundleError = '';
    try {
      const bundle = await importComposerBundle(moduleId);
      statusMessage = `Imported bundle "${bundle.name}" (${bundle.id})`;
      await loadBundles();
    } catch (e) {
      bundleError = e.message;
    }
  }

  $effect(() => {
    if (activeTab === 'agent-bundles' && bundles.length === 0) {
      loadBundles();
    }
  });
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
    {t('modules.title') || 'Modules'}
  </h2>

  {#if statusMessage}
    <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
      {statusMessage}
      <button class="ml-2 text-blue-600 underline" onclick={() => statusMessage = ''}>{t('common.dismiss')}</button>
    </div>
  {/if}

  <div class="border-b border-gray-200 dark:border-gray-700">
    <nav class="flex space-x-4 overflow-x-auto" aria-label="Module tabs">
      {#each TABS as tab}
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap
            {activeTab === tab.id
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
          onclick={() => { activeTab = tab.id; }}
        >
          {tab.label}
        </button>
      {/each}
    </nav>
  </div>

  {#if activeTab === 'llm-profiles'}
    <ModuleManager filterCategory="llm-profiles" />

  {:else if activeTab === 'role-types'}
    <ModuleManager filterCategory="agents" />

  {:else if activeTab === 'prompts'}
    <ModuleManager filterCategory="prompts" />

  {:else if activeTab === 'tone-profiles'}
    <ModuleManager filterCategory="tone-profiles" />

  {:else if activeTab === 'prompt-modifiers'}
    <ModuleManager filterCategory="prompt-modifiers" />

  {:else if activeTab === 'agent-bundles'}
    <div class="space-y-4">
      {#if bundleError}
        <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
          {bundleError}
        </div>
      {/if}

      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">Create Bundle</h3>
        <div class="space-y-3">
          <input
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Bundle name"
            bind:value={bundleName}
          />
          <textarea
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Description (optional)"
            rows="2"
            bind:value={bundleDescription}
          ></textarea>
          <button
            class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            onclick={handleCreateBundle}
            disabled={isSavingBundle || !bundleName.trim()}
          >
            {isSavingBundle ? 'Saving...' : 'Create Bundle'}
          </button>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
            Saved Bundles
            {#if !isLoadingBundles}
              <span class="text-sm font-normal text-gray-400 ml-2">({bundles.length})</span>
            {/if}
          </h3>
        </div>
        {#if isLoadingBundles}
          <div class="p-6 text-center text-gray-500 dark:text-gray-400">{t('common.loading')}</div>
        {:else if bundles.length === 0}
          <div class="p-6 text-center text-gray-500 dark:text-gray-400">No bundles yet.</div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-gray-50 dark:bg-gray-750 border-b border-gray-200 dark:border-gray-700">
                  <th class="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Name</th>
                  <th class="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">ID</th>
                  <th class="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Description</th>
                  <th class="text-right px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each bundles as bundle (bundle.id)}
                  <tr class="border-b border-gray-100 dark:border-gray-700 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
                    <td class="px-4 py-2.5 font-medium text-gray-800 dark:text-white">{bundle.name}</td>
                    <td class="px-4 py-2.5 text-gray-500 dark:text-gray-400 font-mono text-xs">{bundle.id}</td>
                    <td class="px-4 py-2.5 text-gray-500 dark:text-gray-400">{bundle.description || '—'}</td>
                    <td class="px-4 py-2.5 text-right">
                      <div class="flex items-center justify-end gap-1">
                        <button
                          class="px-2.5 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                          onclick={() => { selectedBundleId = bundle.id; handleLoadBundle(); }}
                        >
                          Load
                        </button>
                        <button
                          class="px-2.5 py-1 text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors"
                          onclick={() => { selectedBundleId = bundle.id; handleExportBundle(); }}
                        >
                          Export
                        </button>
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>

      <div class="flex items-center justify-between">
        <button
          class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm"
          onclick={handleImportBundle}
        >
          Import from Disk
        </button>
        <button
          class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm"
          onclick={() => navigate('bundle-composer')}
        >
          Open Full Composer →
        </button>
      </div>
    </div>

  {:else if activeTab === 'workflows'}
    <ModuleManager filterCategory="workflows" />

  {:else if activeTab === 'kitsune'}
    <ModuleManager filterCategory="kitsune" />

  {:else if activeTab === 'translations'}
    <ModuleManager filterCategory="translations" />
  {/if}
</div>
