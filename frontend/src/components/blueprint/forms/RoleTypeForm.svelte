<script>
  /**
   * RoleTypeForm — Inspector form for Role Type entities.
   *
   * Maps 1:1 to the RoleType Pydantic model.
   * Save: POST if draft, PUT if existing.
   */
  import { i18n } from '../../../lib/i18n/index.js';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import {
    createRoleType,
    updateRoleType,
    deleteRoleType,
  } from '../../../lib/blueprint/api.js';

  /** @type {{ node: any, onsave?: (data: any) => void, ondelete?: () => void }} */
  let { node, onsave = () => {}, ondelete = () => {} } = $props();

  let t = $derived((key) => $i18n[key] || key);

  let draft = $state({});
  let saving = $state(false);
  let error = $state(null);

  const presetColors = [
    { label: 'Violet', value: '#8b5cf6' },
    { label: 'Blue', value: '#3b82f6' },
    { label: 'Green', value: '#10b981' },
    { label: 'Amber', value: '#f59e0b' },
    { label: 'Rose', value: '#f43f5e' },
    { label: 'Cyan', value: '#06b6d4' },
    { label: 'Indigo', value: '#6366f1' },
    { label: 'Teal', value: '#14b8a6' },
  ];

  const presetIcons = ['🧠', '🔍', '⚡', '🎯', '👤', '🎭', '🛡️', '🔬', '📊', '💡', '⚙️', '🌟'];

  $effect(() => {
    if (node?.data) {
      draft = {
        id: node.data.blueprint_id || node.id,
        name: node.data.name || '',
        description: node.data.description || '',
        icon: node.data.icon || '👤',
        color: node.data.color || '#8b5cf6',
        default_max_rounds: node.data.default_max_rounds ?? 5,
        default_consensus_threshold: node.data.default_consensus_threshold ?? 0.9,
        tags: node.data.tags || [],
        is_active: node.data.is_active !== false,
      };
    }
  });

  async function handleSave() {
    saving = true;
    error = null;
    try {
      const payload = { ...draft };
      let result;
      if (node.data?.isDraft) {
        result = await createRoleType(payload);
      } else {
        result = await updateRoleType(payload.id, payload);
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
      await deleteRoleType(draft.id);
      canvasStore.removeNode(node.id);
      ondelete();
    } catch (err) {
      error = err.message;
    }
  }
</script>

<div class="form-container" data-testid="form-role-type">
  <div class="form-header">
    <span class="form-icon">{draft.icon || '👤'}</span>
    <span class="form-title">Role Type</span>
    {#if node?.data?.isDraft}
      <span class="draft-badge">{t('blueprint.inspector.draft')}</span>
    {/if}
  </div>

  {#if error}
    <div class="form-error">{error}</div>
  {/if}

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.name')}</span>
    <input type="text" bind:value={draft.name} class="field-input" data-testid="form-rt-name" />
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.description')}</span>
    <textarea bind:value={draft.description} class="field-textarea" rows="2" data-testid="form-rt-description"></textarea>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.icon') || 'Icon'}</span>
    <div class="icon-grid">
      {#each presetIcons as icon}
        <button
          class="icon-btn"
          class:selected={draft.icon === icon}
          onclick={() => { draft.icon = icon; }}
          type="button"
        >{icon}</button>
      {/each}
    </div>
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.color') || 'Color'}</span>
    <div class="color-grid">
      {#each presetColors as c}
        <button
          class="color-btn"
          class:selected={draft.color === c.value}
          style="background: {c.value};"
          onclick={() => { draft.color = c.value; }}
          title={c.label}
          type="button"
        ></button>
      {/each}
    </div>
    <input type="color" bind:value={draft.color} class="color-picker" data-testid="form-rt-color" />
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.maxRounds')}</span>
    <input type="number" bind:value={draft.default_max_rounds} min="1" step="1" class="field-input" data-testid="form-rt-max-rounds" />
  </label>

  <label class="form-field">
    <span class="field-label">{t('blueprint.form.consensusThreshold')}</span>
    <input type="number" bind:value={draft.default_consensus_threshold} min="0" max="1" step="0.05" class="field-input" data-testid="form-rt-threshold" />
  </label>

  <div class="form-actions">
    <button class="btn-save" onclick={handleSave} disabled={saving} data-testid="form-rt-save">
      {saving ? '...' : t('blueprint.inspector.save')}
    </button>
    <button class="btn-delete" onclick={handleDelete} data-testid="form-rt-delete">
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
  .icon-grid { display: flex; flex-wrap: wrap; gap: 4px; }
  .icon-btn {
    width: 32px; height: 32px; border: 2px solid transparent; border-radius: 6px;
    background: #f3f4f6; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: all 0.15s ease;
  }
  :global(.dark) .icon-btn { background: #374151; }
  .icon-btn:hover { border-color: #9ca3af; }
  .icon-btn.selected { border-color: #3b82f6; background: #eff6ff; }
  :global(.dark) .icon-btn.selected { background: #1e3a5f; }
  .color-grid { display: flex; flex-wrap: wrap; gap: 4px; }
  .color-btn {
    width: 24px; height: 24px; border: 2px solid transparent; border-radius: 4px;
    cursor: pointer; transition: all 0.15s ease;
  }
  .color-btn:hover { transform: scale(1.15); }
  .color-btn.selected { border-color: #1f2937; box-shadow: 0 0 0 2px white; }
  :global(.dark) .color-btn.selected { border-color: #e5e7eb; box-shadow: 0 0 0 2px #1f2937; }
  .color-picker { width: 100%; height: 30px; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; margin-top: 4px; }
  .form-actions { display: flex; gap: 8px; margin-top: 4px; }
  .btn-save { flex: 1; padding: 8px 12px; border: none; border-radius: 6px; background: #3b82f6; color: white; font-size: 13px; font-weight: 600; cursor: pointer; }
  .btn-save:hover { background: #2563eb; }
  .btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-delete { padding: 8px 12px; border: 1px solid #ef4444; border-radius: 6px; background: transparent; color: #ef4444; font-size: 13px; font-weight: 600; cursor: pointer; }
  .btn-delete:hover { background: #fef2f2; }
</style>
