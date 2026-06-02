<script>
  import { tStore } from '../../lib/i18n/index.js';
  import { getDebates } from '../../lib/api.js';

  let {
    config = $bindable(),
    agents = [],
    profiles = [],
    agentCores = [],
    argumentationPatterns = [],
    toneProfiles = [],
    promptModifiers = [],
    documents = [],
    isLoadingProfiles = false,
    isLoadingComponents = false,
    error = '',
    onReview = () => {},
  } = $props();

  let t = $derived($tStore);

  let completedDebates = $state([]);
  let loadingCompletedDebates = $state(false);

  $effect(() => {
    if (config.includeDebateResults && completedDebates.length === 0 && !loadingCompletedDebates) {
      loadCompletedDebates();
    }
    if (!config.includeDebateResults) {
      config.selectedDebateIds = [];
    }
  });

  async function loadCompletedDebates() {
    if (loadingCompletedDebates) return;
    loadingCompletedDebates = true;
    try {
      const res = await getDebates(100, { status: 'completed' });
      completedDebates = res || [];
      config.selectedDebateIds = completedDebates.map(d => d.debate_id);
    } catch (e) {
      console.warn('Failed to load completed debates:', e);
      completedDebates = [];
    } finally {
      loadingCompletedDebates = false;
    }
  }

  function toggleDocumentSelection(docId) {
    const idx = config.selectedDocumentIds.indexOf(docId);
    if (idx >= 0) {
      config.selectedDocumentIds = config.selectedDocumentIds.filter(id => id !== docId);
    } else {
      config.selectedDocumentIds = [...config.selectedDocumentIds, docId];
    }
  }

  function toggleSelectAll() {
    if (config.selectedDocumentIds.length === documents.length) {
      config.selectedDocumentIds = [];
    } else {
      config.selectedDocumentIds = documents.map(d => d.id);
    }
  }

  function toggleDebateSelection(debateId) {
    const idx = config.selectedDebateIds.indexOf(debateId);
    if (idx >= 0) {
      config.selectedDebateIds = config.selectedDebateIds.filter(id => id !== debateId);
    } else {
      config.selectedDebateIds = [...config.selectedDebateIds, debateId];
    }
  }
</script>

