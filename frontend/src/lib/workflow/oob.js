/**
 * OOB (Out-of-Band) Input Queue & Actions
 *
 * Allows users to inject additional context into a running debate
 * without interrupting the current agent execution.
 *
 * Migrated from Svelte 4 store.update()/.get() pattern to Svelte 5 $state direct mutation.
 */

/**
 * @typedef {'append'|'inject_now'|'override_context'} OOBUrgency
 *
 * @typedef {Object} OOBTarget
 * @property {'specific_agent'|'next_agent'|'all_future'|'current_active'} type
 * @property {string} [agentRole] - For specific_agent
 * @property {number} [round] - For specific_agent
 * @property {string} [currentAgentRole] - For next_agent
 * @property {number} [fromRound] - For all_future
 *
 * @typedef {Object} OOBInput
 * @property {string} id
 * @property {string} content
 * @property {OOBTarget} target
 * @property {number} timestamp
 * @property {OOBUrgency} urgency
 * @property {'pending'|'consumed'|'stale'} status
 * @property {string} [consumedBy]
 * @property {number} [consumedAt]
 */

/**
 * Submit an OOB input to the queue.
 * Immediately emits USER_OUT_OF_BAND_INPUT event for visualization.
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {Omit<OOBInput, 'id'|'timestamp'|'status'>} input
 * @returns {string} The OOB input ID
 */
export function submitOOBInput(store, input) {
  const id = `oob_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  const newOOB = {
    ...input,
    id,
    timestamp: Date.now(),
    status: 'pending',
  };

  const newItems = [...store.oobQueueItems, newOOB];

  // Update index for fast lookup (create new Map for reactivity)
  const newIndex = new Map(store.oobQueueIndexByTarget);
  const key = getOOBIndexKey(newOOB.target);
  const existing = newIndex.get(key) || [];
  newIndex.set(key, [...existing, newOOB]);

  store.oobQueueItems = newItems;
  store.oobQueueIndexByTarget = newIndex;

  // Immediately emit event for visualization
  store.dispatchEvent({
    type: 'USER_OUT_OF_BAND_INPUT',
    payload: {
      inputId: id,
      targetAgentId: resolveTargetAgentId(store, input.target),
      content: input.content,
      round: store.runtimeCurrentRound,
    },
  });

  return id;
}

/**
 * Consume all pending OOB inputs for a specific agent at a given round.
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {string} agentRole
 * @param {number} round
 * @returns {OOBInput[]}
 */
export function consumeOOBForAgent(store, agentRole, round) {
  const relevant = [];

  // 1. Specific for this agent in this round
  const specificKey = `specific:${agentRole}:${round}`;
  relevant.push(...(store.oobQueueIndexByTarget.get(specificKey) || []));

  // 2. "Next agent" — if the previous agent targeted this one
  const prevRole = getPreviousRole(agentRole);
  const nextKey = `next:${prevRole}`;
  relevant.push(...(store.oobQueueIndexByTarget.get(nextKey) || []));

  // 3. "All future" from this round onwards
  store.oobQueueItems.forEach((item) => {
    if (item.target.type === 'all_future'
        && item.target.fromRound <= round
        && item.status === 'pending') {
      relevant.push(item);
    }
  });

  // 4. "Current active"
  const currentKey = 'current:any';
  relevant.push(...(store.oobQueueIndexByTarget.get(currentKey) || []));

  // Remove duplicates and filter only pending
  const unique = Array.from(new Map(relevant.map(o => [o.id, o])).values())
    .filter(o => o.status === 'pending');

  return unique;
}

/**
 * Mark an OOB input as consumed by a specific agent.
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {string} oobId
 * @param {string} agentId
 */
export function markOOBConsumed(store, oobId, agentId) {
  store.oobQueueItems = store.oobQueueItems.map(o =>
    o.id === oobId
      ? { ...o, status: 'consumed', consumedBy: agentId, consumedAt: Date.now() }
      : o
  );
}

/**
 * Get count of pending OOB inputs.
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @returns {number}
 */
export function getPendingOOBCount(store) {
  return store.oobQueueItems.filter(o => o.status === 'pending').length;
}

/**
 * Mark stale OOB inputs (older than threshold).
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {number} olderThanMs
 */
export function clearStaleOOB(store, olderThanMs) {
  const cutoff = Date.now() - olderThanMs;
  store.oobQueueItems = store.oobQueueItems.map(o =>
    o.status === 'pending' && o.timestamp < cutoff
      ? { ...o, status: 'stale' }
      : o
  );
}

// ─── Helpers ───

function getOOBIndexKey(target) {
  switch (target.type) {
    case 'specific_agent': return `specific:${target.agentRole}:${target.round || 'any'}`;
    case 'next_agent': return `next:${target.currentAgentRole}`;
    case 'all_future': return `future:${target.fromRound}`;
    case 'current_active': return 'current:any';
    default: return 'unknown';
  }
}

function resolveTargetAgentId(store, target) {
  if (target.type === 'specific_agent') {
    const found = Array.from(store.graphNodes.values())
      .filter(n => n.type === 'agent' && n.data.role === target.agentRole)
      .sort((a, b) => b.data.round - a.data.round);
    return found[0]?.id || `pending_${target.agentRole}`;
  }
  return 'pending_dynamic';
}

function getPreviousRole(role) {
  const order = ['strategist', 'critic', 'fact-checker', 'optimizer', 'moderator', 'analyst', 'creative'];
  const idx = order.indexOf(role);
  return idx > 0 ? order[idx - 1] : 'input';
}
