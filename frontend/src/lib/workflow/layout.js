/**
 * ELK.js Layout Engine
 *
 * Wraps ELK.js to calculate automatic node positioning for non-linear workflows.
 * Uses the layered algorithm with round containers as ELK parent nodes.
 *
 * Key design decisions:
 * - Incremental layout: only positions NEW nodes that lack a position.
 *   Existing nodes keep their initial positions (set by graphReducer).
 * - hierarchyHandling: INCLUDE_CHILDREN ensures ELK respects the round subgraph
 *   hierarchy and lays out the ENTIRE graph, not just top-level nodes.
 * - Both agent AND artifact nodes are grouped into round containers.
 * - applyPositions uses a direct import (not dynamic) to avoid race conditions.
 */

import ELK from 'elkjs/lib/elk.bundled.js';
import { graphNodes } from './store.js';

const elk = new ELK();

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.layered.spacing.nodeNodeBetweenLayers': '80',
  'elk.spacing.nodeNode': '40',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
};

// Debounce layout calculations
let layoutTimer = null;
let lastNodeCount = 0;
let lastEdgeCount = 0;

/**
 * Apply ELK layout to the given nodes and edges.
 * Only recalculates when topology changes (node/edge count differs).
 * Updates node positions in the graphNodes store — but ONLY for nodes
 * that don't already have a position (incremental layout).
 *
 * @param {Array} nodes - Svelte Flow compatible nodes
 * @param {Array} edges - Svelte Flow compatible edges
 */
export async function applyLayout(nodes, edges) {
  // Skip if topology hasn't changed
  if (nodes.length === lastNodeCount && edges.length === lastEdgeCount) {
    return;
  }

  // Debounce rapid updates
  if (layoutTimer) {
    clearTimeout(layoutTimer);
  }

  layoutTimer = setTimeout(async () => {
    lastNodeCount = nodes.length;
    lastEdgeCount = edges.length;

    try {
      const positions = await calculateLayout(nodes, edges);
      if (positions) {
        applyPositions(positions);
      }
    } catch (err) {
      console.warn('[workflow/layout] ELK layout failed:', err);
    }
  }, 30);
}

/**
 * Calculate ELK layout positions for the given graph.
 *
 * @param {Array} nodes
 * @param {Array} edges
 * @returns {Promise<Map<string, {x: number, y: number}>>|null}
 */
async function calculateLayout(nodes, edges) {
  if (nodes.length === 0) return null;

  // Build ELK graph structure
  // Group nodes by round into containers (agents AND artifacts)
  const roundContainers = new Map();
  const topLevelNodes = [];

  for (const node of nodes) {
    const round = node.data?.round;
    // Group agent, artifact, and input nodes with a valid round into containers
    // Skip user_action, placeholder, decision — they stay at top level
    if (round != null && round > 0 && (node.type === 'agent' || node.type === 'artifact' || node.type === 'input' || node.type === 'decision')) {
      if (!roundContainers.has(round)) {
        roundContainers.set(round, []);
      }
      roundContainers.get(round).push(node);
    } else {
      topLevelNodes.push(node);
    }
  }

  // Build ELK children
  const elkChildren = [];

  // Add round containers as hierarchical parent nodes
  for (const [round, roundNodes] of roundContainers) {
    elkChildren.push({
      id: `round_container_${round}`,
      layoutOptions: {
        'elk.partitioning.partition': String(round),
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.spacing.nodeNode': '30',
      },
      children: roundNodes.map(n => ({
        id: n.id,
        width: getNodeWidth(n),
        height: getNodeHeight(n),
      })),
    });
  }

  // Add top-level nodes (input, artifacts without round, user actions, placeholders)
  for (const node of topLevelNodes) {
    elkChildren.push({
      id: node.id,
      width: getNodeWidth(node),
      height: getNodeHeight(node),
    });
  }

  // Build ELK edges
  const elkEdges = edges.map(e => ({
    id: e.id,
    sources: [e.source],
    targets: [e.target],
  }));

  const elkGraph = {
    id: 'root',
    layoutOptions: elkOptions,
    children: elkChildren,
    edges: elkEdges,
  };

  const result = await elk.layout(elkGraph);

  // Extract positions from result (recursively for nested children)
  const positions = new Map();

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
 * Apply calculated positions back to the graphNodes store.
 * Uses a direct import (not dynamic) to avoid race conditions.
 *
 * INCREMENTAL: Only updates nodes that don't already have a position.
 * This prevents ELK from overwriting the good initial positions set by
 * graphReducer's getInitialPosition() — fixing the "node stacking" bug.
 *
 * @param {Map<string, {x: number, y: number}>} positions
 */
function applyPositions(positions) {
  graphNodes.update(nodes => {
    const copy = new Map(nodes);
    for (const [id, pos] of positions) {
      const node = copy.get(id);
      // Only apply ELK position if node doesn't already have one
      if (node && !node.position) {
        copy.set(id, { ...node, position: pos });
      }
    }
    return copy;
  });
}

/**
 * Get display width for a node type.
 * @param {Object} node
 * @returns {number}
 */
function getNodeWidth(node) {
  switch (node.type) {
    case 'agent': return 200;
    case 'input': return 160;
    case 'artifact': return 180;
    case 'user_action': return 160;
    case 'placeholder': return 140;
    case 'decision': return 180;
    default: return 160;
  }
}

/**
 * Get display height for a node type.
 * @param {Object} node
 * @returns {number}
 */
function getNodeHeight(node) {
  switch (node.type) {
    case 'agent': return 80;
    case 'input': return 60;
    case 'artifact': return 60;
    case 'user_action': return 70;
    case 'placeholder': return 50;
    case 'decision': return 80;
    default: return 60;
  }
}
