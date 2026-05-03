<script>
  import { onMount } from 'svelte';
  import { loading, error, selectedLLMProfile, selectedPromptVariant, selectedPersonas } from '../lib/stores.js';
  import { i18n } from '../lib/i18n/index.js';
  import {
    getLLMProfiles,
    getAgentPersonas,
    getPromptVariants,
    estimateCost,
    previewPromptVariant,
    reloadProfiles,
    getBackendLogs,
  } from '../lib/api.js';

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  // --- State ---
  let llmProfiles = [];
  let agentPersonas = [];
  let promptVariants = [];
  let costEstimate = null;
  let previewContent = null;
  let previewRole = 'strategist';

  // Selected profile for debate defaults — uses global stores so DebateView can read them

  // Cost estimation inputs
  let costNumAgents = 4;
  let costNumRounds = 3;

  // Active tab
  let activeTab = 'llm'; // 'llm' | 'agents' | 'prompts' | 'cost' | 'system'

  let isLoading = false;
  let statusMessage = '';

  // System tab state
  let isReloading = false;
  let reloadResult = null;
  let logLines = [];
  let logSearch = '';
  let isLoadingLogs = false;

  // --- Lifecycle ---
  onMount(async () => {
    $error = null;  // Clear any stale error from previous views
    isLoading = true;
    try {
      // Load each resource independently so one failure doesn't block others
      const results = await Promise.allSettled([
        getLLMProfiles(),
        getAgentPersonas(),
        getPromptVariants(),
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

  async function handlePreview(variantId) {
    try {
      const result = await previewPromptVariant(variantId, previewRole);
      previewContent = result.content;
    } catch (e) {
      $error = e.message;
    }
  }

  async function handleReloadProfiles() {
    isReloading = true;
    statusMessage = '';
    try {
      reloadResult = await reloadProfiles();
      statusMessage = `✓ ${reloadResult.message} — ${reloadResult.llm_profiles} LLM, ${reloadResult.agent_personas} Agenten, ${reloadResult.prompt_variants} Prompts`;
      // Reload the profile lists in the UI
      const results = await Promise.allSettled([getLLMProfiles(), getAgentPersonas(), getPromptVariants()]);
      if (results[0].status === 'fulfilled') llmProfiles = results[0].value;
      if (results[1].status === 'fulfilled') agentPersonas = results[1].value;
      if (results[2].status === 'fulfilled') promptVariants = results[2].value;
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

  function getPersonasByRole(role) {
    return agentPersonas.filter(p => p.role === role);
  }

  function formatCost(cost) {
    if (cost === null || cost === undefined) return '—';
    return `$${cost.toFixed(4)}`;
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
      {#each ['llm', 'agents', 'prompts', 'cost', 'system'] as tab}
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
            {activeTab === tab
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
          on:click={() => { activeTab = tab; previewContent = null; }}
        >
          {#if tab === 'llm'}{t('config.llmProfiles')}
          {:else if tab === 'agents'}{t('config.agentProfiles')}
          {:else if tab === 'prompts'}{t('config.promptVariants')}
          {:else if tab === 'cost'}{t('config.costEstimate')}
          {:else if tab === 'system'}⚙️ System
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
              </tr>
            </thead>
            <tbody>
              {#each llmProfiles as profile}
                <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50
                  {$selectedLLMProfile === profile.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}">
                  <td class="px-4 py-3 font-medium">
                    <button
                      class="text-blue-600 dark:text-blue-400 hover:underline"
                      on:click={() => { $selectedLLMProfile = profile.id; }}
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
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

  <!-- Agent Personas Tab -->
  {:else if activeTab === 'agents'}
    <div class="space-y-4">
      {#each ['strategist', 'critic', 'optimizer', 'moderator'] as role}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
          <h4 class="text-md font-semibold text-gray-800 dark:text-white mb-3 capitalize">
            {t(`agent.${role}`)}
          </h4>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {#each getPersonasByRole(role) as persona}
              <div
                class="p-3 rounded-lg border cursor-pointer transition-colors
                  {$selectedPersonas[role] === persona.id
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'}"
                on:click={() => { $selectedPersonas = { ...$selectedPersonas, [role]: persona.id }; }}
                on:keydown={(e) => { if (e.key === 'Enter') $selectedPersonas = { ...$selectedPersonas, [role]: persona.id }; }}
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
            {:else}
              <p class="text-sm text-gray-500 dark:text-gray-400 col-span-full">
                {t('config.noProfiles')}
              </p>
            {/each}
          </div>
        </div>
      {/each}
    </div>

  <!-- Prompt Variants Tab -->
  {:else if activeTab === 'prompts'}
    <div class="space-y-4">
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
        {#if promptVariants.length === 0}
          <div class="flex items-center justify-center h-32">
            <p class="text-gray-500 dark:text-gray-400">{t('config.promptVariantsPlaceholder')}</p>
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm text-left">
              <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th class="px-4 py-3">ID</th>
                  <th class="px-4 py-3">{t('config.description')}</th>
                  <th class="px-4 py-3">{t('config.preview')}</th>
                </tr>
              </thead>
              <tbody>
                {#each promptVariants as variant}
                  <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50
                    {$selectedPromptVariant === variant.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}">
                    <td class="px-4 py-3 font-medium">
                      <button
                        class="text-blue-600 dark:text-blue-400 hover:underline"
                        on:click={() => { $selectedPromptVariant = variant.id; }}
                      >
                        {variant.id}
                      </button>
                      {#if $selectedPromptVariant === variant.id}
                        <span class="ml-2 text-xs text-green-600 dark:text-green-400">✓ {t('config.active')}</span>
                      {/if}
                    </td>
                    <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{variant.description || '—'}</td>
                    <td class="px-4 py-3">
                      <select
                        bind:value={previewRole}
                        class="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white mr-2"
                      >
                        <option value="strategist">Strategist</option>
                        <option value="critic">Critic</option>
                        <option value="optimizer">Optimizer</option>
                        <option value="moderator">Moderator</option>
                      </select>
                      <button
                        class="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                        on:click={() => handlePreview(variant.id)}
                      >
                        {t('config.preview')}
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>

      {#if previewContent}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border border-gray-200 dark:border-gray-700">
          <h4 class="text-sm font-semibold text-gray-800 dark:text-white mb-2">
            {t('config.preview')}: {$selectedPromptVariant}/{previewRole}
          </h4>
          <pre class="text-xs text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-3 rounded overflow-x-auto max-h-64 whitespace-pre-wrap">{previewContent}</pre>
        </div>
      {/if}
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
        on:click={handleEstimateCost}
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
          on:click={handleReloadProfiles}
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
          on:click={() => location.reload()}
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
            on:keydown={(e) => { if (e.key === 'Enter') handleLoadLogs(); }}
          />
          <button
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors
                   disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            on:click={handleLoadLogs}
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
