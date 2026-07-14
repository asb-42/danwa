<script>
  import { onMount } from 'svelte';
  import { error, selectedLLMProfile } from '../lib/stores.js';
  import { tStore } from '../lib/i18n/index.js';
  import {
    getLLMProfiles,
    deleteLLMProfile,
    estimateCost,
    reloadProfiles,
    getServiceEligibleProfiles,
    setServiceLLM,
  } from '../lib/api/profile.js';
  import { getServiceLLMConfig } from '../lib/api/settings.js';
  import ConfigModal from '../components/config/ConfigModal.svelte';
  import LlmProfileList from '../components/manage/LlmProfileList.svelte';

  let t = $derived($tStore);

  let llmProfiles = $state([]);
  let costEstimate = $state(null);
  let costNumAgents = $state(4);
  let costNumRounds = $state(3);
  let activeTab = $state('llm');
  let isLoading = $state(false);
  let statusMessage = $state('');

  // Service LLM state
  let serviceEligibleProfiles = $state([]);
  let serviceLLMConfig = $state({});
  let isLoadingServiceLLM = $state(false);

  // Modal state
  let showModal = $state(false);
  let modalMode = $state('create');
  let modalType = $state('llm');
  let formData = $state({});
  let formErrors = $state({});
  let showDeleteConfirm = $state(false);
  let deleteTarget = $state(null);

  onMount(async () => {
    error.set(null);
    isLoading = true;
    try {
      const results = await Promise.allSettled([
        getLLMProfiles(),
        getServiceEligibleProfiles(),
        getServiceLLMConfig(),
      ]);
      const errors = [];
      if (results[0].status === 'fulfilled') llmProfiles = results[0].value;
      else errors.push(`LLM Profiles: ${results[0].reason?.message || results[0].reason}`);
      if (results[1].status === 'fulfilled') serviceEligibleProfiles = results[1].value || [];
      if (results[2].status === 'fulfilled') serviceLLMConfig = results[2].value || {};
      if (errors.length > 0) error.set(errors.join('; '));
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoading = false;
    }
  });

  async function loadServiceLLMData() {
    isLoadingServiceLLM = true;
    try {
      const [eligible, config] = await Promise.all([
        getServiceEligibleProfiles(),
        getServiceLLMConfig(),
      ]);
      serviceEligibleProfiles = eligible || [];
      serviceLLMConfig = config || {};
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingServiceLLM = false;
    }
  }

  async function toggleServiceProfile(profileId, isChecked) {
    isLoadingServiceLLM = true;
    try {
      if (isChecked) {
        // Validate first
        const elig = serviceEligibleProfiles.find(p => p.id === profileId);
        if (elig && !elig.service_eligible) {
          error.set(`"${elig.name}" is not suitable as Utility LLM: ${elig.eligibility_reason}`);
          isLoadingServiceLLM = false;
          return;
        }
        await setServiceLLM(profileId);
        const prof = llmProfiles.find(p => p.id === profileId);
        statusMessage = `Utility LLM set to "${prof?.name || profileId}"`;
      } else {
        await setServiceLLM('');
        statusMessage = 'Utility LLM cleared';
      }
      await loadServiceLLMData();
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingServiceLLM = false;
    }
  }

  async function setServiceProfile(profileId) {
    isLoadingServiceLLM = true;
    try {
      await setServiceLLM(profileId);
      await loadServiceLLMData();
      statusMessage = t('service.setSuccess') || 'Utility LLM updated successfully';
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingServiceLLM = false;
    }
  }

  async function refreshLists() {
    const results = await Promise.allSettled([getLLMProfiles(), getServiceEligibleProfiles()]);
    if (results[0].status === 'fulfilled') llmProfiles = results[0].value;
    if (results[1].status === 'fulfilled') serviceEligibleProfiles = results[1].value || [];
  }

  function formatCost(cost) {
    if (cost === null || cost === undefined) return '—';
    return `$${cost.toFixed(4)}`;
  }

  function openDuplicateLLM(profile) {
    modalMode = 'create';
    modalType = 'llm';
    const ts = Date.now().toString(36).slice(-4);
    formData = {
      ...profile,
      id: `${profile.id}-copy-${ts}`,
      name: `${profile.name} (Kopie)`,
    };
    delete formData.created_at;
    delete formData.updated_at;
    formErrors = {};
    showModal = true;
  }

  function openCreateLLM() {
    modalMode = 'create';
    modalType = 'llm';
    formData = {
      id: '', name: '', profile_type: 'text', provider: 'openrouter', model: '',
      api_base: '', api_key_env: 'OPENROUTER_API_KEY', max_tokens: 4096,
      context_window: null, temperature: 0.7, timeout: 600,
      cost_per_1k_input: null, cost_per_1k_output: null,
    };
    formErrors = {};
    showModal = true;
  }

  function openEditLLM(profile) {
    modalMode = 'edit';
    modalType = 'llm';
    formData = { ...profile };
    formErrors = {};
    showModal = true;
  }

  function closeModal() {
    showModal = false;
    formErrors = {};
  }

  function handleModalSaved() {
    showModal = false;
    statusMessage = `✓ ${t('config.profileSaved')}`;
    refreshLists();
  }

  function confirmDelete(type, id, name) {
    deleteTarget = { type, id, name };
    showDeleteConfirm = true;
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.type === 'llm') await deleteLLMProfile(deleteTarget.id);
      showDeleteConfirm = false;
      deleteTarget = null;
      statusMessage = `✓ ${t('config.profileDeleted')}`;
      await refreshLists();
    } catch (e) { error.set(e.message); }
  }

  function closeDeleteConfirm() {
    showDeleteConfirm = false;
    deleteTarget = null;
  }

  async function handleEstimateCost() {
    try {
      costEstimate = await estimateCost($selectedLLMProfile, costNumAgents, costNumRounds);
    } catch (e) { error.set(e.message); }
  }

  async function handleReloadProfiles() {
    statusMessage = '';
    try {
      const result = await reloadProfiles();
      statusMessage = `✓ ${result.message} — ${result.llm_profiles} LLM, ${result.agent_personas} Agenten, ${result.prompt_variants} Prompts`;
      await refreshLists();
    } catch (e) { error.set(e.message); }
  }
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('manage.title') || 'Manage'}</h2>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">{$error}</div>
  {/if}

  {#if statusMessage}
    <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">{statusMessage}</div>
  {/if}

  <!-- Tab Navigation -->
  <div class="border-b border-gray-200 dark:border-gray-700">
    <nav class="flex space-x-4" aria-label="Manage tabs">
      {#each ['llm', 'cost'] as tab}
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
            {activeTab === tab
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
          onclick={() => { activeTab = tab; }}
        >
          {#if tab === 'llm'}{t('config.llmProfiles')}
          {:else if tab === 'cost'}{t('config.costEstimate')}
          {/if}
        </button>
      {/each}
    </nav>
  </div>

  {#if isLoading}
    <div class="flex items-center justify-center h-32">
      <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
    </div>

  <!-- LLM Profiles Tab -->
  {:else if activeTab === 'llm'}
    <LlmProfileList
      profiles={llmProfiles}
      selectedProfileId={$selectedLLMProfile}
      {serviceLLMConfig}
      {serviceEligibleProfiles}
      {isLoadingServiceLLM}
      onCreate={openCreateLLM}
      onEdit={openEditLLM}
      onDuplicate={openDuplicateLLM}
      onDelete={(id, name) => confirmDelete('llm', id, name)}
      onToggleService={toggleServiceProfile}
      onSelectProfile={(id) => selectedLLMProfile.set(id)}
    />

  <!-- Cost Estimation Tab -->
  {:else if activeTab === 'cost'}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('config.costEstimate')}</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label for="cost-llm" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.llmProfile')}</label>
          <select id="cost-llm" bind:value={$selectedLLMProfile} class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
            {#each llmProfiles as profile}
              <option value={profile.id}>{profile.name} ({profile.model})</option>
            {/each}
          </select>
        </div>
        <div>
          <label for="cost-agents" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.numAgents')}</label>
          <input id="cost-agents" type="number" bind:value={costNumAgents} min="1" max="10" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
        </div>
        <div>
          <label for="cost-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.numRounds')}</label>
          <input id="cost-rounds" type="number" bind:value={costNumRounds} min="1" max="20" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
        </div>
      </div>
      <button class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors" onclick={handleEstimateCost}>
        {t('config.estimateCost')}
      </button>
      {#if costEstimate}
        <div class="mt-4 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
          <p class="text-lg font-semibold text-gray-800 dark:text-white">
            {t('config.estimatedCost')}: <span class="text-blue-600 dark:text-blue-400">${costEstimate.estimated_cost_usd?.toFixed(4) || '0.0000'}</span>
          </p>
          <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {costEstimate.num_agents} agents × {costEstimate.num_rounds} rounds
          </p>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Current Selection Summary -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
    <h3 class="text-sm font-semibold text-gray-800 dark:text-white mb-2">{t('config.debateDefaults')}</h3>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
      <div>
        <span class="text-gray-500 dark:text-gray-400">{t('config.llmProfile')}:</span>
        <span class="ml-1 font-medium text-gray-800 dark:text-white">{llmProfiles.find(p => p.id === $selectedLLMProfile)?.name || $selectedLLMProfile}</span>
      </div>
    </div>
  </div>
</div>

<!-- Config Modal (LLM Profile / Agent Persona) -->
<ConfigModal visible={showModal} mode={modalMode} type={modalType} bind:formData bind:formErrors {llmProfiles} onClose={closeModal} onSaved={handleModalSaved} />

<!-- Delete Confirmation Dialog -->
{#if showDeleteConfirm && deleteTarget}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeDeleteConfirm} role="dialog" aria-modal="true" aria-labelledby="manage-delete-title" tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6" role="presentation" onclick={(e) => e.stopPropagation()}>
      <h3 id="manage-delete-title" class="text-lg font-semibold text-gray-800 dark:text-white mb-2">{t('config.deleteProfile')}</h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">{t('config.confirmDelete', { name: deleteTarget.name })}</p>
      <div class="flex items-center justify-end gap-3">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={closeDeleteConfirm}>{t('common.cancel')}</button>
        <button class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors" onclick={handleDelete}>{t('common.delete')}</button>
      </div>
    </div>
  </div>
{/if}
