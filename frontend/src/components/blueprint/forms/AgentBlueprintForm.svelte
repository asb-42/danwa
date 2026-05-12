<script>
  /**
   * AgentBlueprintForm — Inspector form for Agent Blueprint entities.
   *
   * Maps 1:1 to the AgentBlueprint Pydantic model.
   * Save: POST if draft, PUT if existing.
   */
  import { i18n } from '../../../lib/i18n/index.js';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import {
    createAgentBlueprint,
    updateAgentBlueprint,
    deleteAgentBlueprint,
    listBlueprintLLMProfiles,
    listRoleDefinitions,
    listPromptTemplates,
  } from '../../../lib/blueprint/api.js';

  /** @type {{ node: any, onsave?: (data: any) => void, ondelete?: () => void }} */
  let { node, onsave = () => {}, ondelete = () => {} } = $props();

  let t = $derived((key) => $i18n[key] || key);

  let draft = $state({});
  let saving = $state(false);
  let error = $state(null);

  // Dropdown options
  let llmProfiles = $state([]);
  let roleDefinitions = $state([]);
  let promptTemplates = $state([]);
  let mimoVoices = $state([]);

  // Initialize draft from node data
  $effect(() => {
    if (node?.data) {
      draft = {
        id: node.data.blueprint_id || node.id,
        name: node.data.name || '',
        description: node.data.description || '',
        llm_profile_id: node.data.llm_profile_id || '',
        role_definition_id: node.data.role_definition_id || '',
        prompt_template_id: node.data.prompt_template_id || null,
        tts_voice_id: node.data.tts_voice_id || null,
        tags: node.data.tags || [],
        is_active: node.data.is_active !== false,
      };
    }
  });

  // Real-time sync: push draft changes back to canvas store
  $effect(() => {
    if (node?.id && draft.name !== undefined) {
      canvasStore.updateNodeData(node.id, {
        name: draft.name,
        description: draft.description,
        tags: draft.tags,
        is_active: draft.is_active,
      });
    }
  });

  // Load dropdown options
  $effect(() => {
    Promise.all([
      listBlueprintLLMProfiles(),
      listRoleDefinitions(),
      listPromptTemplates(),
      fetch('/api/v1/tts-voices?engine=mimo_tts').then(r => r.json()).catch(() => []),
    ]).then(([llm, roles, prompts, voices]) => {
      llmProfiles = llm;
      roleDefinitions = roles;
      promptTemplates = prompts;
      mimoVoices = voices;
    }).catch(() => {});
  });

  async function handleSave() {
    saving = true;
    error = null;
    try {
      const payload = { ...draft };
      let result;
      if (node.data?.isDraft) {
        result = await createAgentBlueprint(payload);
      } else {
        result = await updateAgentBlueprint(payload.id, payload);
      }
      canvasStore.updateNodeData(node.id, { ...result, isDraft: false, blueprint_id: result.id });
      onsave(result);
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  }

  async function handleDelete() {
    if (node.data?.isDraft) {
      canvasStore.removeNode(node.id);
      ondelete();
      return;
    }
    try {
      await deleteAgentBlueprint(draft.id);
      canvasStore.removeNode(node.id);
      ondelete();
    } catch (err) {
      error = err.message;
    }
  }
  // Connected entities (resolved from edges)
  let connectedLLMProfile = $state(null);
  let connectedRoleDefinition = $state(null);
  let connectedPromptTemplate = $state(null);

  // Resolve connected entities from canvas edges
  $effect(() => {
    if (!node?.id || typeof window === 'undefined') return;
    const edges = canvasStore.edges;
    const nodes = canvasStore.nodes;

    // uses_llm edge: agent-blueprint (source) → llm-profile (target)
    const llmEdge = edges.find(
      (e) => e.source === node.id && e.type === 'uses_llm'
    );
    if (llmEdge) {
      const llmNode = nodes.find((n) => n.id === llmEdge.target);
      connectedLLMProfile = llmNode?.data || null;
    } else {
      connectedLLMProfile = null;
    }

    // implements_role edge: this → RoleDefinition
    const roleEdge = edges.find(
      (e) => e.source === node.id && e.type === 'implements_role'
    );
    if (roleEdge) {
      const rdNode = nodes.find((n) => n.id === roleEdge.target);
      connectedRoleDefinition = rdNode?.data || null;
    } else {
      connectedRoleDefinition = null;
    }

    // overrides_prompt edge: this → PromptTemplate
    const promptEdge = edges.find(
      (e) => e.source === node.id && e.type === 'overrides_prompt'
    );
    if (promptEdge) {
      const ptNode = nodes.find((n) => n.id === promptEdge.target);
      connectedPromptTemplate = ptNode?.data || null;
    } else {
      connectedPromptTemplate = null;
    }
  });

  // Effective config: merge connected entities into a summary
  let effectiveConfig = $derived.by(() => {
    const config = {};
    if (connectedLLMProfile) {
      config.llm = {
        name: connectedLLMProfile.name || connectedLLMProfile.id,
        model: connectedLLMProfile.model || '',
        provider: connectedLLMProfile.provider || '',
      };
    }
    if (connectedRoleDefinition) {
      config.role = {
        name: connectedRoleDefinition.name || connectedRoleDefinition.id,
        role_type_id: connectedRoleDefinition.role_type_id || '',
        max_rounds: connectedRoleDefinition.max_rounds ?? 5,
        consensus_threshold: connectedRoleDefinition.consensus_threshold ?? 0.9,
      };
    }
    if (connectedPromptTemplate) {
      config.prompt = {
        name: connectedPromptTemplate.name || connectedPromptTemplate.id,
        role: connectedPromptTemplate.role || '',
        variant: connectedPromptTemplate.variant || 'default',
      };
    }
    return config;
  });
</script>

<div class="form-container" data-testid="form-agent-blueprint">
  <div class="form-header">
    <span class="form-icon">🤖</span>
    <span class="form-title">Agent Blueprint</span>
    {#if node?.data?.isDraft}
      <span class="draft-badge">{t('blueprint.inspector.draft')}</span>
    {/if}
  </div>

  {#if error}
    <div class="form-error">{error}</div>
  {/if}

  <!-- Connected entities summary -->
  {#if connectedLLMProfile || connectedRoleDefinition || connectedPromptTemplate}
    <div class="connections-section">
      <span class="connections-label">{t('blueprint.inspector.connections') || 'Connections'}</span>
      {#if connectedLLMProfile}
        <div class="connection-item">
          <span class="connection-edge">uses_llm →</span>
          <span class="connection-entity">⚡ {connectedLLMProfile.name || connectedLLMProfile.id}</span>
          {#if connectedLLMProfile.model}
            <span class="connection-detail">({connectedLLMProfile.model})</span>
          {/if}
        </div>
      {/if}
      {#if connectedRoleDefinition}
        <div class="connection-item">
          <span class="connection-edge">implements_role →</span>
          <span class="connection-entity">👤 {connectedRoleDefinition.name || connectedRoleDefinition.id}</span>
        </div>
      {/if}
      {#if connectedPromptTemplate}
        <div class="connection-item">
          <span class="connection-edge">overrides_prompt →</span>
          <span class="connection-entity">📝 {connectedPromptTemplate.name || connectedPromptTemplate.id}</span>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Effective config summary -->
  {#if Object.keys(effectiveConfig).length > 0}
    <div class="effective-config-section">
      <span class="effective-config-label">{t('blueprint.inspector.effectiveConfig') || 'Effective Config'}</span>
      {#if effectiveConfig.llm}
        <div class="config-row">
          <span class="config-key">LLM</span>
          <span class="config-value">{effectiveConfig.llm.name} ({effectiveConfig.llm.provider})</span>
        </div>
      {/if}
      {#if effectiveConfig.role}
        <div class="config-row">
          <span class="config-key">Role</span>
          <span class="config-value">{effectiveConfig.role.name} · {effectiveConfig.role.max_rounds} rounds · {(effectiveConfig.role.consensus_threshold * 100).toFixed(0)}%</span>
        </div>
      {/if}
      {#if effectiveConfig.prompt}
        <div class="config-row">
          <span class="config-key">Prompt</span>
          <span class="config-value">{effectiveConfig.prompt.name} ({effectiveConfig.prompt.variant})</span>
        </div>
      {/if}
    </div>
  {/if}

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.name')}</span>
    <input
      type="text"
      bind:value={draft.name}
      class="field-input"
      data-testid="form-ab-name"
    />
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.description')}</span>
    <textarea
      bind:value={draft.description}
      class="field-textarea"
      rows="2"
      data-testid="form-ab-description"
    ></textarea>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.llmProfile')}</span>
    <select bind:value={draft.llm_profile_id} class="field-select" data-testid="form-ab-llm">
      <option value="">-- Select --</option>
      {#each llmProfiles as profile}
        <option value={profile.id}>{profile.name}</option>
      {/each}
    </select>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.roleDefinition')}</span>
    <select bind:value={draft.role_definition_id} class="field-select" data-testid="form-ab-role">
      <option value="">-- Select --</option>
      {#each roleDefinitions as role}
        <option value={role.id}>{role.name}</option>
      {/each}
    </select>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.promptTemplate')}</span>
    <select bind:value={draft.prompt_template_id} class="field-select" data-testid="form-ab-prompt">
      <option value={null}>-- None --</option>
      {#each promptTemplates as tmpl}
        <option value={tmpl.id}>{tmpl.name}</option>
      {/each}
    </select>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.ttsVoice') || 'TTS Voice'}</span>
    <select bind:value={draft.tts_voice_id} class="field-select" data-testid="form-ab-voice">
      <option value={null}>-- Default --</option>
      {#each mimoVoices as voice}
        <option value={voice.voice_id}>{voice.name} ({voice.gender})</option>
      {/each}
    </select>
    <span class="field-hint">MiMo TTS voice for audio export</span>
  </label>

  <div class="form-actions">
    <button class="btn-save" onclick={handleSave} disabled={saving} data-testid="form-ab-save">
      {saving ? '...' : t('blueprint.inspector.save')}
    </button>
    <button class="btn-delete" onclick={handleDelete} data-testid="form-ab-delete">
      {t('blueprint.inspector.delete')}
    </button>
  </div>
</div>

<style>
  .form-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
  }
  .form-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .form-icon { font-size: 18px; }
  .form-title {
    font-weight: 700;
    font-size: 14px;
    color: #1f2937;
  }
  :global(.dark) .form-title { color: #e5e7eb; }
  .draft-badge {
    font-size: 9px;
    background: #f59e0b;
    color: white;
    padding: 1px 6px;
    border-radius: 8px;
    font-weight: 600;
  }
  .form-error {
    font-size: 12px;
    color: #ef4444;
    background: #fef2f2;
    padding: 6px 8px;
    border-radius: 6px;
  }
  .connections-section {
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  :global(.dark) .connections-section {
    background: #0c2d48;
    border-color: #1e3a5f;
  }
  .connections-label {
    font-size: 10px;
    font-weight: 700;
    color: #0369a1;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  :global(.dark) .connections-label { color: #7dd3fc; }
  .connection-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }
  .connection-edge {
    font-size: 10px;
    color: #6b7280;
    font-family: monospace;
    white-space: nowrap;
  }
  .connection-entity {
    color: #1f2937;
    font-weight: 500;
  }
  :global(.dark) .connection-entity { color: #e5e7eb; }
  .connection-detail {
    font-size: 10px;
    color: #9ca3af;
  }
  .effective-config-section {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  :global(.dark) .effective-config-section {
    background: #052e16;
    border-color: #14532d;
  }
  .effective-config-label {
    font-size: 10px;
    font-weight: 700;
    color: #15803d;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  :global(.dark) .effective-config-label { color: #4ade80; }
  .config-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }
  .config-key {
    font-size: 10px;
    font-weight: 600;
    color: #6b7280;
    min-width: 32px;
    text-transform: uppercase;
  }
  .config-value {
    color: #1f2937;
    font-weight: 500;
  }
  :global(.dark) .config-value { color: #e5e7eb; }
  .form-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .field-label {
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .field-input, .field-select, .field-textarea {
    padding: 6px 8px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 13px;
    background: white;
    color: #1f2937;
  }
  :global(.dark) .field-input,
  :global(.dark) .field-select,
  :global(.dark) .field-textarea {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .field-textarea { resize: vertical; }
  .field-hint {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 2px;
  }
  :global(.dark) .field-hint { color: #6b7280; }
  .form-actions {
    display: flex;
    gap: 8px;
    margin-top: 4px;
  }
  .btn-save {
    flex: 1;
    padding: 8px 12px;
    border: none;
    border-radius: 6px;
    background: #3b82f6;
    color: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s ease;
  }
  .btn-save:hover { background: #2563eb; }
  .btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-delete {
    padding: 8px 12px;
    border: 1px solid #ef4444;
    border-radius: 6px;
    background: transparent;
    color: #ef4444;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .btn-delete:hover {
    background: #fef2f2;
  }
</style>
