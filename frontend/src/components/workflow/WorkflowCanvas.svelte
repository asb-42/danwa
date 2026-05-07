<script>
  /**
   * WorkflowCanvas — Main Svelte Flow container for workflow visualization.
   *
   * Registers custom node/edge types, subscribes to workflow store,
   * and triggers ELK layout on topology changes.
   *
   * IMPORTANT: Layout is triggered via $effect (not inside a derived store)
   * because applyLayout is async and mutates the graphNodes store — a side
   * effect that must NOT live inside a derived() callback.
   */
  import { SvelteFlow, Background, Controls, MiniMap } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { flowNodes, flowEdges, runtime, viewMode } from '../../lib/workflow/store.js';
  import { workflowGraph } from '../../lib/workflow/useWorkflowGraph.js';
  import { applyLayout } from '../../lib/workflow/layout.js';
  import { i18n } from '../../lib/i18n/index.js';

  // Custom nodes
  import InputNode from './nodes/InputNode.svelte';
  import AgentNode from './nodes/AgentNode.svelte';
  import DecisionNode from './nodes/DecisionNode.svelte';
  import ArtifactNode from './nodes/ArtifactNode.svelte';
  import UserActionNode from './nodes/UserActionNode.svelte';
  import HistoryNode from './nodes/HistoryNode.svelte';
  import A2ANode from './nodes/A2ANode.svelte';

  // Custom edges
  import FlowEdge from './edges/FlowEdge.svelte';
  import FeedbackEdge from './edges/FeedbackEdge.svelte';
  import UserEdge from './edges/UserEdge.svelte';
  import OOBEdge from './edges/OOBEdge.svelte';

  // Panels
  import NodeDetailPanel from './panels/NodeDetailPanel.svelte';
  import TimelinePanel from './panels/TimelinePanel.svelte';

  /** @type {{ data?: any }} */
  let { data = {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let selectedNode = $state(null);

  const nodeTypes = {
    input: InputNode,
    agent: AgentNode,
    decision: DecisionNode,
    artifact: ArtifactNode,
    user_action: UserActionNode,
    history: HistoryNode,
    placeholder: AgentNode, // Reuse agent node for placeholders
    a2a_agent: A2ANode,
  };

  const edgeTypes = {
    flow: FlowEdge,
    feedback: FeedbackEdge,
    user_request: UserEdge,
    user_response: UserEdge,
    oob: OOBEdge,
  };

  // Reactive nodes/edges for Svelte Flow
  let nodes = $derived($flowNodes);
  let edges = $derived($flowEdges);
  let status = $derived($runtime.status);

  // Subscribe to workflowGraph to keep the derived store alive
  // (ensures the store stays active while the canvas is mounted)
  let _wg = $workflowGraph;

  // Trigger ELK layout when topology changes (node/edge count).
  // This is a side effect, so it lives in $effect, NOT in a derived store.
  $effect(() => {
    // Reading nodes.length and edges.length makes this effect re-run
    // whenever the graph topology changes (new node/edge added).
    const n = nodes.length;
    const e = edges.length;
    if (n > 0) {
      applyLayout(nodes, edges);
    }
  });

  function handleNodeClick(event) {
    selectedNode = event?.node || null;
  }

  function handlePaneClick() {
    selectedNode = null;
  }
</script>

<div class="workflow-canvas-container" class:has-panel={selectedNode}>
  <div class="canvas-area">
    {#if nodes.length === 0}
      <div class="empty-state">
        <span class="empty-icon">🔄</span>
        <p class="empty-text">{t('workflow.emptyState')}</p>
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
        class="workflow-flow"
      >
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            switch (node.type) {
              case 'agent': return '#3b82f6';
              case 'artifact': return '#8b5cf6';
              case 'user_action': return '#f59e0b';
              case 'decision': return '#10b981';
              case 'a2a_agent': return '#8b5cf6';
              default: return '#6b7280';
            }
          }}
          maskColor="rgba(0,0,0,0.1)"
        />
      </SvelteFlow>
    {/if}

    <!-- Status bar -->
    <div class="status-bar">
      <span class="status-indicator" class:running={status === 'running'} class:waiting={status === 'waiting_for_user'} class:completed={status === 'completed'}>
        {#if status === 'running'}
          ● Running
        {:else if status === 'waiting_for_user'}
          ● Waiting for input
        {:else if status === 'completed'}
          ● Completed
        {:else}
          ○ Idle
        {/if}
      </span>
      <span class="node-count">{nodes.length} nodes · {edges.length} edges</span>
    </div>
  </div>

  <!-- Side panels -->
  {#if selectedNode}
    <NodeDetailPanel node={selectedNode} onclose={() => selectedNode = null} />
  {/if}

  {#if $viewMode === 'timeline'}
    <TimelinePanel />
  {/if}
</div>

<style>
  .workflow-canvas-container {
    display: flex;
    width: 100%;
    height: 100%;
    min-height: 400px;
    position: relative;
  }
  .canvas-area {
    flex: 1;
    position: relative;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #e5e7eb;
  }
  :global(.dark) .canvas-area { border-color: #374151; }
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
  .status-bar {
    position: absolute;
    bottom: 8px;
    left: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 11px;
    color: #6b7280;
    background: rgba(255,255,255,0.9);
    padding: 4px 10px;
    border-radius: 6px;
    backdrop-filter: blur(4px);
    z-index: 5;
  }
  :global(.dark) .status-bar {
    background: rgba(17,24,39,0.9);
    color: #9ca3af;
  }
  .status-indicator.running { color: #10b981; }
  .status-indicator.waiting { color: #f59e0b; }
  .status-indicator.completed { color: #6b7280; }
  .node-count { color: #9ca3af; }
</style>
