/**
 * Runtime Reducer — Event → Runtime Status Update
 *
 * Updates the runtime state (active node, current round, status)
 * based on incoming workflow events.
 *
 * IMPORTANT: Must return new object references for Svelte reactivity.
 */

import { runtime } from './store.js';

/**
 * Apply a workflow event to the runtime state.
 * @param {import('./events.js').WorkflowEvent} event
 */
export function applyEventToRuntime(event) {
  switch (event.type) {

    case 'AGENT_STARTED':
      runtime.update(r => ({
        ...r,
        activeNodeId: event.payload.agentId,
        status: 'running',
        currentRound: event.payload.round,
        executionPath: [...r.executionPath, event.payload.agentId],
      }));
      break;

    case 'AGENT_COMPLETED':
      runtime.update(r => ({
        ...r,
        activeNodeId: null,
        activeEdgeId: null,
      }));
      break;

    case 'ARTIFACT_PRODUCED':
      runtime.update(r => ({
        ...r,
        activeEdgeId: `${event.payload.producerAgentId}->${event.payload.artifactId}`,
      }));
      break;

    case 'USER_CLARIFICATION_REQUESTED':
      runtime.update(r => ({
        ...r,
        status: 'waiting_for_user',
        blockingUserRequestId: event.payload.requestId,
        activeNodeId: `user_action_${event.payload.requestId}`,
      }));
      break;

    case 'USER_CLARIFICATION_RECEIVED':
      runtime.update(r => ({
        ...r,
        status: 'running',
        blockingUserRequestId: null,
        activeNodeId: event.payload.respondingToAgentId,
      }));
      break;

    case 'ROUND_COMPLETED':
      runtime.update(r => ({
        ...r,
        currentRound: event.payload.round + 1,
        activeNodeId: null,
        activeEdgeId: null,
      }));
      break;

    case 'CONSENSUS_CHECK':
      // No runtime state change needed — decision node is visual only
      break;

    case 'AGENT_ACTIVITY':
      // No runtime state change needed — activity is shown on the node
      break;

    case 'WORKFLOW_COMPLETED':
      runtime.update(r => ({
        ...r,
        status: 'completed',
        activeNodeId: null,
        activeEdgeId: null,
      }));
      break;

    default:
      break;
  }
}
