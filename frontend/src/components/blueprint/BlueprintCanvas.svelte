<script>
  /**
   * BlueprintCanvas — Center column with SvelteFlow instance.
   *
   * Registers custom node/edge types from the central registry,
   * handles DnD drops, mode-aware connection validation, and canvas toolbar.
   * Supports both Blueprint Mode and Workflow Mode.
   */
  import { SvelteFlow, Background, Controls, MiniMap } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { tStore } from '../../lib/i18n/index.js';
  import { canvasStore } from '../../lib/blueprint/store.svelte.js';
  import { validateConnection } from '../../lib/blueprint/validation.js';
  import { createDraftNode, getNodeTypeFromDrop, getEntityIdFromDrop, createEntityNode } from '../../lib/blueprint/dnd.js';
  import {
    getAgentBlueprint,
    getAgentBundle,
    getBlueprintLLMProfile,
    getRoleDefinition,
    getPromptTemplate,
    getRoleType,
    getToneProfile,
  } from '../../lib/blueprint/api.js';
  import { applyBlueprintLayout } from '../../lib/blueprint/layout.js';
  import { getNodeTypes, getEdgeTypes } from '../../lib/blueprint/registry.js';
  import { registerAllNodeTypes } from '../../lib/blueprint/registerAll.js';
  import { wireEdgeOnConnect, wireEdgeOnDisconnect, isSemanticEdge } from '../../lib/blueprint/edgeWiring.js';
  import ModeSwitcher from './ModeSwitcher.svelte';
  import ExecutionPanel from './ExecutionPanel.svelte';
  import ProposalsPanel from './ProposalsPanel.svelte';
  import SvelteFlowInstanceBridge from './SvelteFlowInstanceBridge.svelte';

  // Initialize registry (idempotent — safe to call multiple times)
  registerAllNodeTypes();

  let { onsave = () => {}, onsaveas = () => {}, onnewworkflow = () => {}, onsaveastemplate = () => {} } = $props();

  let t = $derived($tStore);

  /** @type {HTMLElement|null} */
  let flowContainer = $state(null);

  /** @type {import('@xyflow/svelte').SvelteFlowInstance | null} */
  let svelteFlow = $state(null);

  // Build node/edge type maps from registry
  const nodeTypes = getNodeTypes();
  const edgeTypes = getEdgeTypes();

  // Pass store arrays directly — no derived wrapping to avoid reactivity loops with SvelteFlow
  let nodes = $derived(canvasStore.nodes);
  let edges = $derived(canvasStore.edges);

  // ─── Event handlers ───────────────────────────────────────────────

  function handleNodeClick({ node }) {
    canvasStore.selectNode(node?.id || null);
  }

  function handlePaneClick() {
    canvasStore.clearSelection();
  }

  function handleConnect(connection) {
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);

    if (!sourceNode || !targetNode) return;

    const result = validateConnection(sourceNode.type, targetNode.type, canvasStore.mode);
    if (!result.valid) {
      if (import.meta.env.DEV) console.warn('[BlueprintCanvas] Invalid connection:', result.reason);
      return;
    }

    const sourceHandle = connection.sourceHandle || 'out';
    const targetHandle = connection.targetHandle || 'in';
    const edgeId = `edge-${connection.source}-${sourceHandle}-${connection.target}-${targetHandle}-${result.edgeType}`;
    const newEdge = {
      id: edgeId,
      source: connection.source,
      sourceHandle,
      target: connection.target,
      targetHandle,
      type: result.edgeType,
      data: {},
    };
    canvasStore.addEdge(newEdge);

    // Wire semantic edges to backend FK updates
    if (isSemanticEdge(result.edgeType)) {
      wireEdgeOnConnect(newEdge, canvasStore.nodes, canvasStore.updateNodeData.bind(canvasStore))
        .catch((err) => { if (import.meta.env.DEV) console.error('[BlueprintCanvas] Edge wiring failed:', err) } );
    }
  }

  /**
   * Pre-validate connections during drag — SvelteFlow shows red line + bounce-back
   * for invalid connections, preventing the "ghost edge" UX issue.
   */
  function isValidConnection(connection) {
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);
    if (!sourceNode || !targetNode) return false;
    const result = validateConnection(sourceNode.type, targetNode.type, canvasStore.mode);
    return result.valid;
  }

  /**
   * Handle node/edge deletion — unwire semantic edges from backend.
   * Triggered when the user selects and deletes nodes/edges (Delete/Backspace key).
   * @param {{ nodes: Array, edges: Array }} param0
   */
  function handleDelete({ nodes: deletedNodes = [], edges: deletedEdges = [] }) {
    for (const edge of deletedEdges) {
      canvasStore.removeEdge(edge.id);
      if (isSemanticEdge(edge.type)) {
        wireEdgeOnDisconnect(edge, canvasStore.nodes, canvasStore.updateNodeData.bind(canvasStore))
          .catch((err) => { if (import.meta.env.DEV) console.error('[BlueprintCanvas] Edge unwiring failed:', err) } );
      }
    }
    for (const node of deletedNodes) {
      canvasStore.removeNode(node.id);
    }
  }

  function handleDragOver(event) {
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'move';
    }
  }

  /**
   * Find a parent phase node that contains the given canvas position.
   * @param {{ x: number, y: number }} point - Canvas-space position
   * @returns {string|null} - Phase node ID or null
   */
  function findParentPhase(point) {
    const phaseNodes = canvasStore.nodes.filter(n => n.type === 'wf-phase');
    for (const pn of phaseNodes) {
      const w = pn.width ?? pn.measured?.width ?? 300;
      const h = pn.height ?? pn.measured?.height ?? 200;
      const x = pn.position.x;
      const y = pn.position.y;
      if (point.x >= x && point.x <= x + w && point.y >= y && point.y <= y + h) {
        return pn.id;
      }
    }
    return null;
  }

  async function handleDrop(event) {
    event.preventDefault();
    const nodeType = getNodeTypeFromDrop(event);
    if (!nodeType || !flowContainer || !svelteFlow) return;

    const position = svelteFlow.screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });

    const parentId = findParentPhase(position);

    // If inside a phase, convert drop position to be relative to the parent
    const adjustedPosition = { ...position };
    if (parentId) {
      const parentNode = canvasStore.nodes.find(n => n.id === parentId);
      if (parentNode) {
        adjustedPosition.x -= parentNode.position.x;
        adjustedPosition.y -= parentNode.position.y;
      }
    }

    const entityId = getEntityIdFromDrop(event);

    if (entityId) {
      // Existing entity drop — load entity data and create non-draft node
      try {
        let entityData = $state(null);
        switch (nodeType) {
          case 'agent-blueprint':
            entityData = await getAgentBlueprint(entityId);
            break;
          case 'llm-profile':
            entityData = await getBlueprintLLMProfile(entityId);
            break;
          case 'role-definition':
            entityData = await getRoleDefinition(entityId);
            break;
          case 'prompt-template':
            entityData = await getPromptTemplate(entityId);
            break;
          case 'role-type':
            entityData = await getRoleType(entityId);
            break;
          case 'tone-profile':
            entityData = await getToneProfile(entityId);
            break;
          case 'agent-bundle':
            entityData = await getAgentBundle(entityId);
            break;
        }
        if (entityData) {
          if (nodeType === 'agent-bundle') {
            const bundleNode = {
              id: `entity-${entityId}`,
              type: 'wf-agent',
              position: adjustedPosition,
              data: {
                isDraft: false,
                bundle_id: entityId,
                label: entityData.name || entityId,
                role_type_icon: '\u{1F464}',
                role_type_name: '',
                role_type_color: '#8b5cf6',
              },
            };
            bundleNode.parentId = parentId;
            canvasStore.addNode(bundleNode);
            canvasStore.selectNode(bundleNode.id);
          } else {
            const entityNode = createEntityNode(nodeType, entityId, entityData, adjustedPosition);
            entityNode.parentId = parentId;
            canvasStore.addNode(entityNode);
            canvasStore.selectNode(entityNode.id);
          }
        }
      } catch (err) {
        if (import.meta.env.DEV) console.warn('[BlueprintCanvas] Failed to load entity for drop:', err);
      }
    } else {
      // Draft node drop (new)
      const draftNode = createDraftNode(nodeType, adjustedPosition);
      draftNode.parentId = parentId;
      canvasStore.addNode(draftNode);
      canvasStore.selectNode(draftNode.id);
    }
  }

  // ─── Execution state ──────────────────────────────────────────────
  let showExecutionPanel = $state(false);
  let activeWorkflowId = $state(null);
  let nodeExecutionStatus = $state({}); // nodeId → 'idle' | 'running' | 'completed' | 'failed' | 'paused'

  function handleToggleExecution() {
    showExecutionPanel = !showExecutionPanel;
    if (showExecutionPanel) {
      // Find the current workflow ID from the store
      activeWorkflowId = canvasStore.currentWorkflowId || null;
    }
  }

  function handleCloseExecution() {
    showExecutionPanel = false;
    nodeExecutionStatus = {};
  }

  // ─── Reflection state ──────────────────────────────────────────────
  let showProposalsPanel = $state(false);
  let isReflecting = $state(false);
  let reflectError = $state('');

  let canReflect = $derived(
    isWorkflowMode && canvasStore.currentWorkflowId && !canvasStore.isDirty
  );

  async function handleReflect() {
    const workflowId = canvasStore.currentWorkflowId;
    if (!workflowId) return;
    isReflecting = true;
    reflectError = '';
    try {
      const res = await fetch(`/api/v1/workflows/${workflowId}/reflect`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        reflectError = body.detail || `HTTP ${res.status}`;
        return;
      }
      showProposalsPanel = true;
    } catch (err) {
      reflectError = err.message;
    } finally {
      isReflecting = false;
    }
  }

  function handleNodeStatusUpdate(nodeId, execStatus) {
    nodeExecutionStatus = { ...nodeExecutionStatus, [nodeId]: execStatus };
    // Update the node's data.executionStatus in the store
    canvasStore.updateNodeData(nodeId, { executionStatus: execStatus });
  }

  let isWorkflowMode = $derived(canvasStore.mode === 'workflow');
  let hasNodes = $derived(nodes.length > 0);

  async function handleAutoLayout() {
    await applyBlueprintLayout(canvasStore);
  }

  function handleSaveLayout() {
    onsave();
  }

  function handleNodeDragStop({ targetNode }) {
    if (!targetNode) return;

    const updatedPosition = { ...targetNode.position };

    // Re-evaluate phase parentage on drag end
    let newParentId = $state(null);
    if (targetNode.type !== 'wf-phase') {
      const phaseNodes = canvasStore.nodes.filter(n => n.type === 'wf-phase' && n.id !== targetNode.id);
      // Use absolute position on the canvas (relative position + parent offset)
      const absPos = { ...updatedPosition };
      if (targetNode.parentId) {
        const currentParent = canvasStore.nodes.find(n => n.id === targetNode.parentId);
        if (currentParent) {
          absPos.x += currentParent.position.x;
          absPos.y += currentParent.position.y;
        }
      }
      for (const pn of phaseNodes) {
        const w = pn.width ?? pn.measured?.width ?? 300;
        const h = pn.height ?? pn.measured?.height ?? 200;
        if (absPos.x >= pn.position.x && absPos.x <= pn.position.x + w &&
            absPos.y >= pn.position.y && absPos.y <= pn.position.y + h) {
          newParentId = pn.id;
          // Convert position to be relative to new parent
          updatedPosition.x = absPos.x - pn.position.x;
          updatedPosition.y = absPos.y - pn.position.y;
          break;
        }
      }
    }

    // Only update if something changed
    if (newParentId !== targetNode.parentId ||
        updatedPosition.x !== targetNode.position.x ||
        updatedPosition.y !== targetNode.position.y) {
      canvasStore.updateNode(targetNode.id, updatedPosition, newParentId);
    }
  }
