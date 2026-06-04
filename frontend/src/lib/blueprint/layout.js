/**
 * Blueprint Canvas — ELK.js auto-layout engine.
 *
 * Supports phase containers as ELK parent nodes for multi-phase debate
 * workflows.  Phase containers expand to fit their child nodes.
 * Uses the layered algorithm with LEFT→RIGHT direction.
 */

import { runLayout } from '../elk-service.js';

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.layered.spacing.nodeNodeBetweenLayers': '100',
  'elk.spacing.nodeNode': '60',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.layered.feedbackEdges': 'true',
};

const elkOptionsWithChildren = {
  ...elkOptions,
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
};

const PHASE_CONTAINER_PADDING = 60;

/**
 * Node dimensions by type for ELK layout calculation.
 * @type {Record<string, { width: number, height: number }>}
 */
const NODE_DIMENSIONS = {
  'agent-blueprint': { width: 220, height: 120 },
  'llm-profile': { width: 200, height: 100 },
  'role-definition': { width: 200, height: 100 },
  'prompt-template': { width: 200, height: 110 },
  'role-type': { width: 200, height: 100 },
  'agent-core': { width: 200, height: 100 },
  'wf-input': { width: 180, height: 80 },
  'wf-initialize': { width: 180, height: 80 },
  'wf-strategist': { width: 200, height: 90 },
  'wf-critic': { width: 200, height: 90 },
  'wf-fact-checker': { width: 200, height: 90 },
  'wf-optimizer': { width: 200, height: 90 },
  'wf-moderator': { width: 200, height: 90 },
  'wf-analyst': { width: 200, height: 90 },
  'wf-creative': { width: 200, height: 90 },
  'wf-socratic-questioner': { width: 200, height: 90 },
  'wf-expert-reviewer': { width: 200, height: 90 },
  'wf-steel-manner': { width: 200, height: 90 },
  'wf-devils-advocate': { width: 200, height: 90 },
  'wf-troll': { width: 200, height: 90 },
  'wf-mediator': { width: 200, height: 90 },
  'wf-ethicist': { width: 200, height: 90 },
  'wf-synthesizer': { width: 200, height: 90 },
  'wf-user-injection': { width: 200, height: 90 },
  'wf-gate': { width: 180, height: 80 },
  'wf-angels-advocate': { width: 200, height: 90 },
};

/**
 * Calculate ELK layout positions for blueprint canvas nodes.
 *
 * Supports phase containers:
 * - `wf-phase` nodes become ELK parent containers
 * - Workflow nodes with `parentId` matching a phase are placed as children
 * - Asset-mode nodes and unaffiliated workflow nodes stay at top level
 * - Phase containers are connected by sequential edges
 *
 * @param {import('@xyflow/svelte').Node[]} nodes
 * @param {import('@xyflow/svelte').Edge[]} edges
 * @returns {Promise<Map<string, { x: number, y: number }>>}
 */
export async function calculateBlueprintLayout(nodes, edges) {
  if (nodes.length === 0) return new Map();

  // Separate phase containers, their children, and top-level nodes
  const phaseNodes = nodes.filter(n => n.type === 'wf-phase');
  const phaseIds = new Set(phaseNodes.map(n => n.id));

  const phaseChildren = new Map(); // phaseId -> child nodes
  const topLevelNodes = [];

  for (const node of nodes) {
    if (node.type === 'wf-phase') continue;
    const parentId = node.parentId || node.data?.parentId;
    if (parentId && phaseIds.has(parentId)) {
      if (!phaseChildren.has(parentId)) {
        phaseChildren.set(parentId, []);
      }
      phaseChildren.get(parentId).push(node);
    } else {
      topLevelNodes.push(node);
    }
  }

  // Build ELK children
  const elkChildren = [];

  // Add phase containers as hierarchical parent nodes
  for (const phase of phaseNodes) {
    const children = phaseChildren.get(phase.id) || [];
    const dims = NODE_DIMENSIONS[phase.type] || { width: 300, height: 100 };

    elkChildren.push({
      id: phase.id,
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.spacing.nodeNode': '30',
        'elk.padding': `[top=${PHASE_CONTAINER_PADDING},left=${PHASE_CONTAINER_PADDING / 2},bottom=${PHASE_CONTAINER_PADDING / 2},right=${PHASE_CONTAINER_PADDING / 2}]`,
      },
      width: dims.width + PHASE_CONTAINER_PADDING,
      height: dims.height + PHASE_CONTAINER_PADDING,
      children: children.map(n => {
        const nd = NODE_DIMENSIONS[n.type] || { width: 200, height: 80 };
        return { id: n.id, width: nd.width, height: nd.height };
      }),
    });
  }

  // Add top-level nodes (asset nodes + unaffiliated workflow nodes)
  for (const node of topLevelNodes) {
    const dims = NODE_DIMENSIONS[node.type] || { width: 200, height: 100 };
    elkChildren.push({
      id: node.id,
      width: dims.width,
      height: dims.height,
    });
  }

  const elkEdges = edges.map(e => ({
    id: e.id,
    sources: [e.source],
    targets: [e.target],
  }));

  const hasPhases = phaseNodes.length > 0;
  const elkGraph = {
    id: 'blueprint-root',
    layoutOptions: hasPhases ? elkOptionsWithChildren : elkOptions,
    children: elkChildren,
    edges: elkEdges,
  };

  const result = await runLayout(elkGraph);

  const positions = new Map();

  /**
   * Recursively extract positions from ELK result.
   * @param {Object} node
   */
  function extractPositions(node) {
    if (node.x != null && node.y != null) {
      positions.set(node.id, { x: node.x, y: node.y });
    }
    if (node.children) {
      for (const child of node.children) {
        extractPositions(child);
      }
    }
  }

  extractPositions(result);
  return positions;
}

/**
 * Apply auto-layout to the canvas store.
 *
 * @param {import('./store.svelte.js').canvasStore} store - The canvas store instance
 */
export async function applyBlueprintLayout(store) {
  const { nodes, edges } = store;
  if (nodes.length === 0) return;

  try {
    const positions = await calculateBlueprintLayout(nodes, edges);

    const updatedNodes = nodes.map((n) => {
      const pos = positions.get(n.id);
      return pos ? { ...n, position: pos } : n;
    });

    store.setNodes(updatedNodes);
  } catch (err) {
    console.warn('[blueprint/layout] ELK layout failed:', err);
  }
}
