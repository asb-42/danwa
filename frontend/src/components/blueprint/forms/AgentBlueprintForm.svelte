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
        tags: node.data.tags || [],
        is_active: node.data.is_active !== false,
      };
    }
  });

  // Load dropdown options
  $effect(() => {
    Promise.all([
      listBlueprintLLMProfiles(),
      listRoleDefinitions(),
      listPromptTemplates(),
    ]).then(([llm, roles, prompts]) => {
      llmProfiles = llm;
      roleDefinitions = roles;
      promptTemplates = prompts;
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