</script>

<div
  class="blueprint-canvas-wrapper"
  bind:this={flowContainer}
  role="application"
  ondragover={handleDragOver}
  ondrop={handleDrop}
  data-testid="blueprint-canvas"
>
  <!-- Toolbar -->
  <div class="canvas-toolbar">
    <ModeSwitcher />
    <button
      class="toolbar-btn"
      onclick={handleSaveLayout}
      title={t('blueprint.canvas.saveLayout')}
      data-testid="canvas-save-layout"
    >
      💾 {t('blueprint.canvas.saveLayout')}
    </button>
    <button
      class="toolbar-btn"
      onclick={() => onsaveas()}
      title={t('blueprint.canvas.saveAs')}
      data-testid="canvas-save-as"
    >
      📄 {t('blueprint.canvas.saveAs')}
    </button>
    <button
      class="toolbar-btn"
      onclick={handleAutoLayout}
      title={t('blueprint.canvas.autoLayout')}
      data-testid="canvas-auto-layout"
    >
      📐 {t('blueprint.canvas.autoLayout')}
    </button>
    <button
      class="toolbar-btn"
      onclick={() => onnewworkflow()}
      title={t('template.gallery.title') || 'Templates'}
      data-testid="canvas-templates"
    >
      📋 {t('template.gallery.title') || 'Templates'}
    </button>
    {#if isWorkflowMode && hasNodes}
      <button
        class="toolbar-btn"
        onclick={() => onsaveastemplate()}
        title={t('template.saveAs.title')}
        data-testid="canvas-save-as-template"
      >
        📦 {t('template.saveAs.title')}
      </button>
      <button
        class="toolbar-btn toolbar-btn-execute"
        class:active={showExecutionPanel}
        onclick={handleToggleExecution}
        title={t('workflow.execution.title')}
        data-testid="canvas-execute"
      >
        🚀 {t('workflow.execution.title')}
      </button>
      {#if canReflect}
        <button
          class="toolbar-btn toolbar-btn-reflect"
          class:active={showProposalsPanel}
          onclick={handleReflect}
          disabled={isReflecting}
          title={t('workflow.reflect.title') || 'Reflect & Optimize'}
          data-testid="canvas-reflect"
        >
          🔍 {isReflecting ? '...' : (t('workflow.reflect.title') || 'Reflect')}
        </button>
      {/if}
    {/if}
    <span class="toolbar-info">
      {nodes.length} nodes · {edges.length} edges
      {#if canvasStore.isDirty}
        <span class="dirty-indicator">●</span>
      {/if}
    </span>
  </div>

  <!-- SvelteFlow always rendered to accept drops -->
  <SvelteFlow
    {nodes}
    {edges}
    {nodeTypes}
    {edgeTypes}
    {isValidConnection}
    onnodeclick={handleNodeClick}
    onpaneclick={handlePaneClick}
    onconnect={handleConnect}
    ondelete={handleDelete}
    onnodedragstop={handleNodeDragStop}
    minZoom={0.2}
    maxZoom={2}
    class="blueprint-flow"
  >
    <!-- Bridge to expose SvelteFlow instance to parent -->
    <SvelteFlowInstanceBridge onready={(flow) => {
      svelteFlow = flow;
      // Only fit view on initial mount, not on every node change
      setTimeout(() => flow.fitView({ padding: 0.3 }), 100);
    }} />
    <Background />
    <Controls />
    <MiniMap
      nodeColor={(node) => {
        switch (node.type) {
          case 'agent-blueprint': return '#6b7280';
          case 'llm-profile': return '#3b82f6';
          case 'role-definition': return '#8b5cf6';
          case 'prompt-template': return '#10b981';
          default: return '#9ca3af';
        }
      }}
      maskColor="rgba(0,0,0,0.1)"
    />
  </SvelteFlow>

  <!-- Empty state overlay (shown when no nodes exist) -->
  {#if nodes.length === 0}
    <div class="empty-state">
      <span class="empty-icon">🧩</span>
      <p class="empty-text">Drag assets from the palette to start building</p>
    </div>
  {/if}

  <!-- Execution Panel -->
  <ExecutionPanel
    workflowId={activeWorkflowId}
    visible={showExecutionPanel}
    onclose={handleCloseExecution}
    onNodeStatusUpdate={handleNodeStatusUpdate}
  />

  <!-- Proposals Panel -->
  {#if showProposalsPanel && canvasStore.currentWorkflowId}
    <ProposalsPanel
      workflowId={canvasStore.currentWorkflowId}
      visible={showProposalsPanel}
      onclose={() => { showProposalsPanel = false; reflectError = ''; }}
    />
  {/if}

  {#if reflectError}
    <div class="reflect-error" role="alert">
      ⚠️ {reflectError}
      <button class="reflect-error-dismiss" onclick={() => reflectError = ''}>✕</button>
    </div>
  {/if}
</div>

<style>
  .blueprint-canvas-wrapper {
    width: 100%;
    height: 100%;
    position: relative;
    display: flex;
    flex-direction: column;
  }
  /* SvelteFlow canvas dark mode */
  :global(.dark .svelte-flow) {
    background: #111827;
  }
  :global(.dark .svelte-flow__background) {
    color: #374151;
  }
  :global(.dark .svelte-flow__controls button) {
    background: #1f2937;
    border-color: #374151;
    color: #e5e7eb;
    fill: #e5e7eb;
  }
  :global(.dark .svelte-flow__controls button:hover) {
    background: #374151;
  }
  :global(.dark .svelte-flow__minimap) {
    background: #1f2937;
  }
  .canvas-toolbar {
    position: absolute;
    top: 8px;
    left: 8px;
    right: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    z-index: 10;
    pointer-events: none;
  }
  .toolbar-btn {
    pointer-events: auto;
    padding: 6px 12px;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background: white;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    color: #374151;
  }
  :global(.dark) .toolbar-btn {
    background: #1f2937;
    border-color: #374151;
    color: #e5e7eb;
  }
  .toolbar-btn:hover {
    border-color: #3b82f6;
    box-shadow: 0 2px 8px rgba(59,130,246,0.15);
  }
  .toolbar-btn-execute {
    background: #eff6ff;
    border-color: #93c5fd;
    color: #1d4ed8;
  }
  .toolbar-btn-execute:hover {
    background: #dbeafe;
    border-color: #3b82f6;
  }
  .toolbar-btn-execute.active {
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
  }
  :global(.dark) .toolbar-btn-execute {
    background: #1e3a5f;
    border-color: #3b82f6;
    color: #93c5fd;
  }
  :global(.dark) .toolbar-btn-execute:hover {
    background: #1e40af;
    border-color: #60a5fa;
  }
  :global(.dark) .toolbar-btn-execute.active {
    background: #3b82f6;
    color: white;
  }
  .toolbar-btn-reflect {
    background: #fefce8;
    border-color: #fde047;
    color: #854d0e;
  }
  .toolbar-btn-reflect:hover {
    background: #fef9c3;
    border-color: #facc15;
  }
  .toolbar-btn-reflect.active {
    background: #eab308;
    color: white;
    border-color: #eab308;
  }
  :global(.dark) .toolbar-btn-reflect {
    background: #422006;
    border-color: #f59e0b;
    color: #fde047;
  }
  :global(.dark) .toolbar-btn-reflect:hover {
    background: #78350f;
    border-color: #fbbf24;
  }
  :global(.dark) .toolbar-btn-reflect.active {
    background: #eab308;
    color: #1f2937;
  }
  .toolbar-btn-reflect:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .reflect-error {
    position: absolute;
    bottom: 8px;
    left: 50%;
    transform: translateX(-50%);
    background: #fef2f2;
    border: 1px solid #fca5a5;
    color: #991b1b;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  :global(.dark) .reflect-error {
    background: #450a0a;
    border-color: #7f1d1d;
    color: #fca5a5;
  }
  .reflect-error-dismiss {
    background: none;
    border: none;
    cursor: pointer;
    color: #991b1b;
    font-size: 14px;
    padding: 0 2px;
  }
  .toolbar-info {
    pointer-events: auto;
    margin-left: auto;
    font-size: 11px;
    color: #9ca3af;
    background: rgba(255,255,255,0.9);
    padding: 4px 10px;
    border-radius: 6px;
  }
  :global(.dark) .toolbar-info {
    background: rgba(31,41,55,0.9);
    color: #6b7280;
  }
  .dirty-indicator {
    color: #f59e0b;
    margin-left: 4px;
  }
  .empty-state {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    pointer-events: none;
    z-index: 5;
  }
  .empty-icon { font-size: 48px; margin-bottom: 12px; opacity: 0.5; }
  .empty-text { font-size: 14px; }

  /* Ensure SvelteFlow handles are visible on all nodes */
  :global(.svelte-flow__handle) {
    width: 12px;
    height: 12px;
    min-width: 12px;
    min-height: 12px;
    border-radius: 50%;
    border: 2px solid #3b82f6;
    background: white;
    z-index: 1;
    pointer-events: all;
  }
  :global(.dark .svelte-flow__handle) {
    background: #1f2937;
    border-color: #60a5fa;
  }
  :global(.svelte-flow__handle:hover) {
    background: #3b82f6;
  }

  /* Color-coded port types based on edge semantics */
  :global(.port-llm) {
    border-color: #3b82f6 !important;
  }
  :global(.port-role) {
    border-color: #8b5cf6 !important;
  }
  :global(.port-prompt) {
    border-color: #10b981 !important;
  }
  :global(.port-config) {
    border-color: #f59e0b !important;
    background: white !important;
  }
  :global(.port-sequence) {
    border-color: #6366f1 !important;
  }
  :global(.port-feedback) {
    border-color: #ec4899 !important;
  }
  :global(.port-tone) {
    border-color: #f59e0b !important;
  }
  :global(.dark) :global(.port-llm),
  :global(.dark) :global(.port-role),
  :global(.dark) :global(.port-prompt),
  :global(.dark) :global(.port-config),
  :global(.dark) :global(.port-sequence),
  :global(.dark) :global(.port-feedback),
  :global(.dark) :global(.port-tone) {
    background: #1f2937 !important;
  }
</style>