<div class="config-section">
  <div class="form-group">
    <label for="mvp-topic" class="form-label">{t('mvpDebate.form.debateTopic')}</label>
    <textarea
      id="mvp-topic"
      class="form-textarea"
      placeholder={t('mvpDebate.form.topicPlaceholder')}
      bind:value={config.topic}
      disabled={isLoadingProfiles}
      maxlength="2000"
    ></textarea>
  </div>

  <div class="settings-row">
    <div class="form-group">
      <label for="mvp-rounds" class="form-label">{t('mvpDebate.form.maxRounds')}</label>
      <input
        id="mvp-rounds"
        type="number"
        class="form-input"
        bind:value={config.maxRounds}
        min="1"
        max="50"
      />
    </div>
    <div class="form-group">
      <label for="mvp-threshold" class="form-label">{t('mvpDebate.form.consensusThreshold')}</label>
      <input
        id="mvp-threshold"
        type="number"
        class="form-input"
        bind:value={config.threshold}
        min="0"
        max="1"
        step="0.05"
      />
    </div>
  </div>

  <!-- Web Search Mode -->
  <div class="form-group">
    <label for="mvp-search-mode" class="form-label">{t('mvpDebate.form.webSearch')}</label>
    <select
      id="mvp-search-mode"
      class="form-select"
      bind:value={config.searchMode}
    >
      <option value="off">{t('mvpDebate.searchModeOffDesc')}</option>
      <option value="optional">{t('mvpDebate.searchModeOptionalDesc')}</option>
      <option value="required">{t('mvpDebate.searchModeRequiredDesc')}</option>
    </select>
  </div>

  <!-- DMS Document Selection -->
  {#if documents.length > 0}
    <div class="dms-section">
      <div class="flex items-center justify-between mb-2">
        <span class="form-label">{t('mvpDebate.form.dmsDocuments')}</span>
        <div class="flex items-center gap-2">
          <button
            class="text-xs text-blue-600 dark:text-blue-400 hover:underline"
            onclick={toggleSelectAll}
          >{config.selectedDocumentIds.length === documents.length ? t('mvpDebate.form.deselectAll') : t('mvpDebate.form.selectAll')}</button>
          <span class="text-xs text-gray-500 dark:text-gray-400">{config.selectedDocumentIds.length} selected</span>
        </div>
      </div>
      <div class="dms-doc-list">
        {#each documents as doc (doc.id)}
          <label class="dms-doc-item">
            <input
              type="checkbox"
              checked={config.selectedDocumentIds.includes(doc.id)}
              onchange={() => toggleDocumentSelection(doc.id)}
              class="dms-checkbox"
            />
            <span class="dms-doc-name">{doc.filename}</span>
          </label>
        {/each}
      </div>
      <div class="dms-options">
        <label class="dms-option">
          <input type="checkbox" bind:checked={config.ragAutoRetrieve} class="dms-checkbox" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('mvpDebate.form.autoRetrieveChunks')}</span>
        </label>
        <label class="dms-option">
          <input type="checkbox" bind:checked={config.includeDebateResults} class="dms-checkbox" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('mvpDebate.form.includePreviousDebates')}</span>
        </label>
        <label class="dms-option">
          <input type="checkbox" bind:checked={config.includeDocumentAnalysis} class="dms-checkbox" />
          <span class="text-sm text-gray-700 dark:text-gray-300">{t('documents.includeDocumentAnalysis')}</span>
        </label>
        {#if config.includeDebateResults}
          <div class="dms-debate-list">
            {#if loadingCompletedDebates}
              <span class="text-xs text-gray-500 dark:text-gray-400">{t('mvpDebate.form.loadingDebates')}</span>
            {:else if completedDebates.length === 0}
              <span class="text-xs text-gray-500 dark:text-gray-400">{t('mvpDebate.form.noCompletedDebates')}</span>
            {:else}
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs text-gray-500 dark:text-gray-400">{config.selectedDebateIds.length} of {completedDebates.length} selected</span>
                <button
                  class="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  onclick={() => { config.selectedDebateIds = config.selectedDebateIds.length === completedDebates.length ? [] : completedDebates.map(d => d.debate_id); }}
                >{config.selectedDebateIds.length === completedDebates.length ? t('mvpDebate.form.deselectAll') : t('mvpDebate.form.selectAll')}</button>
              </div>
              {#each completedDebates as debate (debate.debate_id)}
                <label class="dms-debate-item">
                  <input
                    type="checkbox"
                    checked={config.selectedDebateIds.includes(debate.debate_id)}
                    onchange={() => toggleDebateSelection(debate.debate_id)}
                    class="dms-checkbox"
                  />
                  <span class="dms-debate-name">{debate.title || debate.debate_id.slice(0, 12)}</span>
                </label>
              {/each}
            {/if}
          </div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Extension / Extra Rounds -->
  <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
    <label class="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        bind:checked={config.enableExtraRounds}
        class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
      />
      <span class="text-sm text-gray-700 dark:text-gray-300">
        {t('debate.enableExtraRounds')}
      </span>
    </label>
    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400 ml-6">
      {t('debate.extensionRequest', { rounds: config.maxRounds, current: '…', threshold: config.threshold })}
    </p>
  </div>

  <div class="agent-nodes">
    {#each agents as agent, idx}
      <div class="agent-node" style="border-top-color: {agent.color}">
        <div class="agent-header">
          <div class="agent-badge" style="background: {agent.color}20; color: {agent.color}">
            <span class="agent-icon">{agent.icon}</span>
            <span class="agent-label">{agent.label}</span>
          </div>
        </div>
        <p class="agent-desc">{agent.desc}</p>
        <div class="agent-llm-select">
          <label for="llm-{agent.role}" class="select-label">{t('mvpDebate.form.llmProfile')}</label>
          {#if isLoadingProfiles}
            <div class="select-loading">{t('mvpDebate.form.loadingProfiles')}</div>
          {:else}
            <select
              id="llm-{agent.role}"
              class="form-select"
              bind:value={config.llmAssignments[agent.role]}
            >
              {#each profiles as profile}
                <option value={profile.id}>{profile.name}</option>
              {/each}
            </select>
          {/if}
        </div>

        <div class="agent-core-select">
          <label for="core-{agent.role}" class="select-label">{t('mvpDebate.form.agentCoreOptional')}</label>
          {#if isLoadingComponents}
            <div class="select-loading">Loading...</div>
          {:else}
            <select
              id="core-{agent.role}"
              class="form-select"
              bind:value={config.agentCoreAssignments[agent.role]}
            >
              <option value="">{t('mvpDebate.form.defaultBuiltIn')}</option>
              {#each agentCores.filter(c => c.role === agent.role) as core}
                <option value={core.id}>{core.name}</option>
              {/each}
            </select>
          {/if}
        </div>

        <div class="agent-pat-select">
          <label for="pat-{agent.role}" class="select-label">{t('mvpDebate.form.argumentationPatternOptional')}</label>
          {#if isLoadingComponents}
            <div class="select-loading">Loading...</div>
          {:else}
            <select
              id="pat-{agent.role}"
              class="form-select"
              bind:value={config.argumentationPatternAssignments[agent.role]}
            >
              <option value="">{t('mvpDebate.form.defaultNone')}</option>
              {#each argumentationPatterns as pattern}
                <option value={pattern.id}>{pattern.name}</option>
              {/each}
            </select>
          {/if}
        </div>

        <div class="agent-tone-select">
          <label for="tone-{agent.role}" class="select-label">{t('mvpDebate.form.toneProfileOptional')}</label>
          {#if isLoadingComponents}
            <div class="select-loading">Loading...</div>
          {:else}
            <select
              id="tone-{agent.role}"
              class="form-select"
              bind:value={config.toneProfileAssignments[agent.role]}
            >
              <option value="">{t('mvpDebate.form.defaultNone')}</option>
              {#each toneProfiles as profile}
                <option value={profile.id}>{profile.name}</option>
              {/each}
            </select>
          {/if}
        </div>

        <div class="agent-mod-select">
          <label for="mod-{agent.role}" class="select-label">{t('mvpDebate.form.promptModifierOptional')}</label>
          {#if isLoadingComponents}
            <div class="select-loading">Loading...</div>
          {:else}
            <select
              id="mod-{agent.role}"
              class="form-select"
              bind:value={config.promptModifierAssignments[agent.role]}
            >
              <option value="">{t('mvpDebate.form.defaultNone')}</option>
              {#each promptModifiers as mod}
                <option value={mod.id}>{mod.name}</option>
              {/each}
            </select>
          {/if}
        </div>
      </div>
      {#if idx < agents.length - 1}
        <div class="agent-arrow">→</div>
      {/if}
    {/each}
  </div>

  {#if error}
    <div class="error-box" role="alert">
      <span class="error-icon">⚠️</span>
      <span class="error-text">{error}</span>
    </div>
  {/if}

  <div class="actions-row">
    <button
      class="btn btn-start"
      onclick={() => { if (config.topic.trim() && !isLoadingProfiles) onReview(); }}
      disabled={!config.topic.trim() || isLoadingProfiles}
    >
      ▶ Review & Start
    </button>
  </div>
</div>

<style>
  .config-section {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .form-label {
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .form-textarea {
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
    resize: vertical;
    outline: none;
    background: white;
    color: #1f2937;
  }
  :global(.dark) .form-textarea {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-textarea:focus { border-color: #3b82f6; }

  .form-input {
    padding: 8px 10px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    width: 100px;
    outline: none;
    background: white;
    color: #1f2937;
  }
  :global(.dark) .form-input {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-input:focus { border-color: #3b82f6; }

  .settings-row {
    display: flex;
    gap: 16px;
  }

  .agent-nodes {
    display: flex;
    flex-direction: column;
    gap: 0;
    align-items: center;
  }

  .agent-node {
    width: 100%;
    padding: 16px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    border-top: 3px solid;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  :global(.dark) .agent-node {
    background: #1f2937;
    border-color: #374151;
  }

  .agent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .agent-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
  }
  .agent-icon { font-size: 16px; }

  .agent-desc {
    font-size: 12px;
    color: #9ca3af;
    margin: 0;
  }

  .agent-llm-select {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .select-label {
    font-size: 11px;
    font-weight: 500;
    color: #6b7280;
  }
  .form-select {
    padding: 8px 10px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 13px;
    background: white;
    color: #1f2937;
    outline: none;
    cursor: pointer;
  }
  :global(.dark) .form-select {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-select:focus { border-color: #3b82f6; }
  .select-loading {
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
  }

  .agent-arrow {
    font-size: 20px;
    color: #9ca3af;
    padding: 4px 0;
  }

  .actions-row {
    display: flex;
    justify-content: center;
  }

  .btn {
    padding: 10px 24px;
    border-radius: 8px;
    border: none;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-start {
    background: #3b82f6;
    color: white;
  }
  .btn-start:hover:not(:disabled) { background: #2563eb; }

  /* DMS Document Section */
  .dms-section {
    padding: 16px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  :global(.dark) .dms-section {
    background: #1f2937;
    border-color: #374151;
  }
  .dms-doc-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 140px;
    overflow-y: auto;
  }
  .dms-doc-item {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding: 4px 0;
  }
  .dms-checkbox {
    border-radius: 4px;
    border: 1px solid #d1d5db;
    accent-color: #3b82f6;
  }
  .dms-doc-name {
    font-size: 13px;
    color: #374151;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.dark) .dms-doc-name { color: #e5e7eb; }
  .dms-options {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 8px;
    border-top: 1px solid #e5e7eb;
  }
  :global(.dark) .dms-options { border-color: #374151; }
  .dms-option {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }
  .dms-debate-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 140px;
    overflow-y: auto;
    padding: 8px 10px;
    margin-top: 4px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }
  :global(.dark) .dms-debate-list {
    background: #111827;
    border-color: #374151;
  }
  .dms-debate-item {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding: 3px 0;
  }
  .dms-debate-name {
    font-size: 12px;
    color: #374151;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  :global(.dark) .dms-debate-name { color: #d1d5db; }

  .error-box {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 14px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    font-size: 13px;
    color: #991b1b;
  }
  :global(.dark) .error-box {
    background: #451a1a;
    border-color: #7f1d1d;
    color: #fca5a5;
  }
</style>
