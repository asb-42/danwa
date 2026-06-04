<script>
  /**
   * TemplateInstantiateModal — Dynamic form for template placeholder values.
   *
   * Renders form fields based on the template's placeholder definitions.
   * Supports: string, blueprint_ref (dropdown), integer, float.
   */
  import { tStore } from '../../lib/i18n/index.js';
  import {
    instantiateWorkflowTemplate,
    listAgentBlueprints,
    getWorkflowTemplate,
  } from '../../lib/blueprint/api.js';

  /** @type {{ templateId?: string|null, visible?: boolean, onSuccess?: Function, onClose?: Function }} */
  let { templateId = null, visible = false, onSuccess = () => {}, onClose = () => {} } = $props();

  let t = $derived($tStore);

  let workflowName = $state('');
  let placeholderValues = $state({});
  let blueprints = $state([]);
  let blueprintsLoading = $state(false);
  let loading = $state(false);
  let error = $state(null);

  // Load template data on demand — avoids reactivity on large template_data
  let templateName = $state('');
  let templatePlaceholders = $state([]);

  $effect(() => {
    if (templateId && visible) {
      workflowName = '';
      placeholderValues = {};
      error = null;
      templateName = '';
      templatePlaceholders = [];
      getWorkflowTemplate(templateId).then((tmpl) => {
        templateName = tmpl.name;
        templatePlaceholders = tmpl.placeholders || [];
        // Set defaults
        for (const ph of templatePlaceholders) {
          if (ph.default !== null && ph.default !== undefined) {
            placeholderValues[ph.key] = ph.default;
          }
        }
        // Load blueprints if any placeholder is blueprint_ref
        if (templatePlaceholders.some((p) => p.type === 'blueprint_ref')) {
          loadBlueprints();
        }
      }).catch(() => {
        error = 'Failed to load template';
      });
    }
  });

  async function loadBlueprints() {
    blueprintsLoading = true;
    try {
      blueprints = await listAgentBlueprints({ active_only: false });
    } catch (err) {
      if (import.meta.env.DEV) console.warn('[TemplateInstantiateModal] Failed to load blueprints:', err);
      blueprints = [];
    } finally {
      blueprintsLoading = false;
    }
  }

  async function handleInstantiate() {
    if (!templateId) return;
    loading = true;
    error = null;
    try {
      const wf = await instantiateWorkflowTemplate(templateId, {
        name: workflowName || undefined,
        placeholder_values: placeholderValues,
      });
      onSuccess(wf);
    } catch (e) {
      error = e.message || t('template.instantiate.error');
    } finally {
      loading = false;
    }
  }

  function handleValueChange(key, value, type) {
    if (type === 'integer') {
      placeholderValues[key] = parseInt(value, 10) || 0;
    } else if (type === 'float') {
      placeholderValues[key] = parseFloat(value) || 0;
    } else {
      placeholderValues[key] = value;
    }
  }
</script>

