/**
 * Snapshot System — Round Snapshots for Timeline
 *
 * Creates deep-copy snapshots of the current graph state at round boundaries.
 * Used for timeline view and audit trail.
 *
 * Migrated from Svelte 4 store.get() pattern to Svelte 5 $state direct access.
 */

/**
 * Create a deep-copy snapshot of the current graph state for a round.
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {number} roundNumber
 */
export function createRoundSnapshot(store, roundNumber) {
  const nodesSnapshot = Array.from(store.graphNodes.values()).map(n => ({
    ...n,
    data: { ...n.data, isActive: false, status: 'completed' },
  }));

  const edgesSnapshot = Array.from(store.graphEdges.values()).map(e => ({
    ...e,
    data: { ...e.data, isActive: false },
  }));

  const snapshot = {
    round: roundNumber,
    title: `Round ${roundNumber}`,
    nodes: nodesSnapshot,
    edges: edgesSnapshot,
    executionPath: [...store.runtimeExecutionPath],
    completedAt: Date.now(),
  };

  store.roundSnapshots = [...store.roundSnapshots, snapshot];

  // Reset execution path for new round
  store.runtimeExecutionPath = [];
}
