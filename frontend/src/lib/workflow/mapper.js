/**
 * SSE → Workflow Event Mapping
 *
 * Maps incoming SSE events from the backend to workflow events
 * and dispatches them to the workflow store.
 * Called from DebateView's handleSSEEvent().
 */

import { workflowStore } from './store.svelte.js';
import { PIPELINE_ROLES, ROLE_ARTIFACT_MAP } from './constants.js';

/**
 * Map incoming SSE events to workflow events and dispatch them.
 * @param {Object} sseEvent - Raw SSE event from backend
 */
export function handleWorkflowSSE(sseEvent) {
  switch (sseEvent.type) {

    case 'workflow_started':
      // Initialize graph with input node
      workflowStore.dispatchEvent({
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
      // Detect A2A agents by phase === 'a2a_invocation'
      if (sseEvent.phase === 'a2a_invocation') {
        workflowStore.dispatchEvent({
          type: 'AGENT_STARTED',
          payload: {
            agentId: `${sseEvent.role}_r${sseEvent.round}`,
            role: sseEvent.role,
            round: sseEvent.round,
            inputArtifactIds: getInputArtifacts(sseEvent.role, sseEvent.round),
            timestamp: Date.now(),
            isA2A: true,
            agentUrl: sseEvent.agent_url || '',
          },
        });
      } else {
        workflowStore.dispatchEvent({
          type: 'AGENT_STARTED',
          payload: {
            agentId: `${sseEvent.role}_r${sseEvent.round}`,
            role: sseEvent.role,
            round: sseEvent.round,
            inputArtifactIds: getInputArtifacts(sseEvent.role, sseEvent.round),
            timestamp: Date.now(),
          },
        });
      }
      break;

    case 'agent_started':
      // Agent profile resolved — update node with profile info
      workflowStore.dispatchEvent({
        type: 'AGENT_STARTED',
        payload: {
          agentId: `${sseEvent.role}_r${sseEvent.round}`,
          role: sseEvent.role,
          round: sseEvent.round,
          inputArtifactIds: getInputArtifacts(sseEvent.role, sseEvent.round),
          timestamp: Date.now(),
          profile: sseEvent.profile,
          model: sseEvent.model,
        },
      });
      break;

    case 'agent_output':
      // Agent completed — produce artifact
      {
        const artifactId = `${sseEvent.role}_output_r${sseEvent.round}`;
        workflowStore.dispatchEvent({
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
        workflowStore.dispatchEvent({
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
      {
        // Handle both flat and nested data structures
        // Backend may send: {"round": X, "data": {...}} or {"round": X, "consensus": Y, ...}
        const roundData = sseEvent.data || sseEvent;
        const consensus = roundData.consensus ?? sseEvent.consensus ?? null;
        const threshold = roundData.threshold ?? sseEvent.threshold ?? 0.8;
        const passed = consensus != null && consensus >= threshold;

        // First dispatch CONSENSUS_CHECK to create/update the decision node
        if (consensus != null) {
          workflowStore.dispatchEvent({
            type: 'CONSENSUS_CHECK',
            payload: {
              decisionId: `decision_r${sseEvent.round}`,
              round: sseEvent.round,
              consensus,
              threshold,
              passed,
            },
          });
        }

        // Then dispatch ROUND_COMPLETED
        workflowStore.dispatchEvent({
          type: 'ROUND_COMPLETED',
          payload: {
            round: sseEvent.round,
            finalArtifactId: `moderator_output_r${sseEvent.round}`,
            pathTaken: [],
            consensus,
            threshold,
          },
        });
      }
      break;

    case 'oob_consumed':
      workflowStore.dispatchEvent({
        type: 'OOB_CONSUMED',
        payload: {
          oobIds: sseEvent.oob_ids || [],
          byAgentId: sseEvent.by_agent || '',
        },
      });
      break;

    case 'web_search':
      workflowStore.dispatchEvent({
        type: 'AGENT_ACTIVITY',
        payload: {
          agentId: `${sseEvent.role}_r${sseEvent.round}`,
          activity: 'searching',
          detail: sseEvent.query || '',
        },
      });
      break;

    case 'llm_call_started':
      workflowStore.dispatchEvent({
        type: 'AGENT_ACTIVITY',
        payload: {
          agentId: `${sseEvent.role}_r${sseEvent.round}`,
          activity: 'thinking',
          detail: '',
        },
      });
      break;

    case 'hitl_inject_consumed':
      workflowStore.dispatchEvent({
        type: 'USER_OUT_OF_BAND_INPUT',
        payload: {
          inputId: sseEvent.interaction_id || `inject_${Date.now()}`,
          targetAgentId: `${sseEvent.target_agent}_r${sseEvent.target_round || 1}`,
          content: sseEvent.content || 'HITL context injected',
          round: sseEvent.target_round || 1,
        },
      });
      break;

    case 'status_change':
      if (sseEvent.status === 'completed' || sseEvent.status === 'failed') {
        workflowStore.dispatchEvent({
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
 * Uses the shared PIPELINE_ROLES constant for consistent ordering.
 * @param {string} role
 * @param {number} round
 * @returns {string[]}
 */
function getInputArtifacts(role, round) {
  if (round === 1 && role === 'strategist') return ['input'];
  // For subsequent agents in same round, use previous agent's output
  const idx = PIPELINE_ROLES.indexOf(role);
  if (idx > 0) return [`${PIPELINE_ROLES[idx - 1]}_output_r${round}`];
  // A2A agents (custom roles not in pipeline) receive moderator output as input
  // since they run after all standard agents
  if (!PIPELINE_ROLES.includes(role)) return [`moderator_output_r${round}`];
  // For first agent of new round, use previous round's moderator output
  return [`moderator_output_r${round - 1}`];
}

/**
 * Map an agent role to an artifact type.
 * Uses the shared ROLE_ARTIFACT_MAP constant.
 * @param {string} role
 * @returns {string}
 */
function mapRoleToArtifactType(role) {
  // A2A agents produce 'synthesis' type artifacts
  return ROLE_ARTIFACT_MAP[role] || 'synthesis';
}
