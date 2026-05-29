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
    convertLayoutToWorkflow,
    getWorkflowDefinition,
  } from '../lib/blueprint/api.js';
  import { startWorkflow } from '../lib/workflowExec.js';

  import Palette from '../components/blueprint/Palette.svelte';
  import BlueprintCanvas from '../components/blueprint/BlueprintCanvas.svelte';
  import Inspector from '../components/blueprint/Inspector.svelte';
  import TemplateGallery from '../components/blueprint/TemplateGallery.svelte';
  import TemplateInstantiateModal from '../components/blueprint/TemplateInstantiateModal.svelte';
  import SaveAsTemplateDialog from '../components/blueprint/SaveAsTemplateDialog.svelte';
  import RunWorkflowDialog from '../components/blueprint/RunWorkflowDialog.svelte';
  import ExecutionPanel from '../components/blueprint/ExecutionPanel.svelte';

  /** @type {{ layoutId?: string|null, routeParams?: string[], navigate?: function }} */
  let { layoutId = null, routeParams = [], navigate = () => {} } = $props();

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
  let selectedTemplateId = $state(null);

  // Compile/Clone state
  let isCompiling = $state(false);
  let compileResult = $state(null);
  let compileError = $state('');
  let isCloning = $state(false);

  // "Save as Workflow" state
  let showWorkflowDialog = $state(false);
  let isConverting = $state(false);
  let workflowName = $state('');
  let workflowDescription = $state('');
  let workflowMaxRounds = $state(5);
  let workflowConsensus = $state(0.9);
  let convertError = $state(null);
  let convertSuccess = $state(null);

  // "Run Debate" state
  let showRunDialog = $state(false);
  let showExecutionPanel = $state(false);
  let executionSessionId = $state(null);
  let executionContext = $state('');
  let executionOptions = $state({});

  // Load layout or workflow if layoutId provided
  $effect(() => {
    if (layoutId) {
      if (layoutId === 'wf' && routeParams[1]) {
        loadWorkflow(routeParams[1]);
      } else if (layoutId !== 'wf') {
        loadLayout(layoutId);
      }
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
      const layoutData = layout.layout_data || { nodes: [], edges: [] };

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

  async function loadWorkflow(wfId) {
    canvasStore.isLoading = true;
    try {
      const wf = await getWorkflowDefinition(wfId);
      canvasStore.reset();
      canvasStore.currentWorkflowId = wf.id;
      canvasStore.currentLayoutName = wf.name;

      const layoutData = {
        nodes: (wf.nodes || []).map((n) => ({
          id: n.id,
          type: n.type,
          x: n.position?.x ?? 0,
          y: n.position?.y ?? 0,
          blueprint_id: n.agent_blueprint_id || n.bundle_id || n.id,
          label: n.label || '',
          config: n.config || {},
          parent_id: n.parent_id || null,
        })),
        edges: (wf.edges || []).map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          type: e.type,
          data: {},
        })),
      };
      canvasStore.loadFromLayout(layoutData, {});
      canvasStore.setMode('workflow');
    } catch (err) {
      canvasStore.error = err.message;
      console.error('[BlueprintCanvasView] Failed to load workflow:', err);
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
        layout_data: layoutJson,
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
        layout_data: layoutJson,
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
    selectedTemplateId = template.id;
    showInstantiateModal = true;
  }

  function handleInstantiated(wf) {
    showInstantiateModal = false;
    selectedTemplateId = null;
    if (wf && wf.id) {
      // Convert WorkflowDefinition to canvas layout format and load directly
      canvasStore.reset();
      canvasStore.currentWorkflowId = wf.id;
      canvasStore.currentLayoutName = wf.name;

      // Convert WorkflowDefinition nodes/edges to layout format
      const layoutData = {
        nodes: (wf.nodes || []).map((n) => ({
          id: n.id,
          type: n.type,
          x: n.position?.x ?? 0,
          y: n.position?.y ?? 0,
          blueprint_id: n.agent_blueprint_id || n.bundle_id || n.id,
          label: n.label || '',
          config: n.config || {},
          parent_id: n.parent_id || null,
        })),
        edges: (wf.edges || []).map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          type: e.type,
          data: {},
        })),
      };
      canvasStore.loadFromLayout(layoutData, {});
      canvasStore.setMode('workflow');
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
      // Convert layout to workflow first if not already linked
      let workflowId = canvasStore.currentWorkflowId;
      if (!workflowId) {
        const wf = await convertLayoutToWorkflow(canvasStore.currentLayoutId);
        workflowId = wf.id;
        canvasStore.currentWorkflowId = wf.id;
      }
      compileResult = await compileWorkflow(workflowId);
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
      // Convert to workflow first if needed, then clone the workflow
      let workflowId = canvasStore.currentWorkflowId;
      if (!workflowId) {
        const wf = await convertLayoutToWorkflow(canvasStore.currentLayoutId);
        workflowId = wf.id;
        canvasStore.currentWorkflowId = wf.id;
      }
      const cloned = await cloneWorkflow(workflowId);
      if (cloned && cloned.id) {
        canvasStore.currentWorkflowId = cloned.id;
      }
    } catch (err) {
      compileError = err.message;
    } finally {
      isCloning = false;
    }
  }

  // --- "Save as Workflow" handlers ---

  function handleOpenWorkflowDialog() {
    workflowName = canvasStore.currentLayoutName || '';
    workflowDescription = '';
    workflowMaxRounds = 5;
    workflowConsensus = 0.9;
    convertError = null;
    convertSuccess = null;
    showWorkflowDialog = true;
  }

  async function handleSaveAsWorkflow() {
    if (!canvasStore.currentLayoutId) return;
    convertError = null;
    convertSuccess = null;
    isConverting = true;

    try {
      // Save the layout first if dirty
      if (canvasStore.isDirty) {
        await handleSaveLayout();
      }

      const wf = await convertLayoutToWorkflow(canvasStore.currentLayoutId, {
        name: workflowName.trim() || canvasStore.currentLayoutName || 'Untitled Workflow',
        description: workflowDescription.trim(),
        max_rounds: workflowMaxRounds,
        consensus_threshold: workflowConsensus,
      });

      canvasStore.currentWorkflowId = wf.id;
      convertSuccess = wf.name || wf.id;

      // Close dialog after short delay to show success
      setTimeout(() => {
        showWorkflowDialog = false;
        convertSuccess = null;
      }, 1500);
    } catch (err) {
      convertError = err.message;
    } finally {
      isConverting = false;
    }
  }

  // --- "Run Debate" handlers ---

  function handleOpenRunDialog() {
    showRunDialog = true;
  }

  async function handleStartDebate(params) {
    try {
      let workflowId = canvasStore.currentWorkflowId;

      // If no workflow yet, save layout and convert
      if (!workflowId) {
        if (!canvasStore.currentLayoutId) return;

        // Save layout first if dirty
        if (canvasStore.isDirty) {
          await handleSaveLayout();
        }

        // Convert layout to workflow
        const wf = await convertLayoutToWorkflow(canvasStore.currentLayoutId, {
          name: canvasStore.currentLayoutName || 'Untitled Workflow',
          max_rounds: params.maxRounds,
          consensus_threshold: params.consensusThreshold,
        });
        workflowId = wf.id;
        canvasStore.currentWorkflowId = wf.id;
      }

      // Start the workflow execution
      const result = await startWorkflow(workflowId, params.topic, {
        language: params.language,
        maxRounds: params.maxRounds,
        threshold: params.consensusThreshold,
        documentIds: params.documentIds || [],
        ragAutoRetrieve: params.ragAutoRetrieve ?? false,
        includeDebateResults: params.includeDebateResults ?? false,
      });

      // Close run dialog, open execution panel with session ID
      showRunDialog = false;
      executionContext = params.topic;
      executionOptions = {
        language: params.language,
        maxRounds: params.maxRounds,
        threshold: params.consensusThreshold,
        documentIds: params.documentIds || [],
        ragAutoRetrieve: params.ragAutoRetrieve ?? false,
        includeDebateResults: params.includeDebateResults ?? false,
      };
      executionSessionId = result.session_id;
      showExecutionPanel = true;
    } catch (err) {
      console.error('[BlueprintCanvasView] Failed to start debate:', err);
      // Re-throw so RunWorkflowDialog can display the error
      throw err;
    }
  }

  function handleCloseExecutionPanel() {
    showExecutionPanel = false;
    executionSessionId = null;
  }
