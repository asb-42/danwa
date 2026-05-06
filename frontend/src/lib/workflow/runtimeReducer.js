/**
 * Runtime Reducer — Event → Runtime Status Update
 *
 * Tracks who is currently active, the current round,
 * and whether the workflow is waiting for user input.
 */

import { runtime } from './store.js';

/**
 * Apply a workflow event to the runtime state.
 * @param {import('./events.js').WorkflowEvent} event
 */
export function applyEventToRuntime(event) {
  switch (event.type) {

    case 'AGENT_STARTED': {
      runtime.update(r => ({
        ...r,
        status: 'running',
        activeNodeId: event.payload.agentId,
        activeEdgeId: null,
        executionPath: [...r.executionPath, event.payload.agentId],
      }));
      break;
    }

    case 'AGENT_COMPLETED': {
      runtime.update(r => ({
        ...r,
        activeNodeId: null,
      }));
      break;
    }

    case 'USER_CLARIFICATION_REQUESTED': {
      runtime.update(r => ({
        ...r,
        status: 'waiting_for_user',
        blockingUserRequestId: event.payload.requestId,
        activeNodeId: `user_action_${event.payload.requestId}`,
      }));
      break;
    }

    case 'USER_CLARIFICATION_RECEIVED': {
      runtime.update(r => ({
        ...r,
        status: 'running',
        blockingUserRequestId: null,
        activeNodeId: null,
      }));
      break;
    }

    case 'ROUND_COMPLETED': {
      runtime.update(r => ({
        ...r,
        currentRound: event.payload.round + 1,
        activeNodeId: null,
        activeEdgeId: null,
      }));
      break;
    }

    case 'WORKFLOW_COMPLETED': {
      runtime.update(r => ({
        ...r,
        status: 'completed',
        activeNodeId: null,
        activeEdgeId: null,
      }));
      break;
    }
  }
}
