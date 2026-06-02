<script>
  /**
   * SaveAsTemplateDialog — Dialog for saving a workflow as a reusable template.
   *
   * Allows the user to specify name, description, and which fields
   * should be extracted as placeholders.
   */
  import { tStore } from '../../lib/i18n/index.js';
  import { saveWorkflowAsTemplate } from '../../lib/blueprint/api.js';

  /** @type {{ workflowId?: string|null, workflowData?: Object|null, visible?: boolean, onSuccess?: Function, onClose?: Function }} */
  let { workflowId = null, workflowData = null, visible = false, onSuccess = () => {}, onClose = () => {} } = $props();

  let t = $derived($tStore);

  let name = $state('');
  let description = $state('');
  let extractedPlaceholders = $state([]);
  let newPlaceholderKey = $state('');
  let loading = $state(false);
  let error = $state(null);

  // Suggest extractable fields from workflow data
  let suggestedFields = $derived(() => {
    if (!workflowData) return [];
    const fields = [];
    // Look for agent_blueprint_id fields in nodes
    if (workflowData.nodes) {
      for (const node of workflowData.nodes) {
        if (node.agent_blueprint_id) {
          fields.push({
            key: `${node.id}_blueprint_id`,
            label: `${node.label || node.id} → agent_blueprint_id`,
            value: node.agent_blueprint_id,
          });
        }
      }
    }
    return fields;
  });

  function addPlaceholder(key) {
    if (key && !extractedPlaceholders.includes(key)) {
      extractedPlaceholders = [...extractedPlaceholders, key];
    }
    newPlaceholderKey = '';
  }

  function removePlaceholder(key) {
    extractedPlaceholders = extractedPlaceholders.filter((p) => p !== key);
  }

  async function handleSave() {
    if (!workflowId || !name.trim()) return;
    loading = true;
    error = null;
    try {
      const template = await saveWorkflowAsTemplate(workflowId, {
        name: name.trim(),
        description: description.trim(),
        extracted_placeholders: extractedPlaceholders,
      });
      onSuccess(template);
    } catch (e) {
      error = e.message || t('template.saveAs.error');
    } finally {
      loading = false;
    }
  }
</script>