</script>

<div class="blueprint-canvas-view" data-testid="blueprint-canvas-view">
  <!-- Left: Palette -->
  <aside class="palette-column">
    <Palette onloadlayout={handleLoadLayout} />
  </aside>

  <!-- Center: Canvas -->
  <main class="canvas-column">
    <!-- Compile/Clone/Save-as-Workflow toolbar -->
    {#if canvasStore.currentLayoutId || canvasStore.currentWorkflowId}
      <div class="absolute top-2 right-2 z-10 flex items-center gap-2">
        {#if canvasStore.currentLayoutId}
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
                   bg-violet-600 text-white hover:bg-violet-700 transition-colors
                   disabled:opacity-50 disabled:cursor-not-allowed"
            onclick={handleOpenWorkflowDialog}
            title={t('blueprint.workflow.saveAsWorkflow')}
          >
            💾 {t('blueprint.workflow.saveAsWorkflow')}
          </button>
        {/if}
        <button
          class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg
                 bg-indigo-600 text-white hover:bg-indigo-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleClone}
          disabled={isCloning || !canvasStore.currentWorkflowId}
          title={t('blueprint.workflow.clone')}
        >
          {#if isCloning}
            <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          {:else}
            📋
          {/if}
          {t('blueprint.workflow.clone')}
        </button>
        <button
          class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg
                 bg-green-600 text-white hover:bg-green-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleOpenRunDialog}
          title={t('blueprint.workflow.runDebate')}
        >
          ▶️ {t('blueprint.workflow.runDebate')}
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
  templateId={selectedTemplateId}
  visible={showInstantiateModal}
  onSuccess={handleInstantiated}
  onClose={() => { showInstantiateModal = false; selectedTemplateId = null; }}
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
  <div class="dialog-overlay" role="button" tabindex="0" onclick={() => { showSaveDialog = false; }} onkeydown={(e) => { if (e.key === 'Escape') showSaveDialog = false; }}>
    <div class="dialog" role="dialog" aria-modal="true" tabindex="0" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === 'Enter') handleSaveNewLayout(); }}>
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

