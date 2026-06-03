<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { error } from '../lib/stores.js';
  import {
    listComposerComponents,
    previewComposition,
    createComposerBundle,
    updateComposerBundle,
    getComposerBundle,
    listComposerBundles,
    exportComposerBundle,
    importComposerBundle,
  } from '../lib/blueprint/api.js';

  let t = $derived($tStore);

  let agentCores = $state([]);
  let argPatterns = $state([]);
  let toneProfiles = $state([]);
  let promptModifiers = $state([]);
  let llmProfiles = $state([]);

  let selectedAgentCore = $state('');
  let selectedArgPattern = $state('');
  let selectedToneProfile = $state('');
  let selectedPromptModifier = $state('');
  let selectedLLMProfile = $state('');

  let previewPrompt = $state('');
  let isPreviewing = $state(false);

  let bundleName = $state('');
  let bundleDescription = $state('');
  let isSaving = $state(false);
  let savedBundleId = $state(null);
  let statusMessage = $state('');

  let bundles = $state([]);
  let isLoadingBundles = $state(false);
  let selectedBundleId = $state('');

  let isLoading = $state(false);

  onMount(async () => {
    isLoading = true;
    try {
      const components = await listComposerComponents();
      agentCores = components.agent_cores || [];
      argPatterns = components.argumentation_patterns || [];
      toneProfiles = components.tone_profiles || [];
      promptModifiers = components.prompt_modifiers || [];
      llmProfiles = components.llm_profiles || [];
      await loadBundles();
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoading = false;
    }
  });

  async function loadBundles() {
    isLoadingBundles = true;
    try {
      bundles = await listComposerBundles({ limit: 100 });
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingBundles = false;
    }
  }

  async function handlePreview() {
    isPreviewing = true;
    previewPrompt = '';
    try {
      const result = await previewComposition({
        agent_core_id: selectedAgentCore,
        argumentation_pattern_id: selectedArgPattern,
        tone_profile_id: selectedToneProfile,
        prompt_modifier_id: selectedPromptModifier,
      });
      previewPrompt = result.prompt;
    } catch (e) {
      error.set(e.message);
    } finally {
      isPreviewing = false;
    }
  }

  async function handleSave() {
    if (!bundleName.trim()) return;
    isSaving = true;
    try {
      const payload = {
        name: bundleName.trim(),
        description: bundleDescription.trim(),
        composition: {
          agent_core_id: selectedAgentCore,
          argumentation_pattern_id: selectedArgPattern,
          tone_profile_id: selectedToneProfile,
          prompt_modifier_id: selectedPromptModifier,
        },
        llm_profile_id: selectedLLMProfile,
      };

      let bundle;
      if (savedBundleId) {
        // Update existing bundle
        bundle = await updateComposerBundle(savedBundleId, payload);
        statusMessage = `Bundle "${bundle.name}" updated (id: ${bundle.id})`;
      } else {
        // Create new bundle
        bundle = await createComposerBundle(payload);
        savedBundleId = bundle.id;
        statusMessage = `Bundle "${bundle.name}" created (id: ${bundle.id})`;
      }
      await loadBundles();
    } catch (e) {
      error.set(e.message);
    } finally {
      isSaving = false;
    }
  }

  async function handleLoadBundle() {
    if (!selectedBundleId) return;
    try {
      const bundle = await getComposerBundle(selectedBundleId);
      const comp = bundle.composition || {};
      selectedAgentCore = comp.agent_core_id || '';
      selectedArgPattern = comp.argumentation_pattern_id || '';
      selectedToneProfile = comp.tone_profile_id || '';
      selectedPromptModifier = comp.prompt_modifier_id || '';
      selectedLLMProfile = bundle.llm_profile_id || '';
      bundleName = bundle.name || '';
      bundleDescription = bundle.description || '';
      savedBundleId = bundle.id;
      statusMessage = `Loaded bundle "${bundle.name}" — editing`;
      previewPrompt = '';
    } catch (e) {
      error.set(e.message);
    }
  }

  async function handleExport() {
    if (!selectedBundleId && !savedBundleId) return;
    const id = selectedBundleId || savedBundleId;
    try {
      const result = await exportComposerBundle(id, true);
      statusMessage = `Bundle exported to ${result.path}`;
    } catch (e) {
      error.set(e.message);
    }
  }

  function handleNewBundle() {
    savedBundleId = null;
    bundleName = '';
    bundleDescription = '';
    selectedAgentCore = '';
    selectedArgPattern = '';
    selectedToneProfile = '';
    selectedPromptModifier = '';
    selectedLLMProfile = '';
    previewPrompt = '';
    statusMessage = '';
  }

  async function handleImport() {
    const moduleId = prompt('Enter module directory name (under modules/agent-bundles/):');
    if (!moduleId) return;
    try {
      const bundle = await importComposerBundle(moduleId);
      statusMessage = `Imported bundle "${bundle.name}" (id: ${bundle.id})`;
      await loadBundles();
    } catch (e) {
      error.set(e.message);
    }
  }
</script>

