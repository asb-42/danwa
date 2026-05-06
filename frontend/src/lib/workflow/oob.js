/**
 * OOB (Out-of-Band) Input Queue & Actions
 *
 * Allows users to inject additional context into a running debate
 * without interrupting the current agent execution.
 */

import { get } from 'svelte/store';
import { oobQueue, graphNodes, runtime, dispatchEvent } from './store.js';

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
 * @param {Omit<OOBInput, 'id'|'timestamp'|'status'>} input
 * @returns {string} The OOB input ID
 */
export function submitOOBInput(input) {
  const id = `oob_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  const newOOB = {
    ...input,
    id,
    timestamp: Date.now(),
    status: 'pending',
  };

  oobQueue.update(q => {
    q.items.push(newOOB);

    // Update index for fast lookup
    const key = getOOBIndexKey(newOOB.target);
    if (!q.indexByTarget.has(key)) {
      q.indexByTarget.set(key, []);
    }
    q.indexByTarget.get(key).push(newOOB);

    return q;
  });

  // Immediately emit event for visualization
  dispatchEvent({
    type: 'USER_OUT_OF_BAND_INPUT',
    payload: {
      inputId: id,
      targetAgentId: resolveTargetAgentId(input.target),
      content: input.content,
      round: get(runtime).currentRound,
    },
  });

  return id;
}

/**
 * Consume all pending OOB inputs for a specific agent at a given round.
 * @param {string} agentRole
 * @param {number} round
 * @returns {OOBInput[]}
 */
export function consumeOOBForAgent(agentRole, round) {
  const q = get(oobQueue);
  const relevant = [];

  // 1. Specific for this agent in this round
  const specificKey = `specific:${agentRole}:${round}`;
  relevant.push(...(q.indexByTarget.get(specificKey) || []));

  // 2. "Next agent" — if the previous agent targeted this one
  const prevRole = getPreviousRole(agentRole);
  const nextKey = `next:${prevRole}`;
  relevant.push(...(q.indexByTarget.get(nextKey) || []));

  // 3. "All future" from this round onwards
  q.items.forEach((item) => {
    if (item.target.type === 'all_future'
        && item.target.fromRound <= round
        && item.status === 'pending') {
      relevant.push(item);
    }
  });

  // 4. "Current active"
  const currentKey = 'current:any';
  relevant.push(...(q.indexByTarget.get(currentKey) || []));

  // Remove duplicates and filter only pending
  const unique = Array.from(new Map(relevant.map(o => [o.id, o])).values())
    .filter(o => o.status === 'pending');

  return unique;
}

/**
 * Mark an OOB input as consumed by a specific agent.
 * @param {string} oobId
 * @param {string} agentId
 */
export function markOOBConsumed(oobId, agentId) {
  oobQueue.update(q => {
    const oob = q.items.find(o => o.id === oobId);
    if (oob) {
      oob.status = 'consumed';
      oob.consumedBy = agentId;
      oob.consumedAt = Date.now();
    }
    return q;
  });
}

/**
 * Get count of pending OOB inputs.
 * @returns {number}
 */
export function getPendingOOBCount() {
  return get(oobQueue).items.filter(o => o.status === 'pending').length;
}

/**
 * Mark stale OOB inputs (older than threshold).
 * @param {number} olderThanMs
 */
export function clearStaleOOB(olderThanMs) {
  const cutoff = Date.now() - olderThanMs;
  oobQueue.update(q => {
    q.items.forEach(o => {
      if (o.status === 'pending' && o.timestamp < cutoff) {
        o.status = 'stale';
      }
    });
    return q;
  });
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

function resolveTargetAgentId(target) {
  const nodes = get(graphNodes);
  if (target.type === 'specific_agent') {
    const found = Array.from(nodes.values())
      .filter(n => n.type === 'agent' && n.data.role === target.agentRole)
      .sort((a, b) => b.data.round - a.data.round);
    return found[0]?.id || `pending_${target.agentRole}`;
  }
  return 'pending_dynamic';
}

function getPreviousRole(role) {
  const order = ['strategist', 'critic', 'optimizer', 'moderator'];
  const idx = order.indexOf(role);
  return idx > 0 ? order[idx - 1] : 'input';
}
