<script>
  import { onMount } from 'svelte';
  import { loading, error, selectedLLMProfile, selectedPromptVariant, selectedPersonas } from '../lib/stores.js';
  import { i18n } from '../lib/i18n/index.js';
  import {
    getLLMProfiles,
    createLLMProfile,
    updateLLMProfile,
    deleteLLMProfile,
    getAgentPersonas,
    createAgentPersona,
    updateAgentPersona,
    deleteAgentPersona,
    getPromptVariants,
    createPromptVariant,
    deletePromptVariant,
    estimateCost,
    previewPromptVariant,
    reloadProfiles,
    getBackendLogs,
    getSettings,
    updateSettings,
  } from '../lib/api.js';
  import {
    listRoleTypes,
    createRoleType,
    updateRoleType,
    deleteRoleType,
  } from '../lib/blueprint/api.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  // --- Constants ---
  const PROMPT_ROLES = [
    { value: 'strategist', label: 'Strategist', emoji: '🧠' },
    { value: 'critic', label: 'Critic', emoji: '🔍' },
    { value: 'optimizer', label: 'Optimizer', emoji: '⚡' },
    { value: 'moderator', label: 'Moderator', emoji: '🎯' },
  ];

  // --- State ---
  let llmProfiles = $state([]);
  let agentPersonas = $state([]);
  let promptVariants = $state([]);
  let roleTypes = $state([]);
  let costEstimate = $state(null);
  let previewContent = $state(null);
  let previewRole = $state('strategist');
  let previewVariantId = $state(null);

  // Cost estimation inputs
  let costNumAgents = $state(4);
  let costNumRounds = $state(3);

  // Active tab
  let activeTab = $state('llm');

  let isLoading = $state(false);
  let statusMessage = $state('');

  // System tab state
  let isReloading = $state(false);
  let reloadResult = $state(null);
  let logLines = $state([]);
  let logSearch = $state('');
  let isLoadingLogs = $state(false);

  // Settings tab state
  let settingsData = $state({});
  let settingsLoaded = $state(false);
  let isLoadingSettings = $state(false);
  let isSavingSettings = $state(false);
  let settingsMessage = $state('');

  // --- Modal state ---
  let showModal = $state(false);
  let modalMode = $state('create'); // 'create' | 'edit'
  let modalType = $state('llm');    // 'llm' | 'agent'
  let formData = $state({});
  let formErrors = $state({});
  let isSaving = $state(false);

  // Delete confirmation
  let showDeleteConfirm = $state(false);
  let deleteTarget = $state(null); // { type: 'llm'|'agent'|'prompt'|'roleType', id, name }

  // Role Type form state
  let showRoleTypeModal = $state(false);
  let roleTypeModalMode = $state('create');
  let roleTypeFormData = $state({});
  let roleTypeFormErrors = $state({});
  let isSavingRoleType = $state(false);

  // --- Lifecycle ---
  onMount(async () => {
    $error = null;
    isLoading = true;
    try {
      const results = await Promise.allSettled([
        getLLMProfiles(),
        getAgentPersonas(),
        getPromptVariants(),
        listRoleTypes(),
      ]);

      const errors = [];
      if (results[0].status === 'fulfilled') {
        llmProfiles = results[0].value;
      } else {
        console.error('Failed to load LLM profiles:', results[0].reason);
        errors.push(`LLM Profiles: ${results[0].reason?.message || results[0].reason}`);
      }
      if (results[1].status === 'fulfilled') {
        agentPersonas = results[1].value;
      } else {
        console.error('Failed to load agent personas:', results[1].reason);
        errors.push(`Agent Personas: ${results[1].reason?.message || results[1].reason}`);
      }
      if (results[2].status === 'fulfilled') {
        promptVariants = results[2].value;
      } else {
        console.error('Failed to load prompt variants:', results[2].reason);
        errors.push(`Prompt Variants: ${results[2].reason?.message || results[2].reason}`);
      }
      if (results[3].status === 'fulfilled') {
        roleTypes = results[3].value;
      } else {
        console.error('Failed to load role types:', results[3].reason);
      }

      if (errors.length > 0) {
        $error = errors.join('; ');
      }
    } catch (e) {
      console.error('ConfigView load error:', e);
      $error = e.message;
    } finally {
      isLoading = false;
    }
  });

  // --- Actions ---
  async function handleEstimateCost() {
    try {
      costEstimate = await estimateCost($selectedLLMProfile, costNumAgents, costNumRounds);
    } catch (e) {
      $error = e.message;
    }
  }

  async function handlePreview(variantId, role) {
    try {
      const r = role || previewRole;
      const result = await previewPromptVariant(variantId, r);
      previewContent = result.content;
      previewVariantId = variantId;
      previewRole = r;
    } catch (e) {
      $error = e.message;
    }
  }

  // --- Prompt Variant Create ---
  let promptCreateData = $state({ id: '', name: '', description: '', prompts: {} });
  let promptCreateErrors = $state({});
  let isSavingPrompt = $state(false);
  let showPromptCreateModal = $state(false);

  function openCreatePrompt() {
    promptCreateData = { id: '', name: '', description: '', prompts: {} };
    promptCreateErrors = {};
    showPromptCreateModal = true;
  }

  function closePromptCreate() {
    showPromptCreateModal = false;
  }

  async function handleSavePromptVariant() {
    promptCreateErrors = {};
    if (!promptCreateData.id) promptCreateErrors.id = 'Required';
    if (!promptCreateData.name) promptCreateErrors.name = 'Required';
    if (Object.keys(promptCreateErrors).length > 0) return;

    isSavingPrompt = true;
    try {
      await createPromptVariant(promptCreateData);
      showPromptCreateModal = false;
      statusMessage = `✓ ${t('config.promptVariantSaved') || 'Prompt variant created'}`;
      await refreshLists();
    } catch (e) {
      $error = e.message;
    } finally {
      isSavingPrompt = false;
    }
  }

  async function handleReloadProfiles() {
    isReloading = true;
    statusMessage = '';
    try {
      reloadResult = await reloadProfiles();
      statusMessage = `✓ ${reloadResult.message} — ${reloadResult.llm_profiles} LLM, ${reloadResult.agent_personas} Agenten, ${reloadResult.prompt_variants} Prompts`;
      await refreshLists();
    } catch (e) {
      $error = e.message;
    } finally {
      isReloading = false;
    }
  }

  async function handleLoadLogs() {
    isLoadingLogs = true;
    try {
      const result = await getBackendLogs(200, logSearch || null);
      logLines = result.lines || [];
    } catch (e) {
      $error = e.message;
    } finally {
      isLoadingLogs = false;
    }
  }

  // --- Settings ---
  async function loadSettings() {
    isLoadingSettings = true;
    try {
      settingsData = await getSettings() || {};
      settingsLoaded = true;
    } catch (e) {
      $error = e.message;
    } finally {
      isLoadingSettings = false;
    }
  }

  async function handleSaveSettings() {
    isSavingSettings = true;
    settingsMessage = '';
    try {
      await updateSettings(settingsData);
      settingsMessage = `✓ ${t('settings.saved')}`;
    } catch (e) {
      $error = e.message;
    } finally {
      isSavingSettings = false;
    }
  }

  // Load settings when settings tab is activated
  $effect(() => {
    if (activeTab === 'settings' && !settingsLoaded) {
      loadSettings();
    }
  });

  async function refreshLists() {
    const results = await Promise.allSettled([getLLMProfiles(), getAgentPersonas(), getPromptVariants(), listRoleTypes()]);
    if (results[0].status === 'fulfilled') llmProfiles = results[0].value;
    if (results[1].status === 'fulfilled') agentPersonas = results[1].value;
    if (results[2].status === 'fulfilled') promptVariants = results[2].value;
    if (results[3].status === 'fulfilled') roleTypes = results[3].value;
  }

  function getPersonasByRole(role) {
    return agentPersonas.filter(p => p.role === role);
  }

  function formatCost(cost) {
    if (cost === null || cost === undefined) return '—';
    return `$${cost.toFixed(4)}`;
  }

  // --- Modal: LLM Profile ---
  function openCreateLLM() {
    modalMode = 'create';
    modalType = 'llm';
    formData = {
      id: '',
      name: '',
      provider: 'openrouter',
      model: '',
      api_base: '',
      api_key_env: 'OPENROUTER_API_KEY',
      max_tokens: 4096,
      context_window: null,
      temperature: 0.7,
      timeout: 600,
      cost_per_1k_input: null,
      cost_per_1k_output: null,
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

  // --- Modal: Agent Persona ---
  function openCreateAgent(role) {
    modalMode = 'create';
    modalType = 'agent';
    formData = {
      id: '',
      name: '',
      role: role,
      system_prompt: '',
      llm_profile_id: llmProfiles.length > 0 ? llmProfiles[0].id : '',
      max_rounds: 5,
      consensus_threshold: 0.9,
      description: '',
      tags: [],
    };
    formErrors = {};
    showModal = true;
  }

  function openEditAgent(persona) {
    modalMode = 'edit';
    modalType = 'agent';
    formData = { ...persona, tags: [...(persona.tags || [])] };
    formErrors = {};
    showModal = true;
  }

  // --- Form validation ---
  function validateForm() {
    const errors = {};
    if (modalType === 'llm') {
      if (!formData.id || !/^[a-z0-9][a-z0-9.-]*$/.test(formData.id)) {
        errors.id = 'ID: lowercase alphanumeric, dots, hyphens (e.g. my-profile)';
      }
      if (!formData.name?.trim()) errors.name = t('config.required');
      if (!formData.model?.trim()) errors.model = t('config.required');
      if (formData.temperature < 0 || formData.temperature > 2) errors.temperature = '0–2';
      if (formData.max_tokens < 1) errors.max_tokens = '≥ 1';
    } else {
      if (!formData.id || !/^[a-z0-9][a-z0-9.-]*$/.test(formData.id)) {
        errors.id = 'ID: lowercase alphanumeric, dots, hyphens';
      }
      if (!formData.name?.trim()) errors.name = t('config.required');
      if (!formData.system_prompt?.trim()) errors.system_prompt = t('config.required');
      if (!formData.llm_profile_id) errors.llm_profile_id = t('config.required');
      if (formData.consensus_threshold < 0 || formData.consensus_threshold > 1) errors.consensus_threshold = '0–1';
    }
    formErrors = errors;
    return Object.keys(errors).length === 0;
  }

  // --- Save ---
  async function handleSave() {
    if (!validateForm()) return;
    isSaving = true;
    try {
      if (modalType === 'llm') {
        const payload = { ...formData };
        // Clean empty optional fields
        if (!payload.api_base) payload.api_base = null;
        if (!payload.context_window) payload.context_window = null;
        if (!payload.cost_per_1k_input) payload.cost_per_1k_input = null;
        if (!payload.cost_per_1k_output) payload.cost_per_1k_output = null;

        if (modalMode === 'create') {
          await createLLMProfile(payload);
        } else {
          await updateLLMProfile(formData.id, payload);
        }
      } else {
        const payload = { ...formData };
        if (!payload.description) payload.description = null;

        if (modalMode === 'create') {
          await createAgentPersona(payload);
        } else {
          await updateAgentPersona(formData.id, payload);
        }
      }
      showModal = false;
      statusMessage = `✓ ${t('config.profileSaved')}`;
      await refreshLists();
    } catch (e) {
      $error = e.message;
    } finally {
      isSaving = false;
    }
  }

  // --- Delete ---
  function confirmDelete(type, id, name) {
    deleteTarget = { type, id, name };
    showDeleteConfirm = true;
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.type === 'llm') {
        await deleteLLMProfile(deleteTarget.id);
      } else if (deleteTarget.type === 'agent') {
        await deleteAgentPersona(deleteTarget.id);
      } else if (deleteTarget.type === 'prompt') {
        await deletePromptVariant(deleteTarget.id);
      } else if (deleteTarget.type === 'roleType') {
        await deleteRoleType(deleteTarget.id);
      }
      showDeleteConfirm = false;
      deleteTarget = null;
      statusMessage = `✓ ${t('config.profileDeleted')}`;
      await refreshLists();
    } catch (e) {
      $error = e.message;
    }
  }

  function closeModal() {
    showModal = false;
    formErrors = {};
  }

  function closeDeleteConfirm() {
    showDeleteConfirm = false;
    deleteTarget = null;
  }

  // Tags helper
  let tagInput = $state('');
  function addTag() {
    const tag = tagInput.trim().toLowerCase();
    if (tag && !formData.tags.includes(tag)) {
      formData.tags = [...formData.tags, tag];
    }
    tagInput = '';
  }
  function removeTag(tag) {
    formData.tags = formData.tags.filter(t => t !== tag);
  }

  // --- Role Type CRUD ---
  function openCreateRoleType() {
    roleTypeModalMode = 'create';
    roleTypeFormData = {
      id: '',
      name: '',
      description: '',
      color: '#6b7280',
      icon: '',
      active: true,
    };
    roleTypeFormErrors = {};
    showRoleTypeModal = true;
  }

  function openEditRoleType(roleType) {
    roleTypeModalMode = 'edit';
    roleTypeFormData = { ...roleType };
    roleTypeFormErrors = {};
    showRoleTypeModal = true;
  }

  function validateRoleTypeForm() {
    const errors = {};
    if (!roleTypeFormData.id || !/^[a-z0-9][a-z0-9._-]*$/.test(roleTypeFormData.id)) {
      errors.id = 'ID: lowercase alphanumeric, dots, hyphens';
    }
    if (!roleTypeFormData.name?.trim()) errors.name = t('config.required');
    roleTypeFormErrors = errors;
    return Object.keys(errors).length === 0;
  }

  async function handleSaveRoleType() {
    if (!validateRoleTypeForm()) return;
    isSavingRoleType = true;
    try {
      const payload = { ...roleTypeFormData };
      if (!payload.description) payload.description = null;
      if (!payload.icon) payload.icon = null;

      if (roleTypeModalMode === 'create') {
        await createRoleType(payload);
      } else {
        await updateRoleType(roleTypeFormData.id, payload);
      }
      showRoleTypeModal = false;
      statusMessage = `✓ ${t('config.roleTypeSaved')}`;
      roleTypes = await listRoleTypes();
    } catch (e) {
      $error = e.message;
    } finally {
      isSavingRoleType = false;
    }
  }

  function closeRoleTypeModal() {
    showRoleTypeModal = false;
    roleTypeFormErrors = {};
  }
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('config.title')}</h2>

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

  <!-- Tab Navigation -->
  <div class="border-b border-gray-200 dark:border-gray-700">
    <nav class="flex space-x-4" aria-label="Configuration tabs">
      {#each ['llm', 'agents', 'roleTypes', 'prompts', 'cost', 'settings', 'system'] as tab}
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
            {activeTab === tab
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
          onclick={() => { activeTab = tab; previewContent = null; }}
        >
          {#if tab === 'llm'}{t('config.llmProfiles')}
          {:else if tab === 'agents'}{t('config.agentProfiles')}
          {:else if tab === 'roleTypes'}🎭 {t('config.roleTypes')}
          {:else if tab === 'prompts'}{t('config.promptVariants')}
          {:else if tab === 'cost'}{t('config.costEstimate')}
          {:else if tab === 'settings'}⚙️ {t('settings.title')}
          {:else if tab === 'system'}🖥️ System
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
    <div class="space-y-4">
      <div class="flex justify-end">
        <button
          class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
          onclick={openCreateLLM}
        >
          + {t('config.createLLM')}
        </button>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        {#if llmProfiles.length === 0}
          <div class="flex items-center justify-center h-32">
            <p class="text-gray-500 dark:text-gray-400">{t('config.llmProfilesPlaceholder')}</p>
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm text-left">
              <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th class="px-4 py-3">ID</th>
                  <th class="px-4 py-3">{t('config.provider')}</th>
                  <th class="px-4 py-3">{t('config.model')}</th>
                  <th class="px-4 py-3">{t('config.temperature')}</th>
                  <th class="px-4 py-3">{t('config.maxTokens')}</th>
                  <th class="px-4 py-3">{t('config.contextWindow')}</th>
                  <th class="px-4 py-3">{t('config.costInput')}</th>
                  <th class="px-4 py-3">{t('config.costOutput')}</th>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each llmProfiles as profile}
                  <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50
                    {$selectedLLMProfile === profile.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}">
                    <td class="px-4 py-3 font-medium">
                      <button
                        class="text-blue-600 dark:text-blue-400 hover:underline"
                        onclick={() => { $selectedLLMProfile = profile.id; }}
                      >
                        {profile.id}
                      </button>
                      {#if $selectedLLMProfile === profile.id}
                        <span class="ml-2 text-xs text-green-600 dark:text-green-400">✓ {t('config.active')}</span>
                      {/if}
                    </td>
                    <td class="px-4 py-3">{profile.provider}</td>
                    <td class="px-4 py-3 font-mono text-xs">{profile.model}</td>
                    <td class="px-4 py-3">{profile.temperature}</td>
                    <td class="px-4 py-3">{profile.max_tokens}</td>
                    <td class="px-4 py-3">{profile.context_window ?? '—'}</td>
                    <td class="px-4 py-3">{formatCost(profile.cost_per_1k_input)}</td>
                    <td class="px-4 py-3">{formatCost(profile.cost_per_1k_output)}</td>
                    <td class="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        class="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                        onclick={() => openEditLLM(profile)}
                      >
                        {t('common.edit')}
                      </button>
                      <button
                        class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors ml-1"
                        onclick={() => confirmDelete('llm', profile.id, profile.name)}
                      >
                        {t('common.delete')}
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

  <!-- Agent Personas Tab -->
  {:else if activeTab === 'agents'}
    <div class="space-y-4">
      {#each ['strategist', 'critic', 'optimizer', 'moderator'] as role}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-md font-semibold text-gray-800 dark:text-white capitalize">
              {t(`agent.${role}`)}
            </h4>
            <button
              class="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              onclick={() => openCreateAgent(role)}
            >
              + {t('config.createPersona')}
            </button>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {#each getPersonasByRole(role) as persona}
              <div
                class="p-3 rounded-lg border transition-colors relative
                  {$selectedPersonas[role] === persona.id
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'}"
              >
                <!-- Select area -->
                <div
                  class="cursor-pointer"
                  onclick={() => { $selectedPersonas = { ...$selectedPersonas, [role]: persona.id }; }}
                  onkeydown={(e) => { if (e.key === 'Enter') $selectedPersonas = { ...$selectedPersonas, [role]: persona.id }; }}
                  role="button"
                  tabindex="0"
                >
                  <div class="flex items-center justify-between mb-1">
                    <span class="font-medium text-sm text-gray-800 dark:text-white">{persona.name}</span>
                    {#if $selectedPersonas[role] === persona.id}
                      <span class="text-xs text-green-600 dark:text-green-400">✓</span>
                    {/if}
                  </div>
                  {#if persona.description}
                    <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{persona.description}</p>
                  {/if}
                  <div class="flex flex-wrap gap-1">
                    {#each persona.tags as tag}
                      <span class="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">
                        {tag}
                      </span>
                    {/each}
                  </div>
                </div>

                <!-- Action buttons -->
                <div class="flex gap-1 mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                  <button
                    class="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                    onclick={() => openEditAgent(persona)}
                  >
                    {t('common.edit')}
                  </button>
                  <button
                    class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                    onclick={() => confirmDelete('agent', persona.id, persona.name)}
                  >
                    {t('common.delete')}
                  </button>
                </div>
              </div>
            {:else}
              <p class="text-sm text-gray-500 dark:text-gray-400 col-span-full">
                {t('config.noProfiles')}
              </p>
            {/each}
          </div>
        </div>
      {/each}
    </div>

  <!-- Role Types Tab -->
  {:else if activeTab === 'roleTypes'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button
          class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
          onclick={openCreateRoleType}
        >
          + {t('config.createRoleType')}
        </button>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        {#if roleTypes.length === 0}
          <div class="flex items-center justify-center h-32">
            <p class="text-gray-500 dark:text-gray-400">{t('config.noRoleTypes')}</p>
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm text-left">
              <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th class="px-4 py-3">ID</th>
                  <th class="px-4 py-3">{t('config.name')}</th>
                  <th class="px-4 py-3">{t('config.description')}</th>
                  <th class="px-4 py-3">{t('config.roleTypeColor')}</th>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each roleTypes as rt}
                  <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td class="px-4 py-3 font-mono text-xs">{rt.id}</td>
                    <td class="px-4 py-3 font-medium">{rt.name}</td>
                    <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{rt.description || '—'}</td>
                    <td class="px-4 py-3">
                      <span class="inline-block w-4 h-4 rounded-full" style="background: {rt.color || '#6b7280'}"></span>
                    </td>
                    <td class="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        class="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                        onclick={() => openEditRoleType(rt)}
                      >
                        {t('common.edit')}
                      </button>
                      <button
                        class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors ml-1"
                        onclick={() => confirmDelete('roleType', rt.id, rt.name)}
                      >
                        {t('common.delete')}
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

  <!-- Prompt Variants Tab -->
  {:else if activeTab === 'prompts'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button
          class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
          onclick={openCreatePrompt}
        >
          + {t('config.createPromptVariant') || 'Create Prompt Variant'}
        </button>
      </div>

      <!-- Each variant as a section with role-based tiles -->
      {#each promptVariants as variant}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <h4 class="text-md font-semibold text-gray-800 dark:text-white">
                {variant.name || variant.id}
              </h4>
              {#if $selectedPromptVariant === variant.id}
                <span class="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full">✓ {t('config.active')}</span>
              {/if}
            </div>
            <div class="flex items-center gap-2">
              <button
                class="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-800/40 transition-colors"
                onclick={() => { $selectedPromptVariant = variant.id; }}
              >
                {$selectedPromptVariant === variant.id ? t('config.active') : t('config.select') || 'Select'}
              </button>
              {#if variant.id !== 'default'}
                <button
                  class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                  onclick={() => confirmDelete('prompt', variant.id, variant.id)}
                >
                  {t('common.delete')}
                </button>
              {/if}
            </div>
          </div>
          {#if variant.description}
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">{variant.description}</p>
          {/if}

          <!-- Role-based prompt tiles -->
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {#each PROMPT_ROLES as role}
              <div class="p-3 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 transition-colors">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm font-medium text-gray-800 dark:text-white capitalize">{role.emoji} {role.label}</span>
                  <button
                    class="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    onclick={() => handlePreview(variant.id, role.value)}
                  >
                    {t('config.preview')}
                  </button>
                </div>
                {#if previewContent && previewVariantId === variant.id && previewRole === role.value}
                  <pre class="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 p-2 rounded overflow-x-auto max-h-32 whitespace-pre-wrap">{previewContent}</pre>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
          <div class="flex items-center justify-center h-32">
            <p class="text-gray-500 dark:text-gray-400">{t('config.promptVariantsPlaceholder')}</p>
          </div>
        </div>
      {/each}
    </div>

  <!-- Cost Estimation Tab -->
  {:else if activeTab === 'cost'}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('config.costEstimate')}</h3>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label for="cost-llm" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.llmProfile')}
          </label>
          <select
            id="cost-llm"
            bind:value={$selectedLLMProfile}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            {#each llmProfiles as profile}
              <option value={profile.id}>{profile.name} ({profile.model})</option>
            {/each}
          </select>
        </div>

        <div>
          <label for="cost-agents" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.numAgents')}
          </label>
          <input
            id="cost-agents"
            type="number"
            bind:value={costNumAgents}
            min="1"
            max="10"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          />
        </div>

        <div>
          <label for="cost-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.numRounds')}
          </label>
          <input
            id="cost-rounds"
            type="number"
            bind:value={costNumRounds}
            min="1"
            max="20"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          />
        </div>
      </div>

      <button
        class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        onclick={handleEstimateCost}
      >
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

  <!-- Settings Tab -->
  {:else if activeTab === 'settings'}
    <div class="space-y-4">
      {#if isLoadingSettings}
        <div class="flex items-center justify-center h-32">
          <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
        </div>
      {:else if settingsLoaded}
        {#if settingsMessage}
          <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
            {settingsMessage}
          </div>
        {/if}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 space-y-6">
          <!-- Search Mode -->
          <div>
            <label for="settings-search-mode" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('settings.searchMode')}
            </label>
            <select
              id="settings-search-mode"
              value={settingsData.search_mode || 'off'}
              onchange={(e) => settingsData = { ...settingsData, search_mode: e.target.value }}
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="off">{t('debate.searchOff')}</option>
              <option value="optional">{t('debate.searchOptional')}</option>
              <option value="required">{t('debate.searchRequired')}</option>
            </select>
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{t('settings.searchModeHint')}</p>
          </div>

          <!-- Privacy -->
          <div>
            <label class="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settingsData.privacy_mode || false}
                onchange={(e) => settingsData = { ...settingsData, privacy_mode: e.target.checked }}
                class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{t('settings.privacy')}</span>
                <p class="text-xs text-gray-500 dark:text-gray-400">{t('settings.privacyHint')}</p>
              </div>
            </label>
          </div>

          <!-- Data Retention -->
          <div>
            <label for="settings-retention" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('settings.retention')}
            </label>
            <input
              id="settings-retention"
              type="number"
              value={settingsData.retention_days ?? 0}
              oninput={(e) => settingsData = { ...settingsData, retention_days: parseInt(e.target.value) || 0 }}
              min="0"
              max="3650"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{t('settings.retentionHint')}</p>
          </div>

          <div class="flex justify-end pt-2">
            <button
              class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700
                     transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              onclick={handleSaveSettings}
              disabled={isSavingSettings}
            >
              {isSavingSettings ? '...' : t('common.save')}
            </button>
          </div>
        </div>
      {/if}
      {#if !settingsLoaded && !isLoadingSettings}
        <div class="flex items-center justify-center h-32">
          <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
        </div>
      {/if}
    </div>

  <!-- System Tab -->
  {:else if activeTab === 'system'}
    <div class="space-y-4">
      <!-- Reload Profiles -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Profile neu laden</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Liest alle YAML-Profile und Prompt-Templates neu von der Festplatte, ohne das Backend neu starten zu müssen.
        </p>
        <button
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleReloadProfiles}
          disabled={isReloading}
        >
          {isReloading ? 'Lade...' : '🔄 Profile neu laden'}
        </button>
        {#if reloadResult}
          <div class="mt-3 text-sm text-gray-600 dark:text-gray-300">
            <p>LLM-Profile: {reloadResult.llm_profiles} | Agenten: {reloadResult.agent_personas} | Prompts: {reloadResult.prompt_variants}</p>
          </div>
        {/if}
      </div>

      <!-- Frontend Reload -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Frontend neu laden</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Lädt die Seite neu (gleich wie Browser-Refresh / F5).
        </p>
        <button
          class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          onclick={() => location.reload()}
        >
          🔄 Seite neu laden
        </button>
      </div>

      <!-- Backend Logs -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Backend-Logs</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Zeigt die letzten Log-Einträge des Backends (mit Timestamps).
        </p>
        <div class="flex gap-2 mb-4">
          <input
            type="text"
            bind:value={logSearch}
            placeholder="Filter (z.B. ERROR, agent, LLM)..."
            class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            onkeydown={(e) => { if (e.key === 'Enter') handleLoadLogs(); }}
          />
          <button
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors
                   disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            onclick={handleLoadLogs}
            disabled={isLoadingLogs}
          >
            {isLoadingLogs ? 'Lade...' : '📋 Logs laden'}
          </button>
        </div>
        {#if logLines.length > 0}
          <div class="bg-gray-900 rounded-lg p-4 overflow-auto max-h-96">
            <pre class="text-xs text-green-400 font-mono whitespace-pre-wrap">{logLines.join('\n')}</pre>
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">{logLines.length} Zeilen</p>
        {:else if !isLoadingLogs}
          <p class="text-sm text-gray-500 dark:text-gray-400">Noch keine Logs geladen. Klicke auf "Logs laden".</p>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Current Selection Summary -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
    <h3 class="text-sm font-semibold text-gray-800 dark:text-white mb-2">{t('config.debateDefaults')}</h3>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
      <div>
        <span class="text-gray-500 dark:text-gray-400">{t('config.llmProfile')}:</span>
        <span class="ml-1 font-medium text-gray-800 dark:text-white">{$selectedLLMProfile}</span>
      </div>
      <div>
        <span class="text-gray-500 dark:text-gray-400">{t('config.promptVariants')}:</span>
        <span class="ml-1 font-medium text-gray-800 dark:text-white">{$selectedPromptVariant}</span>
      </div>
      {#each Object.entries($selectedPersonas) as [role, personaId]}
        <div>
          <span class="text-gray-500 dark:text-gray-400 capitalize">{role}:</span>
          <span class="ml-1 font-medium text-gray-800 dark:text-white">{personaId}</span>
        </div>
      {/each}
    </div>
  </div>
</div>

<!-- ============================================================ -->
<!-- MODAL: Create / Edit LLM Profile or Agent Persona            -->
<!-- ============================================================ -->
{#if showModal}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeModal} role="dialog" aria-modal="true" tabindex="-1">
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto mx-4"
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {#if modalType === 'llm'}
            {modalMode === 'create' ? t('config.createLLM') : t('config.editLLM')}
          {:else}
            {modalMode === 'create' ? t('config.createPersona') : t('config.editPersona')}
          {/if}
        </h3>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none"
          onclick={closeModal}
        >
          ✕
        </button>
      </div>

      <!-- Form -->
      <div class="px-6 py-4 space-y-4">
        {#if modalType === 'llm'}
          <!-- LLM Profile Form -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- ID -->
            <div>
              <label for="form-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.id')} *
              </label>
              <input id="form-id" type="text" bind:value={formData.id}
                disabled={modalMode === 'edit'}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                  disabled:bg-gray-100 dark:disabled:bg-gray-600 disabled:cursor-not-allowed"
                placeholder="my-llm-profile"
              />
              {#if formErrors.id}<p class="text-xs text-red-500 mt-1">{formErrors.id}</p>{/if}
            </div>

            <!-- Name -->
            <div>
              <label for="form-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.name')} *
              </label>
              <input id="form-name" type="text" bind:value={formData.name}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="My LLM Profile"
              />
              {#if formErrors.name}<p class="text-xs text-red-500 mt-1">{formErrors.name}</p>{/if}
            </div>

            <!-- Provider -->
            <div>
              <label for="form-provider" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.provider')} *
              </label>
              <select id="form-provider" bind:value={formData.provider}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                <option value="openrouter">OpenRouter</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="ollama">Ollama</option>
                <option value="opencode-zen">Opencode Zen</option>
                <option value="opencode-go">Opencode Go</option>
                <option value="xiaomi">Xiaomi</option>
                <option value="local">Local</option>
              </select>
            </div>

            <!-- Model -->
            <div>
              <label for="form-model" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.model')} *
              </label>
              <input id="form-model" type="text" bind:value={formData.model}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.model ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="anthropic/claude-3.5-sonnet"
              />
              {#if formErrors.model}<p class="text-xs text-red-500 mt-1">{formErrors.model}</p>{/if}
            </div>

            <!-- API Base -->
            <div>
              <label for="form-apibase" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.apiBase')}
              </label>
              <input id="form-apibase" type="text" bind:value={formData.api_base}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="http://localhost:11434/v1"
              />
            </div>

            <!-- API Key Env -->
            <div>
              <label for="form-apikey" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.apiKeyEnv')}
              </label>
              <input id="form-apikey" type="text" bind:value={formData.api_key_env}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="OPENROUTER_API_KEY"
              />
            </div>

            <!-- Temperature -->
            <div>
              <label for="form-temp" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.temperature')} *
              </label>
              <input id="form-temp" type="number" bind:value={formData.temperature}
                min="0" max="2" step="0.1"
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.temperature ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              {#if formErrors.temperature}<p class="text-xs text-red-500 mt-1">{formErrors.temperature}</p>{/if}
            </div>

            <!-- Max Tokens -->
            <div>
              <label for="form-maxtok" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.maxTokens')} *
              </label>
              <input id="form-maxtok" type="number" bind:value={formData.max_tokens}
                min="1" step="256"
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.max_tokens ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              {#if formErrors.max_tokens}<p class="text-xs text-red-500 mt-1">{formErrors.max_tokens}</p>{/if}
            </div>

            <!-- Context Window -->
            <div>
              <label for="form-ctx" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.contextWindow')}
              </label>
              <input id="form-ctx" type="number" bind:value={formData.context_window}
                min="0" step="1024"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="200000"
              />
            </div>

            <!-- Timeout -->
            <div>
              <label for="form-timeout" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.timeout')}
              </label>
              <input id="form-timeout" type="number" bind:value={formData.timeout}
                min="1" step="30"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            <!-- Cost Input -->
            <div>
              <label for="form-costin" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.costInput')} (USD/1k)
              </label>
              <input id="form-costin" type="number" bind:value={formData.cost_per_1k_input}
                min="0" step="0.0001"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="0.003"
              />
            </div>

            <!-- Cost Output -->
            <div>
              <label for="form-costout" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.costOutput')} (USD/1k)
              </label>
              <input id="form-costout" type="number" bind:value={formData.cost_per_1k_output}
                min="0" step="0.0001"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="0.015"
              />
            </div>
          </div>

        {:else}
          <!-- Agent Persona Form -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- ID -->
            <div>
              <label for="form-agent-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.id')} *
              </label>
              <input id="form-agent-id" type="text" bind:value={formData.id}
                disabled={modalMode === 'edit'}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                  disabled:bg-gray-100 dark:disabled:bg-gray-600 disabled:cursor-not-allowed"
                placeholder="my-strategist"
              />
              {#if formErrors.id}<p class="text-xs text-red-500 mt-1">{formErrors.id}</p>{/if}
            </div>

            <!-- Name -->
            <div>
              <label for="form-agent-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.name')} *
              </label>
              <input id="form-agent-name" type="text" bind:value={formData.name}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="My Strategist"
              />
              {#if formErrors.name}<p class="text-xs text-red-500 mt-1">{formErrors.name}</p>{/if}
            </div>

            <!-- Role -->
            <div>
              <label for="form-agent-role" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.role')} *
              </label>
              <select id="form-agent-role" bind:value={formData.role}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                <option value="strategist">Strategist</option>
                <option value="critic">Critic</option>
                <option value="optimizer">Optimizer</option>
                <option value="moderator">Moderator</option>
              </select>
            </div>

            <!-- LLM Profile Ref -->
            <div>
              <label for="form-agent-llm" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.llmProfileRef')} *
              </label>
              <select id="form-agent-llm" bind:value={formData.llm_profile_id}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.llm_profile_id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                {#each llmProfiles as p}
                  <option value={p.id}>{p.name} ({p.model})</option>
                {/each}
              </select>
              {#if formErrors.llm_profile_id}<p class="text-xs text-red-500 mt-1">{formErrors.llm_profile_id}</p>{/if}
            </div>

            <!-- Max Rounds -->
            <div>
              <label for="form-agent-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.maxRounds')}
              </label>
              <input id="form-agent-rounds" type="number" bind:value={formData.max_rounds}
                min="1" max="20"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            <!-- Consensus Threshold -->
            <div>
              <label for="form-agent-threshold" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.consensusThreshold')}
              </label>
              <input id="form-agent-threshold" type="number" bind:value={formData.consensus_threshold}
                min="0" max="1" step="0.05"
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.consensus_threshold ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              {#if formErrors.consensus_threshold}<p class="text-xs text-red-500 mt-1">{formErrors.consensus_threshold}</p>{/if}
            </div>

            <!-- Description -->
            <div class="md:col-span-2">
              <label for="form-agent-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.description')}
              </label>
              <input id="form-agent-desc" type="text" bind:value={formData.description}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="Short description of this persona"
              />
            </div>

            <!-- Tags -->
            <div class="md:col-span-2">
              <label for="form-agent-tags" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.tags')}
              </label>
              <div class="flex gap-2 mb-2 flex-wrap">
                {#each formData.tags as tag}
                  <span class="inline-flex items-center gap-1 text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                    {tag}
                    <button class="text-gray-400 hover:text-red-500" onclick={() => removeTag(tag)}>✕</button>
                  </span>
                {/each}
              </div>
              <div class="flex gap-2">
                <input id="form-agent-tags" type="text" bind:value={tagInput}
                  class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="Add tag and press Enter"
                  onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                />
                <button
                  class="px-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
                  onclick={addTag}
                >
                  +
                </button>
              </div>
            </div>

            <!-- System Prompt -->
            <div class="md:col-span-2">
              <label for="form-agent-prompt" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.systemPrompt')} *
              </label>
              <textarea id="form-agent-prompt" bind:value={formData.system_prompt}
                rows="6"
                class="w-full px-3 py-2 border rounded-lg text-sm font-mono resize-y
                  {formErrors.system_prompt ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="You are a strategic analyst..."
              ></textarea>
              {#if formErrors.system_prompt}<p class="text-xs text-red-500 mt-1">{formErrors.system_prompt}</p>{/if}
            </div>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={closeModal}
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
  </div>
{/if}

<!-- ============================================================ -->
<!-- DELETE CONFIRMATION DIALOG                                    -->
<!-- ============================================================ -->
{#if showDeleteConfirm && deleteTarget}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeDeleteConfirm} role="dialog" aria-modal="true" tabindex="-1">
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6"
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    >
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
        {t('config.deleteProfile')}
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">
        {t('config.confirmDelete', { name: deleteTarget.name })}
      </p>
      <div class="flex items-center justify-end gap-3">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={closeDeleteConfirm}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
          onclick={handleDelete}
        >
          {t('common.delete')}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ============================================================ -->
<!-- ROLE TYPE MODAL                                                -->
<!-- ============================================================ -->
{#if showRoleTypeModal}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeRoleTypeModal} role="dialog" aria-modal="true" tabindex="-1">
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto mx-4"
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {roleTypeModalMode === 'create' ? t('config.createRoleType') : t('config.editRoleType')}
        </h3>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none"
          onclick={closeRoleTypeModal}
        >
          ✕
        </button>
      </div>

      <!-- Form -->
      <div class="px-6 py-4 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- ID -->
          <div>
            <label for="rt-form-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('config.id')} *
            </label>
            <input id="rt-form-id" type="text" bind:value={roleTypeFormData.id}
              disabled={roleTypeModalMode === 'edit'}
              class="w-full px-3 py-2 border rounded-lg text-sm
                {roleTypeFormErrors.id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                disabled:bg-gray-100 dark:disabled:bg-gray-600 disabled:cursor-not-allowed"
              placeholder="custom-role"
            />
            {#if roleTypeFormErrors.id}<p class="text-xs text-red-500 mt-1">{roleTypeFormErrors.id}</p>{/if}
          </div>

          <!-- Name -->
          <div>
            <label for="rt-form-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('config.name')} *
            </label>
            <input id="rt-form-name" type="text" bind:value={roleTypeFormData.name}
              class="w-full px-3 py-2 border rounded-lg text-sm
                {roleTypeFormErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="Custom Role"
            />
            {#if roleTypeFormErrors.name}<p class="text-xs text-red-500 mt-1">{roleTypeFormErrors.name}</p>{/if}
          </div>

          <!-- Color -->
          <div>
            <label for="rt-form-color" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('config.roleTypeColor')}
            </label>
            <input id="rt-form-color" type="color" bind:value={roleTypeFormData.color}
              class="w-full h-10 px-1 py-1 border border-gray-300 dark:border-gray-600 rounded-lg"
            />
          </div>

          <!-- Icon -->
          <div>
            <label for="rt-form-icon" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('config.roleTypeIcon')}
            </label>
            <input id="rt-form-icon" type="text" bind:value={roleTypeFormData.icon}
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="🔍"
            />
          </div>

          <!-- Description -->
          <div class="md:col-span-2">
            <label for="rt-form-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('config.description')}
            </label>
            <input id="rt-form-desc" type="text" bind:value={roleTypeFormData.description}
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              placeholder="Description of this role type"
            />
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={closeRoleTypeModal}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleSaveRoleType}
          disabled={isSavingRoleType}
        >
          {isSavingRoleType ? '...' : t('common.save')}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ============================================================ -->
<!-- Create Prompt Variant Modal -->
<!-- ============================================================ -->
{#if showPromptCreateModal}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={closePromptCreate}>
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions a11y_interactive_supports_focus -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto" onclick={(e) => e.stopPropagation()}>
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {t('config.createPromptVariant') || 'Create Prompt Variant'}
        </h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" onclick={closePromptCreate}>✕</button>
      </div>

      <!-- Body -->
      <div class="p-6 space-y-4">
        <!-- ID -->
        <div>
          <label for="pv-form-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            ID *
          </label>
          <input id="pv-form-id" type="text" bind:value={promptCreateData.id}
            class="w-full px-3 py-2 border rounded-lg text-sm
              {promptCreateErrors.id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
              bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            placeholder="my-custom-variant"
          />
          {#if promptCreateErrors.id}<p class="text-xs text-red-500 mt-1">{promptCreateErrors.id}</p>{/if}
        </div>

        <!-- Name -->
        <div>
          <label for="pv-form-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.name')} *
          </label>
          <input id="pv-form-name" type="text" bind:value={promptCreateData.name}
            class="w-full px-3 py-2 border rounded-lg text-sm
              {promptCreateErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
              bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            placeholder="My Custom Variant"
          />
          {#if promptCreateErrors.name}<p class="text-xs text-red-500 mt-1">{promptCreateErrors.name}</p>{/if}
        </div>

        <!-- Description -->
        <div>
          <label for="pv-form-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.description')}
          </label>
          <input id="pv-form-desc" type="text" bind:value={promptCreateData.description}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            placeholder="Description of this prompt variant"
          />
        </div>

        <!-- Per-role prompts -->
        <div>
          <p class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Prompts per Role
          </p>
          <div class="space-y-3">
            {#each PROMPT_ROLES as role}
              <div>
                <label for="pv-prompt-{role.value}" class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                  {role.emoji} {role.label}
                </label>
                <textarea
                  id="pv-prompt-{role.value}"
                  value={promptCreateData.prompts[role.value] || ''}
                  oninput={(e) => {
                    promptCreateData = {
                      ...promptCreateData,
                      prompts: { ...promptCreateData.prompts, [role.value]: e.target.value }
                    };
                  }}
                  rows="4"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono"
                  placeholder="System prompt for {role.label}..."
                ></textarea>
              </div>
            {/each}
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={closePromptCreate}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleSavePromptVariant}
          disabled={isSavingPrompt}
        >
          {isSavingPrompt ? '...' : t('common.save')}
        </button>
      </div>
    </div>
  </div>
{/if}
