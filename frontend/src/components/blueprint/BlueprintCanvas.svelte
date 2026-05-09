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
  import { i18n } from '../../lib/i18n/index.js';
  import { canvasStore } from '../../lib/blueprint/store.svelte.js';
  import { validateConnection } from '../../lib/blueprint/validation.js';
  import { screenToFlowPosition, createDraftNode, getNodeTypeFromDrop } from '../../lib/blueprint/dnd.js';
  import { applyBlueprintLayout } from '../../lib/blueprint/layout.js';
  import { getNodeTypes, getEdgeTypes } from '../../lib/blueprint/registry.js';
  import { registerAllNodeTypes } from '../../lib/blueprint/registerAll.js';
  import ModeSwitcher from './ModeSwitcher.svelte';
  import ExecutionPanel from './ExecutionPanel.svelte';

  // Initialize registry (idempotent — safe to call multiple times)
  registerAllNodeTypes();

  let { onsave = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  /** @type {HTMLElement|null} */
  let flowContainer = $state(null);

  // Build node/edge type maps from registry
  const nodeTypes = getNodeTypes();
  const edgeTypes = getEdgeTypes();

  // Reactive nodes/edges for Svelte Flow
  let nodes = $derived(canvasStore.nodes);
  let edges = $derived(canvasStore.edges);

  // ─── Event handlers ───────────────────────────────────────────────

  function handleNodeClick(event) {
    canvasStore.selectNode(event?.node?.id || null);
  }

  function handlePaneClick() {
    canvasStore.clearSelection();
  }

  function handleConnect(event) {
    const connection = event.detail || event;
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);

    if (!sourceNode || !targetNode) return;

    const result = validateConnection(sourceNode.type, targetNode.type, canvasStore.mode);
    if (!result.valid) {
      console.warn('[BlueprintCanvas] Invalid connection:', result.reason);
      return;
    }

    const edgeId = `edge-${connection.source}-${connection.target}-${result.edgeType}`;
    canvasStore.addEdge({
      id: edgeId,
      source: connection.source,
      target: connection.target,
      type: result.edgeType,
      data: {},
    });
  }

  function handleDragOver(event) {
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'move';
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    const nodeType = getNodeTypeFromDrop(event);
    if (!nodeType || !flowContainer) return;

    // Get viewport from the Svelte Flow instance
    const bounds = flowContainer.getBoundingClientRect();
    // Svelte Flow stores viewport in a data attribute or we can approximate
    const viewport = { x: 0, y: 0, zoom: 1 };
    const position = screenToFlowPosition(event, viewport, bounds);

    const draftNode = createDraftNode(nodeType, position);
    canvasStore.addNode(draftNode);
    canvasStore.selectNode(draftNode.id);
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

  function handleNodeDragStop(event) {
    const node = event.detail?.node || event.node;
    if (node) {
      canvasStore.updateNodePosition(node.id, node.position);
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
      onclick={handleAutoLayout}
      title={t('blueprint.canvas.autoLayout')}
      data-testid="canvas-auto-layout"
    >
      📐 {t('blueprint.canvas.autoLayout')}
    </button>
    {#if isWorkflowMode && hasNodes}
      <button
        class="toolbar-btn toolbar-btn-execute"
        class:active={showExecutionPanel}
        onclick={handleToggleExecution}
        title={t('workflow.execution.title')}
        data-testid="canvas-execute"
      >
        🚀 {t('workflow.execution.title')}
      </button>
    {/if}
    <span class="toolbar-info">
      {nodes.length} nodes · {edges.length} edges
      {#if canvasStore.isDirty}
        <span class="dirty-indicator">●</span>
      {/if}
    </span>
  </div>

  {#if nodes.length === 0}
    <div class="empty-state">
      <span class="empty-icon">🧩</span>
      <p class="empty-text">Drag assets from the palette to start building</p>
    </div>
  {:else}
    <SvelteFlow
      {nodes}
      {edges}
      {nodeTypes}
      {edgeTypes}
      fitView
      onnodeclick={handleNodeClick}
      onpaneclick={handlePaneClick}
      onconnect={handleConnect}
      onnodestdragstop={handleNodeDragStop}
      class="blueprint-flow"
    >
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
  {/if}

  <!-- Execution Panel -->
  <ExecutionPanel
    workflowId={activeWorkflowId}
    visible={showExecutionPanel}
    onclose={handleCloseExecution}
    onNodeStatusUpdate={handleNodeStatusUpdate}
  />
</div>

<style>
  .blueprint-canvas-wrapper {
    width: 100%;
    height: 100%;
    position: relative;
    display: flex;
    flex-direction: column;
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
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 300px;
    color: #9ca3af;
  }
  .empty-icon { font-size: 48px; margin-bottom: 12px; opacity: 0.5; }
  .empty-text { font-size: 14px; }
</style>
