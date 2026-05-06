/**
 * SSE → Workflow Event Mapping
 *
 * Maps incoming SSE events from the backend to workflow events
 * and dispatches them to the workflow store.
 * Called from DebateView's handleSSEEvent().
 */

import { dispatchEvent } from './store.js';

/**
 * Map incoming SSE events to workflow events and dispatch them.
 * @param {Object} sseEvent - Raw SSE event from backend
 */
export function handleWorkflowSSE(sseEvent) {
  switch (sseEvent.type) {

    case 'workflow_started':
      // Initialize graph with input node
      dispatchEvent({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'input',
          role: 'input',
          round: 0,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });
      break;

    case 'agent_preparing':
      // Agent is resolving profile/prompts — show as active
      dispatchEvent({
        type: 'AGENT_STARTED',
        payload: {
          agentId: `${sseEvent.role}_r${sseEvent.round}`,
          role: sseEvent.role,
          round: sseEvent.round,
          inputArtifactIds: getInputArtifacts(sseEvent.role, sseEvent.round),
          timestamp: Date.now(),
        },
      });
      break;

    case 'agent_output':
      // Agent completed — produce artifact
      {
        const artifactId = `${sseEvent.role}_output_r${sseEvent.round}`;
        dispatchEvent({
          type: 'ARTIFACT_PRODUCED',
          payload: {
            artifactId,
            type: mapRoleToArtifactType(sseEvent.role),
            producerAgentId: `${sseEvent.role}_r${sseEvent.round}`,
            round: sseEvent.round,
            summary: sseEvent.content?.substring(0, 100) || '',
            tokenCount: sseEvent.tokens || 0,
          },
        });
        dispatchEvent({
          type: 'AGENT_COMPLETED',
          payload: {
            agentId: `${sseEvent.role}_r${sseEvent.round}`,
            role: sseEvent.role,
            round: sseEvent.round,
            outputArtifactId: artifactId,
            durationMs: sseEvent.duration_ms || 0,
          },
        });
      }
      break;

    case 'round_update':
      dispatchEvent({
        type: 'ROUND_COMPLETED',
        payload: {
          round: sseEvent.round,
          finalArtifactId: `moderator_output_r${sseEvent.round}`,
          pathTaken: [], // Will be filled from executionPath
        },
      });
      break;

    case 'status_change':
      if (sseEvent.status === 'completed' || sseEvent.status === 'failed') {
        dispatchEvent({
          type: 'WORKFLOW_COMPLETED',
          payload: {
            finalConsensusId: 'final',
            totalRounds: sseEvent.round || 0,
            totalDurationMs: 0,
          },
        });
      }
      break;
  }
}

/**
 * Get the artifact IDs that serve as input for a given agent role and round.
 * @param {string} role
 * @param {number} round
 * @returns {string[]}
 */
function getInputArtifacts(role, round) {
  if (round === 1 && role === 'strategist') return ['input'];
  // For subsequent agents in same round, use previous agent's output
  const roles = ['strategist', 'critic', 'optimizer', 'moderator'];
  const idx = roles.indexOf(role);
  if (idx > 0) return [`${roles[idx - 1]}_output_r${round}`];
  // For first agent of new round, use previous round's moderator output
  return [`moderator_output_r${round - 1}`];
}

/**
 * Map an agent role to an artifact type.
 * @param {string} role
 * @returns {string}
 */
function mapRoleToArtifactType(role) {
  const map = {
    strategist: 'strategy',
    critic: 'critique',
    optimizer: 'synthesis',
    moderator: 'consensus',
  };
  return map[role] || 'synthesis';
}
