<script>
  /**
   * TemplateGallery — Grid of workflow template cards.
   *
   * Shows system and custom templates with search, category filter,
   * and delete functionality for custom templates.
   */
  import { i18n } from '../../lib/i18n/index.js';
  import {
    listWorkflowTemplates,
    deleteWorkflowTemplate,
  } from '../../lib/blueprint/api.js';

  /** @type {{ visible?: boolean, onSelect?: Function, onClose?: Function }} */
  let { visible = false, onSelect = () => {}, onClose = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let templates = $state([]);
  let loading = $state(false);
  let error = $state(null);
  let searchQuery = $state('');
  let categoryFilter = $state('all'); // 'all' | 'system' | 'custom'
  let deleteConfirmId = $state(null);

  async function loadTemplates() {
    loading = true;
    error = null;
    try {
      const opts = {};
      if (categoryFilter !== 'all') opts.category = categoryFilter;
      templates = await listWorkflowTemplates(opts);
    } catch (e) {
      error = e.message || 'Failed to load templates';
    } finally {
      loading = false;
    }
  }

  // Load on visibility change
  $effect(() => {
    if (visible) loadTemplates();
  });

  let filteredTemplates = $derived(
    templates.filter((tmpl) => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        tmpl.name.toLowerCase().includes(q) ||
        tmpl.description.toLowerCase().includes(q) ||
        tmpl.tags.some((tag) => tag.toLowerCase().includes(q))
      );
    })
  );

  async function handleDelete(templateId) {
    try {
      await deleteWorkflowTemplate(templateId);
      templates = templates.filter((t) => t.id !== templateId);
      deleteConfirmId = null;
    } catch (e) {
      error = e.message || 'Failed to delete template';
    }
  }

  function handleSelect(template) {
    onSelect(template);
  }
</script>

