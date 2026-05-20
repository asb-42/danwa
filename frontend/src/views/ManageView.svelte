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
    translatePromptVariant,
    estimateCost,
    previewPromptVariant,
    reloadProfiles,
    getServiceEligibleProfiles,
    getServiceLLMConfig,
    setServiceLLM,
  } from '../lib/api.js';
  import {
    listRoleTypes,
    createRoleType,
    updateRoleType,
    deleteRoleType,
    listRoleDefinitions,
  } from '../lib/blueprint/api.js';
  import ConfigModal from '../components/config/ConfigModal.svelte';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const PROMPT_ROLES = [
    { value: 'strategist', label: 'Strategist', emoji: '🧠' },
    { value: 'critic', label: 'Critic', emoji: '🔍' },
    { value: 'optimizer', label: 'Optimizer', emoji: '⚡' },
    { value: 'moderator', label: 'Moderator', emoji: '🎯' },
  ];

  let llmProfiles = $state([]);
  let agentPersonas = $state([]);
  let promptVariants = $state([]);
  let roleTypes = $state([]);
  let blueprintRoleDefIds = $state(new Set());
  let costEstimate = $state(null);
  let previewContent = $state(null);
  let previewRole = $state('strategist');
  let previewVariantId = $state(null);
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

  // LLM search / filter / sort
  let llmSearch = $state('');
  let llmDropdownOpen = $state(null);

  // Role Type modal state
  let showRoleTypeModal = $state(false);
  let roleTypeModalMode = $state('create');
  let roleTypeFormData = $state({});
  let roleTypeFormErrors = $state({});
  let isSavingRoleType = $state(false);

  // Prompt create modal state
  let promptCreateData = $state({ id: '', name: '', description: '', prompts: {} });
  let promptCreateErrors = $state({});
  let isSavingPrompt = $state(false);
  let showPromptCreateModal = $state(false);

  // Prompt translation modal state
  let showPromptTranslateModal = $state(false);
  let promptTranslateVariantId = $state('');
  let promptTranslateTargetLang = $state('de');
  let promptTranslateResult = $state(null);
  let isTranslatingPrompt = $state(false);

  onMount(async () => {
    error.set(null);
    isLoading = true;
    try {
      const results = await Promise.allSettled([
        getLLMProfiles(),
        getAgentPersonas(),
        getPromptVariants(),
        listRoleTypes(),
        getServiceEligibleProfiles(),
        getServiceLLMConfig(),
      ]);
      const errors = [];
      if (results[0].status === 'fulfilled') llmProfiles = results[0].value;
      else errors.push(`LLM Profiles: ${results[0].reason?.message || results[0].reason}`);
      if (results[1].status === 'fulfilled') agentPersonas = results[1].value;
      else errors.push(`Agent Personas: ${results[1].reason?.message || results[1].reason}`);
      if (results[2].status === 'fulfilled') promptVariants = results[2].value;
      else errors.push(`Prompt Variants: ${results[2].reason?.message || results[2].reason}`);
      if (results[3].status === 'fulfilled') roleTypes = results[3].value;
      if (results[4].status === 'fulfilled') serviceEligibleProfiles = results[4].value || [];
      if (results[5].status === 'fulfilled') serviceLLMConfig = results[5].value || {};
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
    const results = await Promise.allSettled([getLLMProfiles(), getAgentPersonas(), getPromptVariants(), listRoleTypes(), listRoleDefinitions()]);
    if (results[0].status === 'fulfilled') llmProfiles = results[0].value;
    if (results[1].status === 'fulfilled') agentPersonas = results[1].value;
    if (results[2].status === 'fulfilled') promptVariants = results[2].value;
    if (results[3].status === 'fulfilled') roleTypes = results[3].value;
    if (results[4].status === 'fulfilled') blueprintRoleDefIds = new Set(results[4].value.map(rd => rd.id));
  }

  function isBlueprintManaged(personaId) {
    return blueprintRoleDefIds.has(personaId);
  }

  function getServiceElig(profileId) {
    return serviceEligibleProfiles.find(p => p.id === profileId) || null;
  }

  function getPersonasByRole(role) {
    return agentPersonas.filter(p => p.role === role);
  }

  function formatCost(cost) {
    if (cost === null || cost === undefined) return '—';
    return `$${cost.toFixed(4)}`;
  }

  const PROFILE_TYPE_LABELS = { text: 'Text', tts: 'TTS', stt: 'STT' };
  const PROFILE_TYPE_COLORS = {
    text: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
    tts: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
    stt: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
  };

  let filteredLLMProfiles = $derived(() => {
    const q = llmSearch.toLowerCase().trim();
    let list = [...llmProfiles];
    if (q) {
      list = list.filter(p =>
        p.name.toLowerCase().includes(q) ||
        (p.profile_type || 'text').toLowerCase().includes(q) ||
        p.model.toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => a.name.localeCompare(b.name));
    return list;
  });

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

  function toggleDropdown(profileId) {
    llmDropdownOpen = llmDropdownOpen === profileId ? null : profileId;
  }

  function handleDocClick() {
    llmDropdownOpen = null;
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

  function openCreateAgent(role) {
    modalMode = 'create';
    modalType = 'agent';
    formData = {
      id: '', name: '', role, system_prompt: '',
      llm_profile_id: llmProfiles.length > 0 ? llmProfiles[0].id : '',
      max_rounds: 5, consensus_threshold: 0.9, description: '', tags: [],
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
      else if (deleteTarget.type === 'agent') await deleteAgentPersona(deleteTarget.id);
      else if (deleteTarget.type === 'prompt') await deletePromptVariant(deleteTarget.id);
      else if (deleteTarget.type === 'roleType') await deleteRoleType(deleteTarget.id);
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
    } catch (e) { error.set(e.message); }
    finally { isSavingPrompt = false; }
  }

  function openPromptTranslate(variantId) {
    promptTranslateVariantId = variantId;
    promptTranslateTargetLang = 'de';
    promptTranslateResult = null;
    showPromptTranslateModal = true;
  }

  function closePromptTranslate() {
    showPromptTranslateModal = false;
    promptTranslateResult = null;
  }

  async function handleTranslatePrompt() {
    isTranslatingPrompt = true;
    promptTranslateResult = null;
    try {
      const result = await translatePromptVariant(promptTranslateVariantId, {
        targetLanguage: promptTranslateTargetLang,
        autoApprove: true,
      });
      promptTranslateResult = result;
      statusMessage = `✓ ${t('config.promptTranslated') || 'Prompt translated'}`;
    } catch (e) {
      error.set(e.message);
      promptTranslateResult = { error: e.message };
    } finally {
      isTranslatingPrompt = false;
    }
  }

  function openCreateRoleType() {
    roleTypeModalMode = 'create';
    roleTypeFormData = { id: '', name: '', description: '', color: '#6b7280', icon: '', active: true };
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
      if (!payload.description && payload.description !== 0) payload.description = '';
      if (!payload.icon) payload.icon = '👤';
      if (roleTypeModalMode === 'create') await createRoleType(payload);
      else await updateRoleType(roleTypeFormData.id, payload);
      showRoleTypeModal = false;
      statusMessage = `✓ ${t('config.roleTypeSaved')}`;
      roleTypes = await listRoleTypes();
    } catch (e) { error.set(e.message); }
    finally { isSavingRoleType = false; }
  }

  function closeRoleTypeModal() {
    showRoleTypeModal = false;
    roleTypeFormErrors = {};
  }

  async function handleEstimateCost() {
    try {
      costEstimate = await estimateCost($selectedLLMProfile, costNumAgents, costNumRounds);
    } catch (e) { error.set(e.message); }
  }

  async function handlePreview(variantId, role) {
    try {
      const r = role || previewRole;
      const result = await previewPromptVariant(variantId, r);
      previewContent = result.content;
      previewVariantId = variantId;
      previewRole = r;
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

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="space-y-6" onclick={handleDocClick} onkeydown={() => {}}>
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
      {#each ['llm', 'roleTypes', 'agents', 'prompts', 'cost'] as tab}
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
      <div class="flex items-center justify-between gap-4">
        <div class="relative flex-1 max-w-md">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">🔍</span>
          <input type="text" bind:value={llmSearch}
            placeholder="{t('config.search')}… (Name, Typ, Modell)"
            class="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          {#if llmSearch}
            <button class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" onclick={() => { llmSearch = ''; }}>✕</button>
          {/if}
        </div>
        <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap" onclick={openCreateLLM}>
          + {t('config.createLLM')}
        </button>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        {#if llmProfiles.length === 0}
          <div class="flex items-center justify-center h-32">
            <p class="text-gray-500 dark:text-gray-400">{t('config.llmProfilesPlaceholder')}</p>
          </div>
        {:else if filteredLLMProfiles().length === 0}
          <div class="flex items-center justify-center h-32">
            <p class="text-gray-500 dark:text-gray-400">{t('config.noResults') || 'Keine Treffer'}</p>
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm text-left">
              <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th class="px-4 py-3">{t('config.name')}</th>
                  <th class="px-4 py-3">{t('config.type') || 'Typ'}</th>
                  <th class="px-4 py-3 text-center">🔧 {t('service.utility') || 'Utility'}</th>
                  <th class="px-4 py-3">{t('config.provider')}</th>
                  <th class="px-4 py-3">{t('config.model')}</th>
                  <th class="px-4 py-3">{t('config.temperature')}</th>
                  <th class="px-4 py-3">{t('config.maxTokens')}</th>
                  <th class="px-4 py-3">{t('config.contextWindow')}</th>
                  <th class="px-4 py-3 text-right">{t('config.actions') || 'Aktionen'}</th>
                </tr>
              </thead>
              <tbody>
                {#each filteredLLMProfiles() as profile (profile.id)}
                  <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50
                    {$selectedLLMProfile === profile.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}">
                    <td class="px-4 py-3 font-medium">
                      <button class="text-blue-600 dark:text-blue-400 hover:underline" onclick={() => { selectedLLMProfile.set(profile.id); }}>
                        {profile.name}
                      </button>
                      {#if $selectedLLMProfile === profile.id}
                        <span class="ml-2 text-xs text-green-600 dark:text-green-400">✓ {t('config.active')}</span>
                      {/if}
                    </td>
                    <td class="px-4 py-3">
                      <span class="inline-block text-xs px-2 py-0.5 rounded-full {PROFILE_TYPE_COLORS[profile.profile_type || 'text']}">
                        {PROFILE_TYPE_LABELS[profile.profile_type || 'text']}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-center">
                      {#if getServiceElig(profile.id)}
                        {#if getServiceElig(profile.id).service_eligible || serviceLLMConfig.service_llm_profile_id === profile.id}
                          <div class="flex flex-col items-center gap-0.5">
                            <input type="checkbox"
                              checked={serviceLLMConfig.service_llm_profile_id === profile.id}
                              onchange={(e) => toggleServiceProfile(profile.id, e.target.checked)}
                              disabled={isLoadingServiceLLM}
                              class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500" />
                            {#if !getServiceElig(profile.id).service_eligible}
                              <span class="text-[10px] text-amber-500 dark:text-amber-400" title={getServiceElig(profile.id).eligibility_reason}>⚠️</span>
                            {/if}
                          </div>
                        {:else}
                          <span class="text-[10px] text-gray-400" title={getServiceElig(profile.id).eligibility_reason}>⚠️</span>
                        {/if}
                      {:else}
                        <span class="text-xs text-gray-400">—</span>
                      {/if}
                    </td>
                    <td class="px-4 py-3">{profile.provider}</td>
                    <td class="px-4 py-3 font-mono text-xs">{profile.model}</td>
                    <td class="px-4 py-3">{profile.temperature}</td>
                    <td class="px-4 py-3">{profile.max_tokens}</td>
                    <td class="px-4 py-3">{profile.context_window ?? '—'}</td>
                    <td class="px-4 py-3 text-right">
                      <div class="relative inline-block">
                        <button
                          class="px-2 py-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                          onclick={(e) => { e.stopPropagation(); toggleDropdown(profile.id); }}
                          aria-haspopup="true" aria-expanded={llmDropdownOpen === profile.id}>
                          ⋮
                        </button>
                        {#if llmDropdownOpen === profile.id}
                           <div class="absolute right-0 top-full mt-1 z-40 w-40 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1">
                             <button class="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { llmDropdownOpen = null; openEditLLM(profile); }}>
                               ✏️ {t('common.edit')}
                             </button>
                             <button class="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { llmDropdownOpen = null; openDuplicateLLM(profile); }}>
                               📋 {t('config.duplicate') || 'Duplizieren'}
                             </button>
                             <hr class="my-1 border-gray-200 dark:border-gray-700" />
                             <button class="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors" onclick={() => { llmDropdownOpen = null; confirmDelete('llm', profile.id, profile.name); }}>
                               🗑️ {t('common.delete')}
                             </button>
                           </div>
                        {/if}
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          <div class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 border-t border-gray-100 dark:border-gray-700">
            {filteredLLMProfiles().length} / {llmProfiles.length} {t('config.profiles') || 'Profile'}
          </div>
        {/if}
      </div>
    </div>

  <!-- Role Types Tab -->
  {:else if activeTab === 'roleTypes'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors" onclick={openCreateRoleType}>
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
                      <button class="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors" onclick={() => openEditRoleType(rt)}>
                        {t('common.edit')}
                      </button>
                      <button class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors ml-1" onclick={() => confirmDelete('roleType', rt.id, rt.name)}>
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
            <h4 class="text-md font-semibold text-gray-800 dark:text-white capitalize">{t(`agent.${role}`)}</h4>
            <button class="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors" onclick={() => openCreateAgent(role)}>
              + {t('config.createPersona')}
            </button>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {#each getPersonasByRole(role) as persona}
              <div class="p-3 rounded-lg border transition-colors relative
                {$selectedPersonas[role] === persona.id
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'}">
                <div class="cursor-pointer" onclick={() => { selectedPersonas.set({ ...$selectedPersonas, [role]: persona.id }); }}
                  onkeydown={(e) => { if (e.key === 'Enter') selectedPersonas.set({ ...$selectedPersonas, [role]: persona.id }); }}
                  role="button" tabindex="0">
                  <div class="flex items-center justify-between mb-1">
                    <span class="font-medium text-sm text-gray-800 dark:text-white">{persona.name}</span>
                    <span class="flex items-center gap-1">
                      {#if isBlueprintManaged(persona.id)}
                        <span class="text-xs px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded" title="{t('config.managedByBlueprint') || 'Managed by Blueprint Canvas'}">🧩</span>
                      {/if}
                      {#if $selectedPersonas[role] === persona.id}
                        <span class="text-xs text-green-600 dark:text-green-400">✓</span>
                      {/if}
                    </span>
                  </div>
                  {#if persona.description}
                    <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{persona.description}</p>
                  {/if}
                  <div class="flex flex-wrap gap-1">
                    {#each persona.tags as tag}
                      <span class="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">{tag}</span>
                    {/each}
                  </div>
                </div>
                <div class="flex gap-1 mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                  <button class="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors" onclick={() => openEditAgent(persona)}>
                    {t('common.edit')}
                  </button>
                  <button class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors" onclick={() => confirmDelete('agent', persona.id, persona.name)}>
                    {t('common.delete')}
                  </button>
                </div>
              </div>
            {:else}
              <p class="text-sm text-gray-500 dark:text-gray-400 col-span-full">{t('config.noProfiles')}</p>
            {/each}
          </div>
        </div>
      {/each}
    </div>

  <!-- Prompt Variants Tab -->
  {:else if activeTab === 'prompts'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors" onclick={openCreatePrompt}>
          + {t('config.createPromptVariant') || 'Create Prompt Variant'}
        </button>
      </div>
      {#each promptVariants as variant}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <h4 class="text-md font-semibold text-gray-800 dark:text-white">{variant.name || variant.id}</h4>
              {#if $selectedPromptVariant === variant.id}
                <span class="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full">✓ {t('config.active')}</span>
              {/if}
            </div>
            <div class="flex items-center gap-2">
              <button class="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-800/40 transition-colors" onclick={() => { selectedPromptVariant.set(variant.id); }}>
                {$selectedPromptVariant === variant.id ? t('config.active') : t('config.select') || 'Select'}
              </button>
              <button class="text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded hover:bg-purple-200 dark:hover:bg-purple-800/40 transition-colors" onclick={() => openPromptTranslate(variant.id)} title={t('config.translatePrompt') || 'Translate'}>
                🌐 {t('config.translate') || 'Translate'}
              </button>
              {#if variant.id !== 'default'}
                <button class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors" onclick={() => confirmDelete('prompt', variant.id, variant.id)}>
                  {t('common.delete')}
                </button>
              {/if}
            </div>
          </div>
          {#if variant.description}
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">{variant.description}</p>
          {/if}
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {#each PROMPT_ROLES as role}
              <div class="p-3 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 transition-colors">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm font-medium text-gray-800 dark:text-white capitalize">{role.emoji} {role.label}</span>
                  <button class="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={() => handlePreview(variant.id, role.value)}>
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

<!-- Config Modal (LLM Profile / Agent Persona) -->
<ConfigModal visible={showModal} mode={modalMode} type={modalType} bind:formData bind:formErrors {llmProfiles} onClose={closeModal} onSaved={handleModalSaved} />

<!-- Delete Confirmation Dialog -->
{#if showDeleteConfirm && deleteTarget}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeDeleteConfirm} role="dialog" aria-modal="true" tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6" role="presentation" onclick={(e) => e.stopPropagation()}>
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">{t('config.deleteProfile')}</h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">{t('config.confirmDelete', { name: deleteTarget.name })}</p>
      <div class="flex items-center justify-end gap-3">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={closeDeleteConfirm}>{t('common.cancel')}</button>
        <button class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors" onclick={handleDelete}>{t('common.delete')}</button>
      </div>
    </div>
  </div>
{/if}

<!-- Role Type Modal -->
{#if showRoleTypeModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeRoleTypeModal} role="dialog" aria-modal="true" tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto mx-4" role="presentation" onclick={(e) => e.stopPropagation()}>
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">{roleTypeModalMode === 'create' ? t('config.createRoleType') : t('config.editRoleType')}</h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none" onclick={closeRoleTypeModal}>✕</button>
      </div>
      <div class="px-6 py-4 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label for="rt-form-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.id')} *</label>
            <input id="rt-form-id" type="text" bind:value={roleTypeFormData.id} disabled={roleTypeModalMode === 'edit'}
              class="w-full px-3 py-2 border rounded-lg text-sm {roleTypeFormErrors.id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:bg-gray-100 dark:disabled:bg-gray-600 disabled:cursor-not-allowed" placeholder="custom-role" />
            {#if roleTypeFormErrors.id}<p class="text-xs text-red-500 mt-1">{roleTypeFormErrors.id}</p>{/if}
          </div>
          <div>
            <label for="rt-form-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.name')} *</label>
            <input id="rt-form-name" type="text" bind:value={roleTypeFormData.name}
              class="w-full px-3 py-2 border rounded-lg text-sm {roleTypeFormErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} bg-white dark:bg-gray-700 text-gray-900 dark:text-white" placeholder="Custom Role" />
            {#if roleTypeFormErrors.name}<p class="text-xs text-red-500 mt-1">{roleTypeFormErrors.name}</p>{/if}
          </div>
          <div>
            <label for="rt-form-color" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.roleTypeColor')}</label>
            <input id="rt-form-color" type="color" bind:value={roleTypeFormData.color} class="w-full h-10 px-1 py-1 border border-gray-300 dark:border-gray-600 rounded-lg" />
          </div>
          <div>
            <label for="rt-form-icon" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.roleTypeIcon')}</label>
            <input id="rt-form-icon" type="text" bind:value={roleTypeFormData.icon} class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white" placeholder="🔍" />
          </div>
          <div class="md:col-span-2">
            <label for="rt-form-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.description')}</label>
            <input id="rt-form-desc" type="text" bind:value={roleTypeFormData.description} class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white" placeholder="Description of this role type" />
          </div>
        </div>
      </div>
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={closeRoleTypeModal}>{t('common.cancel')}</button>
        <button class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleSaveRoleType} disabled={isSavingRoleType}>{isSavingRoleType ? '...' : t('common.save')}</button>
      </div>
    </div>
  </div>
{/if}

<!-- Create Prompt Variant Modal -->
{#if showPromptCreateModal}
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="button" tabindex="0" onclick={closePromptCreate} onkeydown={(e) => e.key === 'Enter' && closePromptCreate()}>
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto" role="button" tabindex="0" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">{t('config.createPromptVariant') || 'Create Prompt Variant'}</h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" onclick={closePromptCreate}>✕</button>
      </div>
      <div class="p-6 space-y-4">
        <div>
          <label for="pv-form-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">ID *</label>
          <input id="pv-form-id" type="text" bind:value={promptCreateData.id}
            class="w-full px-3 py-2 border rounded-lg text-sm {promptCreateErrors.id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} bg-white dark:bg-gray-700 text-gray-900 dark:text-white" placeholder="my-custom-variant" />
          {#if promptCreateErrors.id}<p class="text-xs text-red-500 mt-1">{promptCreateErrors.id}</p>{/if}
        </div>
        <div>
          <label for="pv-form-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.name')} *</label>
          <input id="pv-form-name" type="text" bind:value={promptCreateData.name}
            class="w-full px-3 py-2 border rounded-lg text-sm {promptCreateErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} bg-white dark:bg-gray-700 text-gray-900 dark:text-white" placeholder="My Custom Variant" />
          {#if promptCreateErrors.name}<p class="text-xs text-red-500 mt-1">{promptCreateErrors.name}</p>{/if}
        </div>
        <div>
          <label for="pv-form-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.description')}</label>
          <input id="pv-form-desc" type="text" bind:value={promptCreateData.description} class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white" placeholder="Description of this prompt variant" />
        </div>
        <div>
          <p class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Prompts per Role</p>
          <div class="space-y-3">
            {#each PROMPT_ROLES as role}
              <div>
                <label for="pv-prompt-{role.value}" class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{role.emoji} {role.label}</label>
                <textarea id="pv-prompt-{role.value}" value={promptCreateData.prompts[role.value] || ''}
                  oninput={(e) => { promptCreateData = { ...promptCreateData, prompts: { ...promptCreateData.prompts, [role.value]: e.target.value } }; }}
                  rows="4" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono" placeholder="System prompt for {role.label}..."></textarea>
              </div>
            {/each}
          </div>
        </div>
      </div>
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={closePromptCreate}>{t('common.cancel')}</button>
        <button class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleSavePromptVariant} disabled={isSavingPrompt}>{isSavingPrompt ? '...' : t('common.save')}</button>
      </div>
    </div>
  </div>
{/if}

<!-- Prompt Translation Modal -->
{#if showPromptTranslateModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closePromptTranslate} role="dialog" aria-modal="true" tabindex="-1">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4" role="presentation" onclick={(e) => e.stopPropagation()}>
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">🌐 {t('config.translatePrompt') || 'Translate Prompt'}</h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" onclick={closePromptTranslate}>✕</button>
      </div>
      <div class="p-6 space-y-4">
        <p class="text-sm text-gray-600 dark:text-gray-400">{t('config.translatePromptHint') || 'Translate all roles of this prompt variant to the target language using LLM.'}</p>
        <div>
          <label for="translate-lang" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('config.targetLanguage') || 'Target Language'}</label>
          <select id="translate-lang" bind:value={promptTranslateTargetLang}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
            <option value="de">Deutsch (de)</option>
            <option value="en">English (en)</option>
            <option value="fr">Français (fr)</option>
            <option value="es">Español (es)</option>
            <option value="it">Italiano (it)</option>
            <option value="pt">Português (pt)</option>
            <option value="ru">Русский (ru)</option>
            <option value="zh">中文 (zh)</option>
            <option value="ja">日本語 (ja)</option>
            <option value="ko">한국어 (ko)</option>
            <option value="ar">العربية (ar)</option>
            <option value="he">עברית (he)</option>
          </select>
        </div>
        {#if promptTranslateResult}
          <div class="p-3 rounded-lg {promptTranslateResult.error ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300' : 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'}">
            {#if promptTranslateResult.error}
              <p class="text-sm font-medium">{promptTranslateResult.error}</p>
            {:else}
              <p class="text-sm font-medium">{t('config.translationComplete') || 'Translation complete'}</p>
              {#if promptTranslateResult.results}
                <ul class="text-xs mt-2 space-y-1">
                  {#each promptTranslateResult.results as r}
                    <li>{r.role}: {r.status === 'ok' ? '✅' : '❌'} {r.error || ''}</li>
                  {/each}
                </ul>
              {/if}
            {/if}
          </div>
        {/if}
      </div>
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={closePromptTranslate} disabled={isTranslatingPrompt}>{t('common.close')}</button>
        <button class="px-4 py-2 text-sm text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleTranslatePrompt} disabled={isTranslatingPrompt}>{isTranslatingPrompt ? '...' : (t('config.translate') || 'Translate')}</button>
      </div>
    </div>
  </div>
{/if}
