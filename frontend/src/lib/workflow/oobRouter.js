/**
 * OOB Router — Race-Condition Handling
 *
 * Routes OOB inputs to the correct target, handling race conditions:
 * - OOB before agent start → queued and injected at start
 * - OOB while agent runs → queued; agent gets it at next check
 * - OOB after agent done → forwarded to next agent
 * - OOB for agent that never comes → marked stale after timeout
 *
 * Migrated from Svelte 4 store pattern to Svelte 5 runes.
 * Now takes the workflowStore as a parameter (no module-level store coupling).
 */

import { workflowStore } from './store.svelte.js';

/**
 * Route an OOB input to the correct target, handling race conditions.
 *
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {import('./oob.js').OOBInput} oob
 * @returns {import('./oob.js').OOBTarget} Resolved target
 */
export function routeOOB(store, oob) {
  const rt = {
    status: store.runtimeStatus,
    activeNodeId: store.runtimeActiveNodeId,
    currentRound: store.runtimeCurrentRound,
  };
  const nodes = store.graphNodes;

  switch (oob.target.type) {
    case 'specific_agent': {
      const targetRole = oob.target.agentRole;
      const targetRound = oob.target.round || rt.currentRound;
      const agentNodeId = `${targetRole}_r${targetRound}`;
      const agentNode = nodes.get(agentNodeId);

      if (!agentNode) {
        // Agent doesn't exist yet → queue for later
        return oob.target;
      }

      if (agentNode.data.status === 'completed') {
        // Agent already done → forward to successor
        return { type: 'next_agent', currentAgentRole: targetRole };
      }

      // Agent is running or waiting → direct delivery
      return oob.target;
    }

    case 'current_active': {
      if (rt.activeNodeId && rt.status === 'running') {
        const role = extractRoleFromId(rt.activeNodeId);
        return {
          type: 'specific_agent',
          agentRole: role,
          round: rt.currentRound,
        };
      }
      // Nobody active → route to next in pipeline
      return { type: 'next_agent', currentAgentRole: 'input' };
    }

    default:
      return oob.target;
  }
}

/**
 * Extract role from a node ID like "strategist_r2".
 * @param {string} nodeId
 * @returns {string}
 */
function extractRoleFromId(nodeId) {
  const match = nodeId.match(/^(\w+)_r\d+$/);
  return match ? match[1] : nodeId;
}