{#if visible}
  <div class="dialog-overlay" role="dialog" aria-label={t('template.saveAs.title')}>
    <div class="dialog-container">
      <!-- Header -->
      <div class="dialog-header">
        <h2 class="dialog-title">{t('template.saveAs.title')}</h2>
        <button class="close-btn" onclick={onClose} aria-label="Close">✕</button>
      </div>

      <!-- Body -->
      <div class="dialog-body">
        <div class="form-field">
          <label class="field-label" for="tmpl-name">{t('template.saveAs.name')}</label>
          <input
            id="tmpl-name"
            type="text"
            class="field-input"
            bind:value={name}
            placeholder={t('template.saveAs.namePlaceholder')}
            data-testid="save-as-template-name"
          />
        </div>

        <div class="form-field">
          <label class="field-label" for="tmpl-desc">{t('template.saveAs.description')}</label>
          <textarea
            id="tmpl-desc"
            class="field-textarea"
            bind:value={description}
            placeholder={t('template.saveAs.descriptionPlaceholder')}
            rows="3"
            data-testid="save-as-template-description"
          ></textarea>
        </div>

        <!-- Placeholder Extraction -->
        <div class="form-field">
          <span class="field-label">{t('template.saveAs.placeholders')}</span>
          <p class="field-hint">{t('template.saveAs.placeholdersHint')}</p>

          <!-- Suggested fields -->
          {#if suggestedFields().length > 0}
            <div class="suggested-fields">
              <span class="suggested-label">{t('template.saveAs.suggested')}:</span>
              {#each suggestedFields() as field}
                <button
                  class="suggested-chip"
                  class:added={extractedPlaceholders.includes(field.key)}
                  onclick={() => addPlaceholder(field.key)}
                  disabled={extractedPlaceholders.includes(field.key)}
                >
                  {field.label}
                  {#if extractedPlaceholders.includes(field.key)}
                    ✓
                  {/if}
                </button>
              {/each}
            </div>
          {/if}

          <!-- Manual add -->
          <div class="placeholder-add-row">
            <input
              type="text"
              class="field-input-sm"
              bind:value={newPlaceholderKey}
              placeholder={t('template.saveAs.addPlaceholder')}
              onkeydown={(e) => { if (e.key === 'Enter') addPlaceholder(newPlaceholderKey); }}
            />
            <button class="btn-add" onclick={() => addPlaceholder(newPlaceholderKey)}>+</button>
          </div>

          <!-- Current placeholders -->
          {#if extractedPlaceholders.length > 0}
            <div class="placeholder-list">
              {#each extractedPlaceholders as key}
                <span class="placeholder-chip">
                  {`{{${key}}}`}
                  <button class="chip-remove" onclick={() => removePlaceholder(key)}>✕</button>
                </span>
              {/each}
            </div>
          {/if}
        </div>

        {#if error}
          <div class="form-error">{error}</div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="dialog-footer">
        <button class="btn-secondary" onclick={onClose}>{t('template.saveAs.cancel')}</button>
        <button
          class="btn-primary"
          onclick={handleSave}
          disabled={loading || !name.trim()}
          data-testid="save-as-template-submit"
        >
          {loading ? t('template.saveAs.saving') : t('template.saveAs.save')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-overlay {
    position: fixed;
    inset: 0;
    z-index: 1001;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
  }

  .dialog-container {
    background: var(--color-bg, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 12px;
    width: 90vw;
    max-width: 520px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border, #313244);
  }

  .dialog-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--color-text, #cdd6f4);
    margin: 0;
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

  .dialog-body {
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
  }

  .field-hint {
    font-size: 0.75rem;
    color: var(--color-text-muted, #6c7086);
    margin: 0;
  }

  .field-input,
  .field-textarea {
    padding: 8px 12px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    background: var(--color-surface, #313244);
    color: var(--color-text, #cdd6f4);
    font-size: 0.875rem;
    font-family: inherit;
  }
  .field-input:focus,
  .field-textarea:focus {
    outline: none;
    border-color: var(--color-primary, #89b4fa);
  }
  .field-input::placeholder,
  .field-textarea::placeholder {
    color: var(--color-text-muted, #6c7086);
  }

  .suggested-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    margin-top: 4px;
  }

  .suggested-label {
    font-size: 0.75rem;
    color: var(--color-text-muted, #6c7086);
  }

  .suggested-chip {
    font-size: 0.75rem;
    padding: 3px 8px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 4px;
    background: transparent;
    color: var(--color-text-muted, #6c7086);
    cursor: pointer;
  }
  .suggested-chip:hover:not(:disabled) {
    border-color: var(--color-primary, #89b4fa);
    color: var(--color-primary, #89b4fa);
  }
  .suggested-chip.added {
    border-color: var(--color-success, #a6e3a1);
    color: var(--color-success, #a6e3a1);
    opacity: 0.7;
  }

  .placeholder-add-row {
    display: flex;
    gap: 6px;
    margin-top: 4px;
  }

  .field-input-sm {
    flex: 1;
    padding: 6px 10px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    background: var(--color-surface, #313244);
    color: var(--color-text, #cdd6f4);
    font-size: 0.8rem;
  }
  .field-input-sm:focus {
    outline: none;
    border-color: var(--color-primary, #89b4fa);
  }
  .field-input-sm::placeholder {
    color: var(--color-text-muted, #6c7086);
  }

  .btn-add {
    padding: 6px 12px;
    border: 1px solid var(--color-primary, #89b4fa);
    border-radius: 6px;
    background: transparent;
    color: var(--color-primary, #89b4fa);
    font-size: 1rem;
    cursor: pointer;
  }
  .btn-add:hover {
    background: var(--color-primary, #89b4fa);
    color: var(--color-bg, #1e1e2e);
  }

  .placeholder-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }

  .placeholder-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.75rem;
    font-family: monospace;
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(137, 180, 250, 0.15);
    color: var(--color-primary, #89b4fa);
  }

  .chip-remove {
    background: none;
    border: none;
    color: var(--color-text-muted, #6c7086);
    cursor: pointer;
    font-size: 0.7rem;
    padding: 0 2px;
  }
  .chip-remove:hover {
    color: var(--color-error, #f38ba8);
  }

  .form-error {
    padding: 8px 12px;
    border-radius: 6px;
    background: rgba(243, 139, 168, 0.1);
    border: 1px solid var(--color-error, #f38ba8);
    color: var(--color-error, #f38ba8);
    font-size: 0.85rem;
  }

  .dialog-footer {
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
