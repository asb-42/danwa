/**
 * ELK.js Layout Engine — Workflow
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
 *
 * Race-condition safety:
 * - Debounce timer reads fresh data from the store when it fires,
 *   not stale closure-captured values.
 * - A generation counter ensures only the latest layout result is applied.
 * - The $effect in WorkflowCanvas returns a cleanup function that cancels
 *   pending layout timers on component unmount.
 */

import { workflowStore } from './store.svelte.js';
import { runLayout } from '../elk-service.js';

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.layered.spacing.nodeNodeBetweenLayers': '80',
  'elk.spacing.nodeNode': '40',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
};

// ─── Debounce + Generation Counter ────────────────────────────────
// Prevents race conditions when multiple SSE events fire in quick succession.
// The timer always reads fresh data from the store when it fires,
// and only the latest generation's result is applied.

let layoutTimer = null;
let layoutGeneration = 0;

/**
 * Schedule an ELK layout calculation.
 *
 * Uses a debounce timer (100ms) so rapid topology changes don't trigger
 * redundant layout runs. When the timer fires, it reads the current
 * node/edge state directly from the store (not from stale closures).
 *
 * @returns {() => void} Cleanup function to cancel the pending layout.
 */
export function scheduleLayout() {
  // Cancel any pending layout
  if (layoutTimer) {
    clearTimeout(layoutTimer);
    layoutTimer = null;
  }

  // Bump generation — invalidates any in-flight layout calculations
  layoutGeneration++;
  const currentGeneration = layoutGeneration;

  layoutTimer = setTimeout(async () => {
    layoutTimer = null;

    // Read fresh data from the store at execution time
    const nodes = workflowStore.flowNodes;
    const edges = workflowStore.flowEdges;

    if (nodes.length === 0) return;

    try {
      const positions = await calculateLayout(nodes, edges);
      if (positions && currentGeneration === layoutGeneration) {
        applyPositions(positions);
      }
    } catch (err) {
      console.warn('[workflow/layout] ELK layout failed:', err);
    }
  }, 100);

  // Return cleanup function for $effect
  return () => {
    if (layoutTimer) {
      clearTimeout(layoutTimer);
      layoutTimer = null;
    }
  };
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
  //
  // Layout hierarchy:
  //   root
  //   ├── round_container_1
  //   │   ├── strategist_r1 (agent)
  //   │   ├── strategy_r1   (artifact)
  //   │   └── ...
  //   ├── round_container_2
  //   │   └── ...
  //   ├── input             (top-level, round 0)
  //   ├── decision_r1       (top-level, between rounds)
  //   ├── user_action_x     (top-level, HITL)
  //   └── placeholder_x     (top-level, pending agents)

  const roundContainers = new Map(); // Map<round, Node[]>
  const topLevelNodes = [];

  for (const node of nodes) {
    const round = node.data?.round;

    // Only agent and artifact nodes with round > 0 go into round containers.
    // Everything else stays at the top level:
    //   - input (round 0) — entry point before all rounds
    //   - decision — sits between rounds
    //   - user_action — HITL nodes, positioned by ELK based on edges
    //   - placeholder — pending agents waiting to appear
    //   - a2a_agent — external agents, not part of the round pipeline
    const isRoundScoped = round != null && round > 0
      && (node.type === 'agent' || node.type === 'artifact');

    if (isRoundScoped) {
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

  // Add top-level nodes (input, decision, user_action, placeholder, a2a_agent)
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

  const result = await runLayout(elkGraph);

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
 *
 * INCREMENTAL: Only updates nodes that don't already have a position.
 * This prevents ELK from overwriting the good initial positions set by
 * graphReducer's getInitialPosition() — fixing the "node stacking" bug.
 *
 * @param {Map<string, {x: number, y: number}>} positions
 */
function applyPositions(positions) {
  for (const [id, pos] of positions) {
    const node = workflowStore.graphNodes.get(id);
    // Only apply ELK position if node doesn't already have one
    if (node && !node.position) {
      node.position = pos;
    }
  }
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
