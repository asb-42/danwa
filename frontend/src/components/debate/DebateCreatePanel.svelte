<script>
  /**
   * DebateCreatePanel — Form for creating a new debate.
   *
   * Owns all form state and emits onCreate with the collected parameters.
   */
  import { onMount } from 'svelte';
  import { loading, error, selectedLLMProfile, selectedPromptVariant, selectedPersonas, activeProject } from '../../lib/stores.js';
  import { createDebate, getDocuments } from '../../lib/api.js';
  import { discoverA2A } from '../../lib/a2aApi.js';
  import { i18n, locale } from '../../lib/i18n/index.js';
  import A2ACapabilities from '../blueprint/A2ACapabilities.svelte';

  let { onCreated = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let projectId = $derived($activeProject?.id);

  // Form state
  let caseText = $state('');
  let maxRounds = $state(3);
  let consensusThreshold = $state(0.8);
  let searchMode = $state('off');
   let enableExtraRounds = $state(false);

  // RAG document selection
  let availableDocuments = $state([]);
  let selectedDocumentIds = $state([]);
  let ragAutoRetrieve = $state(false);
  let includeDebateResults = $state(false);

  // A2A external agent configuration
  let a2aAgents = $state([]);
  let showA2ASection = $state(false);
  let a2aDiscovering = $state(false);
  let a2aDiscoverError = $state('');
  let a2aCapabilities = $state({});

  let validA2AAgents = $derived(
    a2aAgents.filter(a => a.url.trim() !== '')
  );

  // Load documents on mount
  onMount(() => {
    loadAvailableDocuments();
  });

  // Reload documents when project changes
  $effect(() => {
    if (projectId) {
      loadAvailableDocuments();
    }
  });

  async function loadAvailableDocuments() {
    try {
      availableDocuments = await getDocuments();
    } catch {
      availableDocuments = [];
    }
  }

  function toggleDocumentSelection(docId) {
    const idx = selectedDocumentIds.indexOf(docId);
    if (idx >= 0) {
      selectedDocumentIds = selectedDocumentIds.filter(id => id !== docId);
    } else {
      selectedDocumentIds = [...selectedDocumentIds, docId];
    }
  }

  // A2A agent management
  function addA2AAgent() {
    a2aAgents = [...a2aAgents, { url: '', role: '', position: '' }];
  }

  function removeA2AAgent(index) {
    a2aAgents = a2aAgents.filter((_, i) => i !== index);
  }

  function updateA2AAgent(index, field, value) {
    a2aAgents = a2aAgents.map((agent, i) =>
      i === index ? { ...agent, [field]: value } : agent
    );
  }

  async function handleDiscoverA2A() {
    a2aDiscovering = true;
    a2aDiscoverError = '';
    a2aCapabilities = {};
    try {
      const urls = a2aAgents.filter(a => a.url.trim()).map(a => a.url.trim());
      const results = {};
      for (const url of urls) {
        try {
          results[url] = await discoverA2A(url);
        } catch (e) {
          results[url] = { error: e.message };
        }
      }
      a2aCapabilities = results;
    } catch (e) {
      a2aDiscoverError = e.message;
    } finally {
      a2aDiscovering = false;
    }
  }

  async function handleCreateDebate() {
    if (!caseText.trim()) {
      error.set(t('debate.enterCase'));
      return;
    }

    loading.set(true);
    error.set(null);

    try {
      const response = await createDebate(caseText, {
        max_rounds: maxRounds,
        consensus_threshold: consensusThreshold,
        search_mode: searchMode,
        llm_profile_id: $selectedLLMProfile,
        prompt_variant: $selectedPromptVariant,
        agent_persona_ids: $selectedPersonas,
        language: $locale || 'de',
        document_ids: selectedDocumentIds,
        rag_auto_retrieve: ragAutoRetrieve,
        include_debate_results: includeDebateResults,
        enable_extra_rounds: enableExtraRounds,
        a2a_agents: validA2AAgents,
      });
      caseText = '';
      selectedDocumentIds = [];
      ragAutoRetrieve = false;
      a2aAgents = [];
      onCreated(response);
    } catch (err) {
      error.set(err.message);
    } finally {
      loading.set(false);
    }
  }
</script>

<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
  <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('debate.newDebate')}</h3>

  <form onsubmit={(e) => { e.preventDefault(); handleCreateDebate(); }} class="space-y-4">
    <div>
      <label for="case-text" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {t('debate.caseLabel')}
      </label>
      <textarea
        id="case-text"
        bind:value={caseText}
        rows="4"
        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
               bg-white dark:bg-gray-700 text-gray-900 dark:text-white
               focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
        placeholder={t('debate.casePlaceholder')}
      ></textarea>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="max-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('debate.maxRounds')}
        </label>
        <input
          id="max-rounds"
          type="number"
          bind:value={maxRounds}
          min="1"
          max="10"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      <div>
        <label for="consensus-threshold" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('debate.consensusThreshold')}
        </label>
        <input
          id="consensus-threshold"
          type="number"
          bind:value={consensusThreshold}
          min="0"
          max="1"
          step="0.1"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
    </div>

    <div>
      <label for="search-mode" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {t('debate.searchMode')}
      </label>
      <select
        id="search-mode"
        bind:value={searchMode}
        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
               bg-white dark:bg-gray-700 text-gray-900 dark:text-white
               focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      >
        <option value="off">{t('debate.searchOff')}</option>
        <option value="optional">{t('debate.searchOptional')}</option>
        <option value="required">{t('debate.searchRequired')}</option>
      </select>
      <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
        {t(`debate.searchModeHint.${searchMode}`)}
      </p>
    </div>

    <!-- RAG Document Selection -->
    {#if availableDocuments.length > 0}
      <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            📄 {t('documents.ragContext')}
          </span>
          <span class="text-xs text-gray-500 dark:text-gray-400">
            {selectedDocumentIds.length} {t('documents.selectDocuments').toLowerCase()}
          </span>
        </div>

        <div class="space-y-2 max-h-40 overflow-y-auto">
          {#each availableDocuments as doc (doc.id)}
            <label class="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={selectedDocumentIds.includes(doc.id)}
                onchange={() => toggleDocumentSelection(doc.id)}
                class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
              />
              <span class="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white truncate">
                {doc.filename}
              </span>
            </label>
          {/each}
        </div>

        <div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={ragAutoRetrieve}
              class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
            />
            <span class="text-sm text-gray-700 dark:text-gray-300">
              🔍 {t('documents.ragAutoRetrieve')}
            </span>
          </label>
          <p class="mt-1 text-xs text-gray-500 dark:text-gray-400 ml-6">
            {t('documents.ragAutoRetrieveHint')}
          </p>
        </div>

        <div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={includeDebateResults}
              class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
            />
            <span class="text-sm text-gray-700 dark:text-gray-300">
              🔄 {t('documents.includeDebateResults')}
            </span>
          </label>
          <p class="mt-1 text-xs text-gray-500 dark:text-gray-400 ml-6">
            {t('documents.includeDebateResultsHint')}
          </p>
        </div>
      </div>
    {/if}

    <!-- Extension / Extra Rounds -->
    <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
      <label class="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          bind:checked={enableExtraRounds}
          class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
        />
        <span class="text-sm text-gray-700 dark:text-gray-300">
          {t('debate.enableExtraRounds')}
        </span>
      </label>
      <p class="mt-1 text-xs text-gray-500 dark:text-gray-400 ml-6">
        {t('debate.extensionRequest', { rounds: maxRounds, current: '…', threshold: Math.round(consensusThreshold * 100) })}
      </p>
    </div>

    <!-- A2A External Agent Configuration -->
    <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
      <div class="flex items-center justify-between mb-2">
        <button
          type="button"
          class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
          onclick={() => showA2ASection = !showA2ASection}
        >
          <span class="transition-transform" class:rotate-90={showA2ASection}>▶</span>
          🌐 {t('a2a.title')}
        </button>
        {#if validA2AAgents.length > 0}
          <span class="px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
            {validA2AAgents.length}
          </span>
        {/if}
      </div>

      {#if showA2ASection}
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
          {t('a2a.description')}
        </p>

        {#if a2aAgents.length === 0}
          <p class="text-sm text-gray-400 dark:text-gray-500 italic mb-3">
            {t('a2a.noAgents')}
          </p>
        {:else}
          <div class="space-y-3 mb-3">
            {#each a2aAgents as agent, i (i)}
              <div class="grid grid-cols-1 md:grid-cols-3 gap-2 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div>
                  <label for={`a2a-url-${i}`} class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                    {t('a2a.agentUrl')} <span class="text-red-500">*</span>
                  </label>
                  <input
                    id={`a2a-url-${i}`}
                    type="url"
                    value={agent.url}
                    oninput={(e) => updateA2AAgent(i, 'url', e.target.value)}
                    placeholder={t('a2a.agentUrlPlaceholder')}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded
                           bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                           focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  />
                </div>
                <div>
                  <label for={`a2a-role-${i}`} class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                    {t('a2a.role')}
                  </label>
                  <input
                    id={`a2a-role-${i}`}
                    type="text"
                    value={agent.role}
                    oninput={(e) => updateA2AAgent(i, 'role', e.target.value)}
                    placeholder={t('a2a.rolePlaceholder')}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded
                           bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                           focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  />
                </div>
                <div class="flex items-end gap-2">
                  <div class="flex-1">
                    <label for={`a2a-pos-${i}`} class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                      {t('a2a.position')}
                    </label>
                    <input
                      id={`a2a-pos-${i}`}
                      type="text"
                      value={agent.position}
                      oninput={(e) => updateA2AAgent(i, 'position', e.target.value)}
                      placeholder={t('a2a.positionPlaceholder')}
                      class="w-full px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded
                             bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                             focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    />
                  </div>
                  <button
                    type="button"
                    onclick={() => removeA2AAgent(i)}
                    class="px-2 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                    title={t('a2a.remove')}
                  >
                    ✕
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}

        <button
          type="button"
          onclick={addA2AAgent}
          class="flex items-center gap-1 px-3 py-1.5 text-sm text-purple-600 dark:text-purple-400
                 border border-purple-300 dark:border-purple-600 rounded-lg
                 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors"
        >
          + {t('a2a.addAgent')}
        </button>
        <button
          type="button"
          onclick={handleDiscoverA2A}
          disabled={a2aDiscovering || a2aAgents.filter(a => a.url.trim()).length === 0}
          class="flex items-center gap-1 px-3 py-1.5 text-sm text-cyan-600 dark:text-cyan-400
                 border border-cyan-300 dark:border-cyan-600 rounded-lg
                 hover:bg-cyan-50 dark:hover:bg-cyan-900/20 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {#if a2aDiscovering}
            <span class="w-3 h-3 border-2 border-cyan-600 border-t-transparent rounded-full animate-spin"></span>
            {t('a2a.discover.loading')}
          {:else}
            🔎 {t('a2a.discover.button')}
          {/if}
        </button>
      {/if}

      {#if a2aDiscoverError}
        <p class="mt-2 text-sm text-red-600 dark:text-red-400">{a2aDiscoverError}</p>
      {/if}

      {#each Object.entries(a2aCapabilities) as [url, caps]}
        <div class="mt-3">
          <p class="text-xs font-mono text-gray-500 dark:text-gray-400 mb-1">{url}</p>
          <A2ACapabilities capabilities={caps} />
        </div>
      {/each}
    </div>

    <button
      type="submit"
      class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors
             disabled:opacity-50 disabled:cursor-not-allowed"
      disabled={$loading || !caseText.trim()}
    >
      {$loading ? t('debate.creating') : t('debate.createButton')}
    </button>
  </form>
</div>
