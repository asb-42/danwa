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
  import { getRoleDefinition, getAgentBlueprint } from '../../../lib/blueprint/api.js';

  /** @type {{ node: any, onsave?: (data: any) => void, ondelete?: () => void }} */
  let { node, onsave = () => {}, ondelete = () => {} } = $props();

  let t = $derived((key) => $i18n[key] || key);

  let draft = $state({});
  let saving = $state(false);
  let error = $state(null);
  let promptTemplates = $state([]);

  let roleTypes = $state([]);

  // Connected entities (resolved from edges)
  let connectedRoleType = $state(null);
  let connectedAgentBlueprints = $state([]);

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

  // Real-time sync: push draft changes back to canvas store
  $effect(() => {
    if (node?.id && draft.name !== undefined) {
      canvasStore.updateNodeData(node.id, {
        name: draft.name,
        description: draft.description,
        role: draft.role,
        max_rounds: draft.max_rounds,
        consensus_threshold: draft.consensus_threshold,
      });
    }
  });

  $effect(() => {
    listPromptTemplates().then((t) => { promptTemplates = t; }).catch(() => {});
    listRoleTypes().then((rt) => { roleTypes = rt; }).catch(() => {});
  });

  // Resolve connected entities from canvas edges
  $effect(() => {
    if (!node?.id || typeof window === 'undefined') return;
    const edges = canvasStore.edges;
    const nodes = canvasStore.nodes;

    // Find connected RoleType (defines_role edge: RoleType → this)
    const roleTypeEdge = edges.find(
      (e) => e.target === node.id && e.type === 'defines_role'
    );
    if (roleTypeEdge) {
      const rtNode = nodes.find((n) => n.id === roleTypeEdge.source);
      if (rtNode) {
        connectedRoleType = rtNode.data;
      } else {
        connectedRoleType = null;
      }
    } else {
      connectedRoleType = null;
    }

    // Find connected AgentBlueprints (implements_role edge: this → AgentBlueprint)
    const agentEdges = edges.filter(
      (e) => e.source === node.id && e.type === 'implements_role'
    );
    connectedAgentBlueprints = agentEdges
      .map((e) => nodes.find((n) => n.id === e.target))
      .filter(Boolean)
      .map((n) => n.data);
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

  <!-- Connected entities summary -->
  {#if connectedRoleType || connectedAgentBlueprints.length > 0}
    <div class="connections-section">
      <span class="connections-label">{t('blueprint.inspector.connections') || 'Connections'}</span>
      {#if connectedRoleType}
        <div class="connection-item">
          <span class="connection-edge">defines_role →</span>
          <span class="connection-entity">{connectedRoleType.icon || '👤'} {connectedRoleType.name || connectedRoleType.id}</span>
        </div>
      {/if}
      {#if connectedAgentBlueprints.length > 0}
        {#each connectedAgentBlueprints as agent}
          <div class="connection-item">
            <span class="connection-edge">implements_role ←</span>
            <span class="connection-entity">🤖 {agent.name || agent.id}</span>
          </div>
        {/each}
      {/if}
    </div>
  {/if}

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.name')}</span>
    <input type="text" bind:value={draft.name} class="field-input" data-testid="form-rd-name" />
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.roleType') || 'Role Type'}</span>
    <select bind:value={draft.role_type_id} class="field-select" data-testid="form-rd-role-type">
      {#each roleTypes as rt}
        <option value={rt.id}>{rt.icon || '👤'} {rt.name}</option>
      {/each}
    </select>
    <span class="field-hint">{t('blueprint.form.roleTypeHint') || 'Determines the behavioral category'}</span>
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
  .form-actions { display: flex; gap: 8px; margin-top: 4px; }
  .btn-save { flex: 1; padding: 8px 12px; border: none; border-radius: 6px; background: #3b82f6; color: white; font-size: 13px; font-weight: 600; cursor: pointer; }
  .btn-save:hover { background: #2563eb; }
  .btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-delete { padding: 8px 12px; border: 1px solid #ef4444; border-radius: 6px; background: transparent; color: #ef4444; font-size: 13px; font-weight: 600; cursor: pointer; }
  .btn-delete:hover { background: #fef2f2; }
</style>
