/**
 * ELK.js Layout Engine
 *
 * Wraps ELK.js to calculate automatic node positioning for non-linear workflows.
 * Uses the layered algorithm with round containers as ELK parent nodes.
 */

import ELK from 'elkjs/lib/elk.bundled.js';

const elk = new ELK();

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.layered.spacing.nodeNodeBetweenLayers': '80',
  'elk.spacing.nodeNode': '40',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.partitioning.activate': 'true',
};

// Debounce layout calculations
let layoutTimer = null;
let lastNodeCount = 0;
let lastEdgeCount = 0;

/**
 * Apply ELK layout to the given nodes and edges.
 * Only recalculates when topology changes (node/edge count differs).
 * Updates node positions in the graphNodes store.
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
  }, 150);
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
  // Group nodes by round into containers
  const roundContainers = new Map();
  const topLevelNodes = [];

  for (const node of nodes) {
    const round = node.data?.round;
    if (round != null && node.type === 'agent') {
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

  // Add round containers
  for (const [round, roundNodes] of roundContainers) {
    elkChildren.push({
      id: `round_container_${round}`,
      layoutOptions: {
        'elk.partitioning.partition': String(round),
      },
      children: roundNodes.map(n => ({
        id: n.id,
        width: getNodeWidth(n),
        height: getNodeHeight(n),
      })),
    });
  }

  // Add top-level nodes (input, artifacts, user actions, placeholders)
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

  // Extract positions from result
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
 * @param {Map<string, {x: number, y: number}>} positions
 */
function applyPositions(positions) {
  // We need to import dynamically to avoid circular deps at module level
  // But since this is called from useWorkflowGraph which already imports store,
  // we can import here
  import('./store.js').then(({ graphNodes }) => {
    graphNodes.update(nodes => {
      for (const [id, pos] of positions) {
        const node = nodes.get(id);
        if (node) {
          node.position = pos;
        }
      }
      return nodes;
    });
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
    case 'artifact': return 180;
    case 'user_action': return 160;
    case 'placeholder': return 140;
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
    case 'artifact': return 60;
    case 'user_action': return 70;
    case 'placeholder': return 50;
    default: return 60;
  }
}
