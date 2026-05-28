<script>
  import { i18n } from '../../lib/i18n/index.js';
  import { activeProject, userLanguage } from '../../lib/stores.js';

  let {
    config = {},
    agents = [],
    profiles = [],
    agentCores = [],
    argumentationPatterns = [],
    toneProfiles = [],
    promptModifiers = [],
    documents = [],
    error = '',
    onBack = () => {},
    onStart = () => {},
  } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });
</script>

<div class="confirm-section">
  <h3 class="confirm-title">{t('mvpDebate.confirm.title')}</h3>
  <p class="confirm-subtitle">{t('mvpDebate.confirm.subtitle')}</p>

  <div class="confirm-grid">
    <!-- Topic -->
    <div class="confirm-card">
      <span class="confirm-label">{t('mvpDebate.confirm.topic')}</span>
      <p class="confirm-value confirm-topic">{config.topic}</p>
    </div>

    <!-- Round & Threshold -->
    <div class="confirm-row">
      <div class="confirm-card">
        <span class="confirm-label">{t('mvpDebate.confirm.maxRounds')}</span>
        <span class="confirm-value confirm-number">{config.maxRounds}</span>
      </div>
      <div class="confirm-card">
        <span class="confirm-label">{t('mvpDebate.confirm.consensusThreshold')}</span>
        <span class="confirm-value confirm-number">{(config.threshold * 100).toFixed(0)}%</span>
      </div>
    </div>

    <!-- Agent → LLM Mapping -->
    <div class="confirm-card">
      <span class="confirm-label">{t('mvpDebate.confirm.agentLlmMapping')}</span>
      {#each agents as agent}
        {@const profile = profiles.find(p => p.id === config.llmAssignments[agent.role])}
        <div class="confirm-row-item">
          <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
          {#if profile?.model}
            <span class="confirm-llm-name">{profile.name} ({profile.model})</span>
          {:else}
            <span class="confirm-llm-name dimmed">{t('mvpDebate.confirm.autoAssigned')}</span>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Agent → Core Mapping -->
    <div class="confirm-card">
      <span class="confirm-label">{t('mvpDebate.confirm.agentCoreMapping')}</span>
      {#each agents as agent}
        {@const coreId = config.agentCoreAssignments[agent.role]}
        {@const core = agentCores.find(c => c.id === coreId)}
        <div class="confirm-row-item">
          <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
          {#if core}
            <span class="confirm-llm-name">{core.name}</span>
          {:else}
            <span class="confirm-llm-name dimmed">{t('mvpDebate.defaultBuiltIn')}</span>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Argumentation Patterns -->
    <div class="confirm-card">
      <span class="confirm-label">{t('mvpDebate.confirm.argumentationPatterns')}</span>
      {#each agents as agent}
        {@const patId = config.argumentationPatternAssignments[agent.role]}
        {@const pat = argumentationPatterns.find(p => p.id === patId)}
        <div class="confirm-row-item">
          <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
          {#if pat}
            <span class="confirm-llm-name">{pat.name}</span>
          {:else}
            <span class="confirm-llm-name dimmed">{t('mvpDebate.noneDefault')}</span>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Tone Profiles -->
    <div class="confirm-card">
      <span class="confirm-label">{t('mvpDebate.confirm.toneProfiles')}</span>
      {#each agents as agent}
        {@const toneId = config.toneProfileAssignments[agent.role]}
        {@const tp = toneProfiles.find(p => p.id === toneId)}
        <div class="confirm-row-item">
          <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
          {#if tp}
            <span class="confirm-llm-name">{tp.name}</span>
          {:else}
            <span class="confirm-llm-name dimmed">{t('mvpDebate.noneDefault')}</span>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Prompt Modifiers -->
    <div class="confirm-card">
      <span class="confirm-label">{t('mvpDebate.confirm.promptModifiers')}</span>
      {#each agents as agent}
        {@const modId = config.promptModifierAssignments[agent.role]}
        {@const mod = promptModifiers.find(p => p.id === modId)}
        <div class="confirm-row-item">
          <span class="confirm-role-badge" style="background: {agent.color}22; color: {agent.color}">{agent.label}</span>
          {#if mod}
            <span class="confirm-llm-name">{mod.name}</span>
          {:else}
            <span class="confirm-llm-name dimmed">{t('mvpDebate.noneDefault')}</span>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Web Search -->
    <div class="confirm-card">
      <span class="confirm-label">{t('mvpDebate.confirm.webSearch')}</span>
      <span class="confirm-value">
        {#if config.searchMode === 'required'}{t('mvpDebate.searchModeRequiredDesc')}
        {:else if config.searchMode === 'optional'}{t('mvpDebate.searchModeOptionalDesc')}
        {:else}{t('mvpDebate.searchModeOffDesc')}{/if}
      </span>
    </div>

    <!-- RAG / DMS Documents -->
    {#if config.selectedDocumentIds.length > 0}
      <div class="confirm-card">
        <span class="confirm-label">{t('mvpDebate.confirm.ragContext', { count: config.selectedDocumentIds.length, plural: config.selectedDocumentIds.length > 1 ? 's' : '' })}</span>
        <div class="confirm-value">
          {#each config.selectedDocumentIds as docId}
            {@const doc = documents.find(d => d.id === docId)}
            <span class="confirm-doc">{doc?.filename || docId}</span>
          {/each}
          {#if config.ragAutoRetrieve}<span class="confirm-badge">{t('mvpDebate.confirm.autoRetrieve')}</span>{/if}
          {#if config.includeDebateResults}<span class="confirm-badge">{t('mvpDebate.confirm.includeDebateResults')}</span>{/if}
        </div>
      </div>
    {/if}

    <!-- Language & Project -->
    <div class="confirm-row">
      <div class="confirm-card">
        <span class="confirm-label">{t('mvpDebate.confirm.debateLanguage')}</span>
        <span class="confirm-value">{($userLanguage || 'de').toUpperCase()}</span>
      </div>
      <div class="confirm-card">
        <span class="confirm-label">{t('mvpDebate.confirm.activeProject')}</span>
        <span class="confirm-value">{$activeProject?.name || '—'}</span>
      </div>
    </div>
  </div>

  {#if error}
    <div class="error-box" role="alert">
      <span class="error-icon">⚠️</span>
      <span class="error-text">{error}</span>
    </div>
  {/if}

  <div class="actions-row" style="gap: 12px;">
    <button class="btn btn-cancel" onclick={onBack}>
      ← {t('mvpDebate.confirm.backToEdit')}
    </button>
    <button class="btn btn-start" onclick={onStart}>
      ▶ {t('mvpDebate.confirm.startDebate')}
    </button>
  </div>
</div>

<style>
  .confirm-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 24px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
  }
  :global(.dark) .confirm-section {
    background: #1f2937;
    border-color: #374151;
  }
  .confirm-title {
    font-size: 18px;
    font-weight: 700;
    color: #1f2937;
    margin: 0;
  }
  :global(.dark) .confirm-title { color: #e5e7eb; }
  .confirm-subtitle {
    font-size: 13px;
    color: #6b7280;
    margin: 0;
  }
  .confirm-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .confirm-row {
    display: flex;
    gap: 12px;
  }
  .confirm-row .confirm-card { flex: 1; }
  .confirm-card {
    padding: 12px 16px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }
  :global(.dark) .confirm-card {
    background: #111827;
    border-color: #374151;
  }
  .confirm-label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }
  .confirm-value {
    font-size: 14px;
    color: #1f2937;
    word-break: break-word;
  }
  :global(.dark) .confirm-value { color: #e5e7eb; }
  .confirm-topic {
    font-size: 14px;
    font-weight: 500;
    line-height: 1.5;
  }
  .confirm-number {
    font-size: 20px;
    font-weight: 700;
    color: #3b82f6;
  }
  .confirm-llm-name {
    font-weight: 500;
    color: #3b82f6;
  }
  .confirm-doc {
    display: inline-block;
    padding: 2px 8px;
    margin: 2px 4px 2px 0;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    font-size: 12px;
    color: #1e40af;
  }
  :global(.dark) .confirm-doc {
    background: #1e3a5f;
    border-color: #2563eb;
    color: #93c5fd;
  }
  .confirm-badge {
    display: inline-block;
    padding: 2px 8px;
    margin-left: 6px;
    background: #dcfce7;
    border: 1px solid #86efac;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    color: #166534;
  }
  :global(.dark) .confirm-badge {
    background: #14532d;
    border-color: #16a34a;
    color: #4ade80;
  }

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
  .btn-cancel {
    background: #ef4444;
    color: white;
  }
  .btn-cancel:hover { background: #dc2626; }
</style>
