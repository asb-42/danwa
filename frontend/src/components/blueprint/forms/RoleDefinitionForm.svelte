<script>
  /**
   * RoleDefinitionForm — Inspector form for Role Definition entities.
   *
   * Maps 1:1 to the RoleDefinition Pydantic model.
   */
  import { i18n } from '../../../lib/i18n/index.js';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import {
    createRoleDefinition,
    updateRoleDefinition,
    deleteRoleDefinition,
    listPromptTemplates,
    listRoleTypes,
  } from '../../../lib/blueprint/api.js';

  /** @type {{ node: any, onsave?: (data: any) => void, ondelete?: () => void }} */
  let { node, onsave = () => {}, ondelete = () => {} } = $props();

  let t = $derived((key) => $i18n[key] || key);

  let draft = $state({});
  let saving = $state(false);
  let error = $state(null);
  let promptTemplates = $state([]);

  let roleTypes = $state([]);

  $effect(() => {
    if (node?.data) {
      draft = {
        id: node.data.blueprint_id || node.id,
        name: node.data.name || '',
        role_type_id: node.data.role_type_id || node.data.role || 'strategist',
        description: node.data.description || '',
        prompt_template_id: node.data.prompt_template_id || null,
        max_rounds: node.data.max_rounds ?? 3,
        consensus_threshold: node.data.consensus_threshold ?? 0.7,
        tags: node.data.tags || [],
      };
    }
  });

  $effect(() => {
    listPromptTemplates().then((t) => { promptTemplates = t; }).catch(() => {});
    listRoleTypes().then((rt) => { roleTypes = rt; }).catch(() => {});
  });

  async function handleSave() {
    saving = true;
    error = null;
    try {
      const payload = { ...draft };
      let result;
      if (node.data?.isDraft) {
        result = await createRoleDefinition(payload);
      } else {
        result = await updateRoleDefinition(payload.id, payload);
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
      await deleteRoleDefinition(draft.id);
      canvasStore.removeNode(node.id);
      ondelete();
    } catch (err) {
      error = err.message;
    }
  }
</script>

<div class="form-container" data-testid="form-role-definition">
  <div class="form-header">
    <span class="form-icon">👤</span>
    <span class="form-title">Role Definition</span>
    {#if node?.data?.isDraft}
      <span class="draft-badge">{t('blueprint.inspector.draft')}</span>
    {/if}
  </div>

  {#if error}
    <div class="form-error">{error}</div>
  {/if}

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.name')}</span>
    <input type="text" bind:value={draft.name} class="field-input" data-testid="form-rd-name" />
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.role')}</span>
    <select bind:value={draft.role} class="field-select" data-testid="form-rd-role">
      {#each roles as r}
        <option value={r}>{r}</option>
      {/each}
    </select>
    <span class="field-hint">{t('blueprint.form.roleHint')}</span>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.description')}</span>
    <textarea bind:value={draft.description} class="field-textarea" rows="2" data-testid="form-rd-description"></textarea>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.promptTemplate')}</span>
    <select bind:value={draft.prompt_template_id} class="field-select" data-testid="form-rd-prompt">
      <option value={null}>-- None --</option>
      {#each promptTemplates as tmpl}
        <option value={tmpl.id}>{tmpl.name}</option>
      {/each}
    </select>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.consensusThreshold')}</span>
    <input type="number" bind:value={draft.consensus_threshold} min="0" max="1" step="0.05" class="field-input" data-testid="form-rd-threshold" />
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.maxRounds')}</span>
    <input type="number" bind:value={draft.max_rounds} min="1" step="1" class="field-input" data-testid="form-rd-max-rounds" />
  </label>

  <div class="form-actions">
    <button class="btn-save" onclick={handleSave} disabled={saving} data-testid="form-rd-save">
      {saving ? '...' : t('blueprint.inspector.save')}
    </button>
    <button class="btn-delete" onclick={handleDelete} data-testid="form-rd-delete">
      {t('blueprint.inspector.delete')}
    </button>
  </div>
</div>

<style>
  .form-container { display: flex; flex-direction: column; gap: 12px; padding: 16px; }
  .form-header { display: flex; align-items: center; gap: 8px; }
  .form-icon { font-size: 18px; }
  .form-title { font-weight: 700; font-size: 14px; color: #1f2937; }
  :global(.dark) .form-title { color: #e5e7eb; }
  .draft-badge { font-size: 9px; background: #f59e0b; color: white; padding: 1px 6px; border-radius: 8px; font-weight: 600; }
  .form-error { font-size: 12px; color: #ef4444; background: #fef2f2; padding: 6px 8px; border-radius: 6px; }
  .form-field { display: flex; flex-direction: column; gap: 4px; }
  .field-label { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.03em; }
  .field-hint { font-size: 10px; color: #9ca3af; font-style: italic; }
  :global(.dark) .field-hint { color: #6b7280; }
  .field-input, .field-select, .field-textarea { padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; background: white; color: #1f2937; }
  :global(.dark) .field-input, :global(.dark) .field-select, :global(.dark) .field-textarea { background: #1f2937; border-color: #4b5563; color: #e5e7eb; }
  .field-textarea { resize: vertical; }
  .form-actions { display: flex; gap: 8px; margin-top: 4px; }
  .btn-save { flex: 1; padding: 8px 12px; border: none; border-radius: 6px; background: #3b82f6; color: white; font-size: 13px; font-weight: 600; cursor: pointer; }
  .btn-save:hover { background: #2563eb; }
  .btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-delete { padding: 8px 12px; border: 1px solid #ef4444; border-radius: 6px; background: transparent; color: #ef4444; font-size: 13px; font-weight: 600; cursor: pointer; }
  .btn-delete:hover { background: #fef2f2; }
</style>