{#if visible && templateId}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="template-instantiate-title" onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}>
    <div class="modal-container" role="document" onclick={(e) => e.stopPropagation()}>
      <!-- Header -->
      <div class="modal-header">
        <div>
          <h2 id="template-instantiate-title" class="modal-title">{t('template.instantiate.title')}</h2>
          <p class="modal-subtitle">{templateName}</p>
        </div>
        <button class="close-btn" onclick={onClose} aria-label="Close">✕</button>
      </div>

      <!-- Form -->
      <div class="modal-body">
        <!-- Workflow Name -->
        <div class="form-field">
          <label class="field-label" for="wf-name">{t('template.instantiate.workflowName')}</label>
          <input
            id="wf-name"
            type="text"
            class="field-input"
            placeholder="{templateName} – {new Date().toISOString().slice(0, 16)}"
            bind:value={workflowName}
            data-testid="instantiate-name"
          />
        </div>

        <!-- Dynamic Placeholder Fields -->
        {#each templatePlaceholders as ph (ph.key)}
          <div class="form-field">
            <label class="field-label" for="ph-{ph.key}">
              {ph.key}
              {#if ph.type === 'blueprint_ref'}
                <span class="field-type-badge blueprint">blueprint_ref</span>
              {:else}
                <span class="field-type-badge">{ph.type}</span>
              {/if}
            </label>
            {#if ph.description}
              <p class="field-hint">{ph.description}</p>
            {/if}

            {#if ph.type === 'blueprint_ref'}
              <select
                id="ph-{ph.key}"
                class="field-select"
                value={placeholderValues[ph.key] || ''}
                onchange={(e) => handleValueChange(ph.key, e.target.value, ph.type)}
                data-testid="instantiate-ph-{ph.key}"
                disabled={blueprintsLoading}
              >
                {#if blueprintsLoading}
                  <option value="">Loading blueprints…</option>
                {:else if blueprints.length === 0}
                  <option value="">— No agent blueprints found —</option>
                {:else}
                  <option value="">{t('template.instantiate.selectBlueprint')}</option>
                  {#each blueprints as bp}
                    <option value={bp.id}>{bp.name} ({bp.id})</option>
                  {/each}
                {/if}
              </select>
            {:else if ph.type === 'integer'}
              <input
                id="ph-{ph.key}"
                type="number"
                step="1"
                class="field-input"
                value={placeholderValues[ph.key] ?? ''}
                placeholder={ph.default !== null ? String(ph.default) : ''}
                onchange={(e) => handleValueChange(ph.key, e.target.value, ph.type)}
                data-testid="instantiate-ph-{ph.key}"
              />
            {:else if ph.type === 'float'}
              <input
                id="ph-{ph.key}"
                type="number"
                step="0.1"
                class="field-input"
                value={placeholderValues[ph.key] ?? ''}
                placeholder={ph.default !== null ? String(ph.default) : ''}
                onchange={(e) => handleValueChange(ph.key, e.target.value, ph.type)}
                data-testid="instantiate-ph-{ph.key}"
              />
            {:else}
              <input
                id="ph-{ph.key}"
                type="text"
                class="field-input"
                value={placeholderValues[ph.key] ?? ''}
                placeholder={ph.default !== null ? String(ph.default) : ''}
                onchange={(e) => handleValueChange(ph.key, e.target.value, ph.type)}
                data-testid="instantiate-ph-{ph.key}"
              />
            {/if}
          </div>
        {/each}

        {#if error}
          <div class="form-error" data-testid="instantiate-error">{error}</div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="modal-footer">
        <button class="btn-secondary" onclick={onClose}>{t('template.instantiate.cancel')}</button>
        <button
          class="btn-primary"
          onclick={handleInstantiate}
          disabled={loading}
          data-testid="instantiate-submit"
        >
          {loading ? t('template.instantiate.creating') : t('template.instantiate.create')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 1001;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
  }

  .modal-container {
    background: var(--color-bg, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 12px;
    width: 90vw;
    max-width: 560px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border, #313244);
  }

  .modal-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--color-text, #cdd6f4);
    margin: 0;
  }

  .modal-subtitle {
    font-size: 0.85rem;
    color: var(--color-text-muted, #6c7086);
    margin: 4px 0 0;
  }

  .close-btn {
    background: none;
    border: none;
    color: var(--color-text-muted, #6c7086);
    font-size: 1.25rem;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
  }
  .close-btn:hover {
    background: var(--color-surface, #313244);
  }

  .modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .field-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--color-text, #cdd6f4);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .field-type-badge {
    font-size: 0.6rem;
    padding: 1px 5px;
    border-radius: 3px;
    background: var(--color-surface, #313244);
    color: var(--color-text-muted, #6c7086);
    text-transform: uppercase;
  }
  .field-type-badge.blueprint {
    background: rgba(137, 180, 250, 0.15);
    color: var(--color-primary, #89b4fa);
  }

  .field-hint {
    font-size: 0.75rem;
    color: var(--color-text-muted, #6c7086);
    margin: 0;
  }

  .field-input,
  .field-select {
    padding: 8px 12px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    background: var(--color-surface, #313244);
    color: var(--color-text, #cdd6f4);
    font-size: 0.875rem;
  }
  .field-input:focus,
  .field-select:focus {
    outline: none;
    border-color: var(--color-primary, #89b4fa);
  }
  .field-input::placeholder {
    color: var(--color-text-muted, #6c7086);
  }

  .form-error {
    padding: 8px 12px;
    border-radius: 6px;
    background: rgba(243, 139, 168, 0.1);
    border: 1px solid var(--color-error, #f38ba8);
    color: var(--color-error, #f38ba8);
    font-size: 0.85rem;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 20px;
    border-top: 1px solid var(--color-border, #313244);
  }

  .btn-secondary {
    padding: 8px 16px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    background: transparent;
    color: var(--color-text-muted, #6c7086);
    font-size: 0.875rem;
    cursor: pointer;
  }
  .btn-secondary:hover {
    background: var(--color-surface, #313244);
  }

  .btn-primary {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    background: var(--color-primary, #89b4fa);
    color: var(--color-bg, #1e1e2e);
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-primary:hover {
    opacity: 0.9;
  }
  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