{#if visible}
  <div class="gallery-overlay" role="dialog" aria-label={t('template.gallery.title')}>
    <div class="gallery-modal">
      <!-- Header -->
      <div class="gallery-header">
        <h2 class="gallery-title">{t('template.gallery.title')}</h2>
        <button class="close-btn" onclick={onClose} aria-label="Close">✕</button>
      </div>

      <!-- Search & Filter Bar -->
      <div class="gallery-toolbar">
        <input
          type="text"
          class="search-input"
          placeholder={t('template.gallery.searchPlaceholder')}
          bind:value={searchQuery}
          data-testid="template-search"
        />
        <div class="filter-tabs">
          <button
            class="filter-tab"
            class:active={categoryFilter === 'all'}
            onclick={() => { categoryFilter = 'all'; loadTemplates(); }}
          >
            {t('template.gallery.filterAll')}
          </button>
          <button
            class="filter-tab"
            class:active={categoryFilter === 'system'}
            onclick={() => { categoryFilter = 'system'; loadTemplates(); }}
          >
            {t('template.gallery.filterSystem')}
          </button>
          <button
            class="filter-tab"
            class:active={categoryFilter === 'custom'}
            onclick={() => { categoryFilter = 'custom'; loadTemplates(); }}
          >
            {t('template.gallery.filterCustom')}
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="gallery-content">
        {#if loading}
          <div class="gallery-loading">{t('template.gallery.loading')}</div>
        {:else if error}
          <div class="gallery-error">{error}</div>
        {:else if filteredTemplates.length === 0}
          <div class="gallery-empty">{t('template.gallery.empty')}</div>
        {:else}
          <div class="template-grid">
            <!-- Blank Canvas Card -->
            <button
              class="template-card blank-card"
              onclick={() => onSelect(null)}
              data-testid="template-blank-canvas"
            >
              <div class="card-icon">📄</div>
              <div class="card-name">{t('template.gallery.blankCanvas')}</div>
              <div class="card-desc">{t('template.gallery.blankCanvasDesc')}</div>
            </button>

            {#each filteredTemplates as tmpl (tmpl.id)}
              <div class="template-card" class:system={tmpl.is_system} data-testid="template-card-{tmpl.id}">
                <button class="card-select-btn" onclick={() => handleSelect(tmpl)}>
                  <div class="card-header">
                    <span class="card-icon">{tmpl.is_system ? '⭐' : '📋'}</span>
                    {#if tmpl.is_system}
                      <span class="system-badge">{t('template.gallery.systemBadge')}</span>
                    {/if}
                  </div>
                  <div class="card-name">{tmpl.name}</div>
                  <div class="card-desc">{tmpl.description}</div>
                  {#if tmpl.tags.length > 0}
                    <div class="card-tags">
                      {#each tmpl.tags as tag}
                        <span class="tag-badge">{tag}</span>
                      {/each}
                    </div>
                  {/if}
                  <div class="card-meta">
                    {tmpl.placeholders.length} {t('template.gallery.placeholders')}
                  </div>
                </button>
                {#if !tmpl.is_system}
                  {#if deleteConfirmId === tmpl.id}
                    <div class="delete-confirm">
                      <span>{t('template.gallery.confirmDelete')}</span>
                      <button class="btn-danger-sm" onclick={() => handleDelete(tmpl.id)}>
                        {t('template.gallery.yes')}
                      </button>
                      <button class="btn-secondary-sm" onclick={() => (deleteConfirmId = null)}>
                        {t('template.gallery.no')}
                      </button>
                    </div>
                  {:else}
                    <button
                      class="delete-btn"
                      onclick={() => (deleteConfirmId = tmpl.id)}
                      aria-label="Delete template"
                      data-testid="template-delete-{tmpl.id}"
                    >
                      🗑️
                    </button>
                  {/if}
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .gallery-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
  }

  .gallery-modal {
    background: var(--color-bg, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 12px;
    width: 90vw;
    max-width: 900px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .gallery-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border, #313244);
  }

  .gallery-title {
    font-size: 1.25rem;
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

  .gallery-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--color-border, #313244);
  }

  .search-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    background: var(--color-surface, #313244);
    color: var(--color-text, #cdd6f4);
    font-size: 0.875rem;
  }
  .search-input::placeholder {
    color: var(--color-text-muted, #6c7086);
  }

  .filter-tabs {
    display: flex;
    gap: 4px;
  }

  .filter-tab {
    padding: 6px 12px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    background: transparent;
    color: var(--color-text-muted, #6c7086);
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.15s;
  }
  .filter-tab.active {
    background: var(--color-primary, #89b4fa);
    color: var(--color-bg, #1e1e2e);
    border-color: var(--color-primary, #89b4fa);
  }
  .filter-tab:hover:not(.active) {
    background: var(--color-surface, #313244);
  }

  .gallery-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
  }

  .gallery-loading,
  .gallery-error,
  .gallery-empty {
    text-align: center;
    padding: 40px 20px;
    color: var(--color-text-muted, #6c7086);
    font-size: 0.9rem;
  }

  .gallery-error {
    color: var(--color-error, #f38ba8);
  }

  .template-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
  }

  .template-card {
    position: relative;
    border: 1px solid var(--color-border, #313244);
    border-radius: 8px;
    background: var(--color-surface, #313244);
    overflow: hidden;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .template-card:hover {
    border-color: var(--color-primary, #89b4fa);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }
  .template-card.system {
    border-color: var(--color-warning, #f9e2af);
  }

  .blank-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px 16px;
    cursor: pointer;
    border-style: dashed;
    background: transparent;
    width: 100%;
    text-align: center;
  }
  .blank-card:hover {
    border-color: var(--color-primary, #89b4fa);
    background: var(--color-surface, #313244);
  }

  .card-select-btn {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 16px;
    cursor: pointer;
    background: none;
    border: none;
    color: inherit;
    width: 100%;
    text-align: left;
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    width: 100%;
  }

  .card-icon {
    font-size: 1.5rem;
  }

  .system-badge {
    font-size: 0.65rem;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--color-warning, #f9e2af);
    color: var(--color-bg, #1e1e2e);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .card-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--color-text, #cdd6f4);
    margin-bottom: 4px;
  }

  .card-desc {
    font-size: 0.8rem;
    color: var(--color-text-muted, #6c7086);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 8px;
  }

  .card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }

  .tag-badge {
    font-size: 0.65rem;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--color-primary-alpha, rgba(137, 180, 250, 0.15));
    color: var(--color-primary, #89b4fa);
  }

  .card-meta {
    font-size: 0.75rem;
    color: var(--color-text-muted, #6c7086);
  }

  .delete-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.9rem;
    padding: 4px;
    border-radius: 4px;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .template-card:hover .delete-btn {
    opacity: 1;
  }
  .delete-btn:hover {
    background: var(--color-error-alpha, rgba(243, 139, 168, 0.15));
  }

  .delete-confirm {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 0.75rem;
    color: var(--color-error, #f38ba8);
    border-top: 1px solid var(--color-border, #313244);
  }

  .btn-danger-sm {
    padding: 2px 8px;
    border: 1px solid var(--color-error, #f38ba8);
    border-radius: 4px;
    background: var(--color-error, #f38ba8);
    color: var(--color-bg, #1e1e2e);
    font-size: 0.75rem;
    cursor: pointer;
  }

  .btn-secondary-sm {
    padding: 2px 8px;
    border: 1px solid var(--color-border, #313244);
    border-radius: 4px;
    background: transparent;
    color: var(--color-text-muted, #6c7086);
    font-size: 0.75rem;
    cursor: pointer;
  }
</style>
