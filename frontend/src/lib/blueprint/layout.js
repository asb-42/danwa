/**
 * Blueprint Canvas — ELK.js auto-layout engine.
 *
 * Follows the pattern of the existing workflow layout module.
 * Uses the layered algorithm with LEFT→RIGHT direction.
 */

import ELK from 'elkjs/lib/elk.bundled.js';

const elk = new ELK();

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.layered.spacing.nodeNodeBetweenLayers': '100',
  'elk.spacing.nodeNode': '60',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
};

/**
 * Node dimensions by type for ELK layout calculation.
 * @type {Record<string, { width: number, height: number }>}
 */
const NODE_DIMENSIONS = {
  'agent-blueprint': { width: 220, height: 120 },
  'llm-profile': { width: 200, height: 100 },
  'role-definition': { width: 200, height: 100 },
  'prompt-template': { width: 200, height: 110 },
};

/**
 * Calculate ELK layout positions for blueprint canvas nodes.
 *
 * @param {import('@xyflow/svelte').Node[]} nodes
 * @param {import('@xyflow/svelte').Edge[]} edges
 * @returns {Promise<Map<string, { x: number, y: number }>>}
 */
export async function calculateBlueprintLayout(nodes, edges) {
  if (nodes.length === 0) return new Map();

  const elkChildren = nodes.map((n) => {
    const dims = NODE_DIMENSIONS[n.type] || { width: 200, height: 100 };
    return {
      id: n.id,
      width: dims.width,
      height: dims.height,
    };
  });

  const elkEdges = edges.map((e) => ({
    id: e.id,
    sources: [e.source],
    targets: [e.target],
  }));

  const elkGraph = {
    id: 'blueprint-root',
    layoutOptions: elkOptions,
    children: elkChildren,
    edges: elkEdges,
  };

  const result = await elk.layout(elkGraph);

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
