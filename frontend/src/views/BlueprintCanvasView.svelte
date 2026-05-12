<script>
  /**
   * BlueprintCanvasView — Main three-column layout for the Blueprint Canvas.
   *
   * Left: Palette (240px) | Center: BlueprintCanvas (flex-1) | Right: Inspector (320px, conditional)
   */
  import { i18n } from '../lib/i18n/index.js';
  import { canvasStore } from '../lib/blueprint/store.svelte.js';
  import {
    getCanvasLayout,
    createCanvasLayout,
    updateCanvasLayout,
    getAgentBlueprint,
    getBlueprintLLMProfile,
    getRoleDefinition,
    getPromptTemplate,
    runBlueprintImport,
    compileWorkflow,
    cloneWorkflow,
  } from '../lib/blueprint/api.js';

  import Palette from '../components/blueprint/Palette.svelte';
  import BlueprintCanvas from '../components/blueprint/BlueprintCanvas.svelte';
  import Inspector from '../components/blueprint/Inspector.svelte';
  import TemplateGallery from '../components/blueprint/TemplateGallery.svelte';
  import TemplateInstantiateModal from '../components/blueprint/TemplateInstantiateModal.svelte';
  import SaveAsTemplateDialog from '../components/blueprint/SaveAsTemplateDialog.svelte';

  /** @type {{ layoutId?: string|null, navigate?: function }} */
  let { layoutId = null, navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let selectedNode = $derived(canvasStore.selectedNode);
  let showSaveDialog = $state(false);
  let layoutName = $state('');
  let saveError = $state(null);

  // Template state
  let showTemplateGallery = $state(false);
  let showInstantiateModal = $state(false);
  let showSaveAsTemplate = $state(false);
  let selectedTemplate = $state(null);

  // Compile/Clone state
  let isCompiling = $state(false);
  let compileResult = $state(null);
  let compileError = $state('');
  let isCloning = $state(false);

  // Load layout if layoutId provided
  $effect(() => {
    if (layoutId) {
      loadLayout(layoutId);
    }
  });

  async function loadLayout(id) {
    canvasStore.isLoading = true;
    try {
      const layout = await getCanvasLayout(id);
      canvasStore.currentLayoutId = layout.id;
      canvasStore.currentLayoutName = layout.name;
      layoutName = layout.name;

      // Load entity data for each node
      const entityDataMap = {};
      const layoutData = layout.layout_json || { nodes: [], edges: [] };

      for (const node of layoutData.nodes || []) {
        const entityId = node.blueprint_id || node.id;
        if (entityId && !entityId.startsWith('draft-')) {
          try {
            let entity;
            switch (node.type) {
              case 'agent-blueprint':
                entity = await getAgentBlueprint(entityId);
                break;
              case 'llm-profile':
                entity = await getBlueprintLLMProfile(entityId);
                break;
              case 'role-definition':
                entity = await getRoleDefinition(entityId);
                break;
              case 'prompt-template':
                entity = await getPromptTemplate(entityId);
                break;
            }
            if (entity) entityDataMap[entityId] = entity;
          } catch (err) {
            console.warn(`[BlueprintCanvasView] Failed to load entity ${entityId}:`, err);
          }
        }
      }

      canvasStore.loadFromLayout(layoutData, entityDataMap);
    } catch (err) {
      canvasStore.error = err.message;
      console.error('[BlueprintCanvasView] Failed to load layout:', err);
    } finally {
      canvasStore.isLoading = false;
    }
  }

  async function handleSaveLayout() {
    saveError = null;

    // Force show save dialog if no layout ID or no layout name
    if (!canvasStore.currentLayoutId || !canvasStore.currentLayoutName) {
      showSaveDialog = true;
      return;
    }

    try {
      const layoutJson = canvasStore.toLayoutJson();
      await updateCanvasLayout(canvasStore.currentLayoutId, {
        name: canvasStore.currentLayoutName || 'Untitled Layout',
        layout_json: layoutJson,
      });
      canvasStore.isDirty = false;
    } catch (err) {
      saveError = err.message;
    }
  }

  function handleSaveAs() {
    layoutName = '';
    saveError = null;
    showSaveDialog = true;
  }

  async function handleSaveNewLayout() {
    saveError = null;
    if (!layoutName.trim()) {
      saveError = 'Layout name is required';
      return;
    }

    try {
      const layoutJson = canvasStore.toLayoutJson();
      const result = await createCanvasLayout({
        id: `layout-${crypto.randomUUID().slice(0, 8)}`,
        name: layoutName.trim(),
        layout_json: layoutJson,
      });
      canvasStore.currentLayoutId = result.id;
      canvasStore.currentLayoutName = result.name;
      canvasStore.isDirty = false;
      showSaveDialog = false;
    } catch (err) {
      saveError = err.message;
    }
  }

  async function handleLoadLayout(layout) {
    // Load layout directly instead of relying on hash navigation
    if (layout && layout.id) {
      await loadLayout(layout.id);
      window.location.hash = `#/blueprint/${layout.id}`;
    }
  }

  async function handleImport() {
    try {
      const result = await runBlueprintImport();
      console.log('[BlueprintCanvasView] Import result:', result);
    } catch (err) {
      console.error('[BlueprintCanvasView] Import failed:', err);
    }
  }

  // --- Template handlers ---
  function handleNewWorkflow() {
    showTemplateGallery = true;
  }

  function handleTemplateSelected(template) {
    showTemplateGallery = false;
    if (template === null) {
      // Blank canvas — do nothing special
      return;
    }
    selectedTemplate = template;
    showInstantiateModal = true;
  }

  function handleInstantiated(wf) {
    showInstantiateModal = false;
    selectedTemplate = null;
    // Navigate to the new workflow
    if (wf && wf.id) {
      navigate(`blueprint/workflow/${wf.id}`);
    }
  }

  function handleSaveAsTemplate() {
    showSaveAsTemplate = true;
  }

  function handleTemplateSaved(template) {
    showSaveAsTemplate = false;
    console.log('[BlueprintCanvasView] Template saved:', template);
  }

  async function handleCompile() {
    if (!canvasStore.currentLayoutId) return;
    isCompiling = true;
    compileResult = null;
    compileError = '';
    try {
      compileResult = await compileWorkflow(canvasStore.currentLayoutId);
    } catch (err) {
      compileError = err.message;
    } finally {
      isCompiling = false;
    }
  }

  async function handleClone() {
    if (!canvasStore.currentLayoutId) return;
    isCloning = true;
    try {
      const cloned = await cloneWorkflow(canvasStore.currentLayoutId);
      if (cloned && cloned.id) {
        navigate(`blueprint/${cloned.id}`);
      }
    } catch (err) {
      compileError = err.message;
    } finally {
      isCloning = false;
    }
  }
</script>

<div class="blueprint-canvas-view" data-testid="blueprint-canvas-view">
  <!-- Left: Palette -->
  <aside class="palette-column">
    <Palette onloadlayout={handleLoadLayout} />
  </aside>

  <!-- Center: Canvas -->
  <main class="canvas-column">
    <!-- Compile/Clone toolbar -->
    {#if canvasStore.currentLayoutId}
      <div class="absolute top-2 right-2 z-10 flex items-center gap-2">
        <button
          class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg
                 bg-emerald-600 text-white hover:bg-emerald-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleCompile}
          disabled={isCompiling}
          title={t('blueprint.workflow.compile')}
        >
          {#if isCompiling}
            <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          {:else}
            🔧
          {/if}
          {t('blueprint.workflow.compile')}
        </button>
        <button
          class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg
                 bg-indigo-600 text-white hover:bg-indigo-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleClone}
          disabled={isCloning}
          title={t('blueprint.workflow.clone')}
        >
          {#if isCloning}
            <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          {:else}
            📋
          {/if}
          {t('blueprint.workflow.clone')}
        </button>
      </div>
    {/if}

    <!-- Compile result display -->
    {#if compileResult}
      <div class="absolute top-12 right-2 z-10 w-80 p-3 rounded-lg shadow-lg border text-xs
                  {compileResult.valid
                    ? 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
                    : 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'}">
        <div class="flex items-center justify-between mb-1">
          <span class="font-semibold">
            {compileResult.valid ? '✓' : '✗'} {t('blueprint.workflow.compileResult')}
          </span>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" onclick={() => compileResult = null}>✕</button>
        </div>
        {#if compileResult.errors?.length > 0}
          <p class="font-semibold mt-1">{t('blueprint.workflow.errors')}:</p>
          <ul class="list-disc ml-4 mt-0.5">
            {#each compileResult.errors as err}
              <li>{err}</li>
            {/each}
          </ul>
        {/if}
        {#if compileResult.warnings?.length > 0}
          <p class="font-semibold mt-1">{t('blueprint.workflow.warnings')}:</p>
          <ul class="list-disc ml-4 mt-0.5">
            {#each compileResult.warnings as warn}
              <li>{warn}</li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}

    {#if compileError}
      <div class="absolute top-12 right-2 z-10 w-80 p-3 rounded-lg shadow-lg
                  bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800
                  text-xs text-red-800 dark:text-red-200">
        <div class="flex items-center justify-between">
          <span>{compileError}</span>
          <button class="text-gray-400 hover:text-gray-600" onclick={() => compileError = ''}>✕</button>
        </div>
      </div>
    {/if}

    <BlueprintCanvas
      onsave={handleSaveLayout}
      onsaveas={handleSaveAs}
      onnewworkflow={handleNewWorkflow}
      onsaveastemplate={handleSaveAsTemplate}
    />
  </main>

  <!-- Right: Inspector (conditional) -->
  {#if selectedNode}
    <aside class="inspector-column">
      <Inspector />
    </aside>
  {/if}
</div>

<!-- Template Gallery Modal -->
<TemplateGallery
  visible={showTemplateGallery}
  onSelect={handleTemplateSelected}
  onClose={() => { showTemplateGallery = false; }}
/>

<!-- Template Instantiate Modal -->
<TemplateInstantiateModal
  template={selectedTemplate}
  visible={showInstantiateModal}
  onSuccess={handleInstantiated}
  onClose={() => { showInstantiateModal = false; selectedTemplate = null; }}
/>

<!-- Save as Template Dialog -->
<SaveAsTemplateDialog
  workflowId={canvasStore.currentLayoutId}
  workflowData={canvasStore.toLayoutJson ? canvasStore.toLayoutJson() : null}
  visible={showSaveAsTemplate}
  onSuccess={handleTemplateSaved}
  onClose={() => { showSaveAsTemplate = false; }}
/>

<!-- Save dialog for new layouts -->
{#if showSaveDialog}
  <div class="dialog-overlay" role="button" tabindex="-1" onclick={() => { showSaveDialog = false; }} onkeydown={(e) => { if (e.key === 'Escape') showSaveDialog = false; }}>
    <div class="dialog" role="dialog" aria-modal="true" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === 'Enter') handleSaveNewLayout(); }}>
      <h3 class="dialog-title">{t('blueprint.canvas.saveLayout')}</h3>
      {#if saveError}
        <p class="dialog-error">{saveError}</p>
      {/if}
      <label class="dialog-field">
        <span class="dialog-label">Layout Name</span>
        <input
          type="text"
          bind:value={layoutName}
          class="dialog-input"
          placeholder="My Blueprint Layout"
          data-testid="save-layout-name"
        />
      </label>
      <div class="dialog-actions">
        <button class="dialog-btn-cancel" onclick={() => { showSaveDialog = false; }}>
          {t('blueprint.inspector.cancel')}
        </button>
        <button class="dialog-btn-save" onclick={handleSaveNewLayout} data-testid="save-layout-confirm">
          {t('blueprint.inspector.save')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .blueprint-canvas-view {
    display: flex;
    height: calc(100vh - 4rem);
    overflow: hidden;
  }
  .palette-column {
    width: 240px;
    min-width: 240px;
    border-right: 1px solid #e5e7eb;
    overflow-y: auto;
    background: #f9fafb;
  }
  :global(.dark) .palette-column {
    border-color: #374151;
    background: #111827;
  }
  .canvas-column {
    flex: 1;
    position: relative;
    overflow: hidden;
  }
  .inspector-column {
    width: 320px;
    min-width: 320px;
    border-left: 1px solid #e5e7eb;
    overflow-y: auto;
    background: white;
  }
  :global(.dark) .inspector-column {
    border-color: #374151;
    background: #1f2937;
  }

  /* Save dialog */
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .dialog {
    background: white;
    border-radius: 12px;
    padding: 24px;
    width: 360px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
  }
  :global(.dark) .dialog { background: #1f2937; }
  .dialog-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2937;
    margin-bottom: 16px;
  }
  :global(.dark) .dialog-title { color: #e5e7eb; }
  .dialog-error {
    font-size: 12px;
    color: #ef4444;
    margin-bottom: 8px;
  }
  .dialog-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 16px;
  }
  .dialog-label {
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
  }
  .dialog-input {
    padding: 8px 10px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
  }
  :global(.dark) .dialog-input {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .dialog-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  .dialog-btn-cancel {
    padding: 8px 16px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    background: transparent;
    color: #6b7280;
    font-size: 13px;
    cursor: pointer;
  }
  .dialog-btn-save {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    background: #3b82f6;
    color: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  .dialog-btn-save:hover { background: #2563eb; }
</style>