<!-- "Save as Workflow" dialog -->
{#if showWorkflowDialog}
  <div class="dialog-overlay" role="button" tabindex="0" onclick={() => { showWorkflowDialog = false; }} onkeydown={(e) => { if (e.key === 'Escape') showWorkflowDialog = false; }}>
    <div class="dialog dialog-wide" role="dialog" aria-modal="true" tabindex="0" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === 'Enter' && !isConverting) handleSaveAsWorkflow(); }}>
      <h3 class="dialog-title">💾 {t('blueprint.workflow.saveAsWorkflow')}</h3>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
        {t('blueprint.workflow.saveAsWorkflowHint')}
      </p>

      {#if convertError}
        <p class="dialog-error">{convertError}</p>
      {/if}
      {#if convertSuccess}
        <p class="text-sm text-emerald-600 dark:text-emerald-400 font-medium mb-3">
          ✓ {t('blueprint.workflow.workflowCreated')}: {convertSuccess}
        </p>
      {/if}

      <label class="dialog-field">
        <span class="dialog-label">{t('blueprint.workflow.workflowName')}</span>
        <input
          type="text"
          bind:value={workflowName}
          class="dialog-input"
          placeholder={canvasStore.currentLayoutName || 'My Debate Workflow'}
          data-testid="workflow-name"
        />
      </label>

      <label class="dialog-field">
        <span class="dialog-label">{t('blueprint.workflow.workflowDescription')}</span>
        <input
          type="text"
          bind:value={workflowDescription}
          class="dialog-input"
          placeholder={t('blueprint.workflow.workflowDescriptionPlaceholder')}
          data-testid="workflow-description"
        />
      </label>

      <div class="grid grid-cols-2 gap-3 mb-4">
        <label class="dialog-field">
          <span class="dialog-label">{t('blueprint.workflow.maxRounds')}</span>
          <input
            type="number"
            bind:value={workflowMaxRounds}
            min="1"
            max="50"
            class="dialog-input"
            data-testid="workflow-max-rounds"
          />
        </label>
        <label class="dialog-field">
          <span class="dialog-label">{t('blueprint.workflow.consensusThreshold')}</span>
          <input
            type="number"
            bind:value={workflowConsensus}
            min="0"
            max="1"
            step="0.05"
            class="dialog-input"
            data-testid="workflow-consensus"
          />
        </label>
      </div>

      <div class="dialog-actions">
        <button class="dialog-btn-cancel" onclick={() => { showWorkflowDialog = false; }}>
          {t('blueprint.inspector.cancel')}
        </button>
        <button
          class="dialog-btn-save"
          onclick={handleSaveAsWorkflow}
          disabled={isConverting}
          data-testid="save-as-workflow-confirm"
        >
          {#if isConverting}
            <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block mr-1"></span>
          {/if}
          {t('blueprint.workflow.convert')}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Run Workflow Dialog -->
<RunWorkflowDialog
  visible={showRunDialog}
  layoutName={canvasStore.currentLayoutName || ''}
  onstart={handleStartDebate}
  onclose={() => { showRunDialog = false; }}
/>

<!-- Execution Panel -->
<ExecutionPanel
  workflowId={canvasStore.currentWorkflowId}
  sessionId={executionSessionId}
  context={executionContext}
  startOptions={executionOptions}
  visible={showExecutionPanel}
  onclose={handleCloseExecutionPanel}
/>

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
  .dialog-wide {
    width: 440px;
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
  :global(.dark) .dialog-label { color: #9ca3af; }
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
  :global(.dark) .dialog-btn-cancel {
    border-color: #4b5563;
    color: #9ca3af;
  }
  :global(.dark) .dialog-btn-cancel:hover {
    border-color: #6b7280;
    color: #e5e7eb;
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
