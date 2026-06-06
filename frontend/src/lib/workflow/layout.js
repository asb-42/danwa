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

/** Padding inside phase containers (px). */
const PHASE_CONTAINER_PADDING = 60;

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
  // Supports two grouping strategies (mutually exclusive based on node data):
  //
  // A) Phase grouping (from workflow definitions with wf-phase nodes):
  //   root
  //   ├── phase-1 (container)
  //   │   ├── analyst-1
  //   │   ├── creative-1
  //   │   └── socratic-1
  //   ├── phase-2 (container)
  //   │   └── ...
  //   ├── gate-1 (top-level, between phases)
  //   └── input-1 (top-level, before phases)
  //
  // B) Round grouping (from live debate SSE events):
  //   root
  //   ├── round_container_1
  //   │   ├── strategist_r1 (agent)
  //   │   ├── strategy_r1   (artifact)
  //   │   └── ...
  //   ├── input             (top-level, round 0)
  //   └── decision_r1       (top-level, between rounds)

  // Detect phase containers (type === 'phase' or parent_id-based grouping)
  const phaseNodes = nodes.filter(n => n.type === 'phase');
  const phaseIds = new Set(phaseNodes.map(n => n.id));

  const phaseChildren = new Map(); // phaseId -> Node[]
  const topLevelNodes = [];

  if (phaseIds.size > 0) {
    // Phase grouping mode
    for (const node of nodes) {
      if (node.type === 'phase') continue; // Phase containers handled separately
      const parentId = node.parentId;
      if (parentId && phaseIds.has(parentId)) {
        if (!phaseChildren.has(parentId)) {
          phaseChildren.set(parentId, []);
        }
        phaseChildren.get(parentId).push(node);
      } else {
        topLevelNodes.push(node);
      }
    }
  } else {
    // Round grouping mode (existing behavior)
    const roundContainers = new Map(); // Map<round, Node[]>

    for (const node of nodes) {
      const round = node.data?.round;
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

    // Convert round containers into pseudo-phase entries for unified ELK building
    for (const [round, roundNodes] of roundContainers) {
      const containerId = `round_container_${round}`;
      phaseIds.add(containerId);
      phaseChildren.set(containerId, roundNodes);
      phaseNodes.push({ id: containerId, type: 'round_container', data: { round } });
    }
  }

  // Build ELK children
  const elkChildren = [];

  // Add phase/round containers as hierarchical parent nodes
  for (const phase of phaseNodes) {
    const children = phaseChildren.get(phase.id) || [];
    const childDims = children.map(n => ({
      id: n.id,
      width: getNodeWidth(n),
      height: getNodeHeight(n),
    }));

    // Compute container size from children bounds + padding
    if (phase.type === 'phase') {
      elkChildren.push({
        id: phase.id,
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': 'RIGHT',
          'elk.spacing.nodeNode': '30',
          'elk.padding': `[top=${PHASE_CONTAINER_PADDING},left=${PHASE_CONTAINER_PADDING / 2},bottom=${PHASE_CONTAINER_PADDING / 2},right=${PHASE_CONTAINER_PADDING / 2}]`,
        },
        width: 300 + PHASE_CONTAINER_PADDING,
        height: 200 + PHASE_CONTAINER_PADDING,
        children: childDims,
      });
    } else {
      // Round container (existing behavior)
      elkChildren.push({
        id: phase.id,
        layoutOptions: {
          'elk.partitioning.partition': String(phase.data?.round || 0),
          'elk.algorithm': 'layered',
          'elk.direction': 'RIGHT',
          'elk.spacing.nodeNode': '30',
        },
        children: childDims,
      });
    }
  }

  // Add top-level nodes
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
    case 'phase': return 300;
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
    case 'phase': return 200;
    default: return 60;
  }
}
