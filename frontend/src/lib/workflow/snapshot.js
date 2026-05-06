/**
 * Snapshot System — Round Snapshots for Timeline
 *
 * Creates deep-copy snapshots of the current graph state at round boundaries.
 * Used for timeline view and audit trail.
 */

import { get } from 'svelte/store';
import { graphNodes, graphEdges, runtime, roundSnapshots } from './store.js';

/**
 * Create a deep-copy snapshot of the current graph state for a round.
 * @param {number} roundNumber
 */
export function createRoundSnapshot(roundNumber) {
  const nodes = get(graphNodes);
  const edges = get(graphEdges);
  const rt = get(runtime);

  const nodesSnapshot = Array.from(nodes.values()).map(n => ({
    ...n,
    data: { ...n.data, isActive: false, status: 'completed' },
  }));

  const edgesSnapshot = Array.from(edges.values()).map(e => ({
    ...e,
    data: { ...e.data, isActive: false },
  }));

  const snapshot = {
    round: roundNumber,
    title: `Round ${roundNumber}`,
    nodes: nodesSnapshot,
    edges: edgesSnapshot,
    executionPath: [...rt.executionPath],
    completedAt: Date.now(),
  };

  roundSnapshots.update(snaps => [...snaps, snapshot]);

  // Reset execution path for new round
  runtime.update(r => ({ ...r, executionPath: [] }));
}