<div class="p-6 max-w-6xl mx-auto">
  <h1 class="text-2xl font-bold text-gray-800 dark:text-white mb-6">
    Bundle Composer
  </h1>

  {#if isLoading}
    <p class="text-gray-500 dark:text-gray-400">Loading components...</p>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="space-y-4">
        <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300">Components</h2>


        <div>
          <label class="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Agent Core</label>
          <select
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            bind:value={selectedAgentCore}
          >
            <option value="">-- Select Agent Core --</option>
            {#each agentCores as core}
              <option value={core.id}>{core.name} ({core.role})</option>
            {/each}
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Argumentation Pattern</label>
          <select
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            bind:value={selectedArgPattern}
          >
            <option value="">-- Select Argumentation Pattern --</option>
            {#each argPatterns as pattern}
              <option value={pattern.id}>{pattern.name}</option>
            {/each}
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Tone Profile</label>
          <select
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            bind:value={selectedToneProfile}
          >
            <option value="">-- Select Tone Profile --</option>
            {#each toneProfiles as profile}
              <option value={profile.id}>{profile.name}</option>
            {/each}
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Prompt Modifier</label>
          <select
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            bind:value={selectedPromptModifier}
          >
            <option value="">-- Select Prompt Modifier --</option>
            {#each promptModifiers as modifier}
              <option value={modifier.id}>{modifier.name}</option>
            {/each}
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">LLM Profile</label>
          <select
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            bind:value={selectedLLMProfile}
          >
            <option value="">-- Select LLM Profile --</option>
            {#each llmProfiles as profile}
              <option value={profile.id}>{profile.name} ({profile.provider})</option>
            {/each}
          </select>
        </div>

        <button
          class="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          onclick={handlePreview}
          disabled={isPreviewing}
        >
          {isPreviewing ? 'Assembling...' : 'Preview Prompt'}
        </button>

        <div class="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-md font-semibold text-gray-700 dark:text-gray-300">{savedBundleId ? 'Edit Bundle' : 'Save as Bundle'}</h3>
            {#if savedBundleId}
              <button
                class="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                onclick={handleNewBundle}
              >
                + New Bundle
              </button>
            {/if}
          </div>
          <input
            class="w-full px-3 py-2 mb-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            placeholder="Bundle name"
            bind:value={bundleName}
          />
          <textarea
            class="w-full px-3 py-2 mb-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            placeholder="Description (optional)"
            rows="2"
            bind:value={bundleDescription}
          ></textarea>
          <button
            class="w-full px-4 py-2 {savedBundleId ? 'bg-amber-600 hover:bg-amber-700 disabled:hover:bg-amber-600' : 'bg-green-600 hover:bg-green-700 disabled:hover:bg-green-600'} text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            onclick={handleSave}
            disabled={isSaving || !bundleName.trim()}
          >
            {isSaving ? 'Saving...' : savedBundleId ? 'Update Bundle' : 'Save Bundle'}
          </button>
        </div>
      </div>

      <div class="space-y-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">System Prompt Preview</h2>
          <pre
            class="w-full h-96 p-4 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-sm font-mono text-gray-800 dark:text-gray-200 overflow-auto whitespace-pre-wrap"
          >{previewPrompt || 'Select components and click Preview to assemble the prompt...'}</pre>
        </div>

        {#if statusMessage}
          <div class="p-3 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-lg text-sm">
            {statusMessage}
          </div>
        {/if}

        <div class="border-t border-gray-200 dark:border-gray-700 pt-4">
          <h3 class="text-md font-semibold text-gray-700 dark:text-gray-300 mb-3">Load Existing Bundle</h3>
          <select
            class="w-full px-3 py-2 mb-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-white text-sm"
            bind:value={selectedBundleId}
          >
            <option value="">-- Select Bundle --</option>
            {#each bundles as bundle}
              <option value={bundle.id}>{bundle.name}</option>
            {/each}
          </select>
          <div class="flex gap-2">
            <button
              class="flex-1 px-3 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:hover:bg-gray-600 disabled:opacity-50 text-sm font-medium"
              onclick={handleLoadBundle}
              disabled={!selectedBundleId}
            >
              Load
            </button>
            <button
              class="flex-1 px-3 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:hover:bg-amber-600 disabled:opacity-50 text-sm font-medium"
              onclick={handleExport}
              disabled={!selectedBundleId && !savedBundleId}
            >
              Export to Disk
            </button>
            <button
              class="flex-1 px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium"
              onclick={handleImport}
            >
              Import from Disk
            </button>
          </div>
        </div>

        <div class="border-t border-gray-200 dark:border-gray-700 pt-4">
          <h3 class="text-md font-semibold text-gray-700 dark:text-gray-300 mb-2">Saved Bundles ({bundles.length})</h3>
          {#if isLoadingBundles}
            <p class="text-sm text-gray-500 dark:text-gray-400">Loading...</p>
          {:else if bundles.length === 0}
            <p class="text-sm text-gray-500 dark:text-gray-400">No bundles yet. Create one above.</p>
          {:else}
            <ul class="space-y-1 max-h-48 overflow-y-auto">
              {#each bundles as bundle}
                <li
                  class="px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors
                    {selectedBundleId === bundle.id
                      ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'}"
                  onclick={() => { selectedBundleId = bundle.id; }}
                >
                  <span class="font-medium">{bundle.name}</span>
                  <span class="text-xs text-gray-400 ml-2">{bundle.id}</span>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>
