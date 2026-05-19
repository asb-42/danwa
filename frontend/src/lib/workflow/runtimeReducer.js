/**
 * Runtime Reducer — Event → Runtime Status Update
 *
 * Updates the runtime state (active node, current round, status)
 * based on incoming workflow events.
 *
 * Migrated from Svelte 4 store.update() pattern to Svelte 5 $state direct mutation.
 */

/**
 * Apply a workflow event to the runtime state.
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {import('./events.js').WorkflowEvent} event
 */
export function applyEventToRuntime(store, event) {
  switch (event.type) {

    case 'AGENT_STARTED':
      store.runtimeActiveNodeId = event.payload.agentId;
      store.runtimeStatus = 'running';
      store.runtimeCurrentRound = event.payload.round;
      store.runtimeExecutionPath = [...store.runtimeExecutionPath, event.payload.agentId];
      break;

    case 'AGENT_COMPLETED':
      store.runtimeActiveNodeId = null;
      store.runtimeActiveEdgeId = null;
      break;

    case 'ARTIFACT_PRODUCED':
      store.runtimeActiveEdgeId = `${event.payload.producerAgentId}->${event.payload.artifactId}`;
      break;

    case 'USER_CLARIFICATION_REQUESTED':
      store.runtimeStatus = 'waiting_for_user';
      store.runtimeBlockingUserRequestId = event.payload.requestId;
      store.runtimeActiveNodeId = `user_action_${event.payload.requestId}`;
      break;

    case 'USER_CLARIFICATION_RECEIVED':
      store.runtimeStatus = 'running';
      store.runtimeBlockingUserRequestId = null;
      store.runtimeActiveNodeId = event.payload.respondingToAgentId;
      break;

    case 'ROUND_COMPLETED':
      store.runtimeCurrentRound = event.payload.round + 1;
      store.runtimeActiveNodeId = null;
      store.runtimeActiveEdgeId = null;
      break;

    case 'CONSENSUS_CHECK':
      // No runtime state change needed — decision node is visual only
      break;

    case 'AGENT_ACTIVITY':
      // No runtime state change needed — activity is shown on the node
      break;

    case 'WORKFLOW_COMPLETED':
      store.runtimeStatus = 'completed';
      store.runtimeActiveNodeId = null;
      store.runtimeActiveEdgeId = null;
      break;

    default:
      break;
  }
}
