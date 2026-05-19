/**
 * Graph Reducer — Event → Graph Mutation
 *
 * The heart of the workflow visualization. Each event type knows exactly
 * how it changes the graph (nodes and edges).
 *
 * Migrated from Svelte 4 store.update() pattern to Svelte 5 $state direct mutation.
 * $state creates deep reactive proxies, so Map.set/delete triggers reactivity directly.
 *
 * Pipeline order is defined in constants.js — not hardcoded here — so that
 * mapper.js, layout.js, and graphReducer.js all share the same source of truth.
 */

import { PIPELINE_ROLES, ARTIFACT_ROLE_MAP } from './constants.js';

// ── Initial position calculation ──────────────────────────────────
// Gives each node a reasonable starting position so the graph is
// readable even before ELK layout runs. ELK will refine these.
const NODE_SPACING_X = 220;
const ROUND_SPACING_Y = 200;

function getInitialPosition(nodeType, role, round) {
  if (role === 'input') return { x: -200, y: 0 };
  const r = role in ARTIFACT_ROLE_MAP ? ARTIFACT_ROLE_MAP[role] : role;
  const col = PIPELINE_ROLES.indexOf(r);
  const c = col >= 0 ? col : PIPELINE_ROLES.length; // Unknown roles go after last known
  const baseX = c * 2 * NODE_SPACING_X;
  const baseY = ((round || 1) - 1) * ROUND_SPACING_Y;
  if (nodeType === 'artifact') return { x: baseX + NODE_SPACING_X, y: baseY + 30 };
  if (nodeType === 'decision') return { x: PIPELINE_ROLES.length * 2 * NODE_SPACING_X + 80, y: baseY };
  if (nodeType === 'user_action') return { x: baseX + NODE_SPACING_X / 2, y: baseY - 90 };
  // A2A agents are positioned after the last pipeline role column
  if (nodeType === 'a2a_agent') return { x: (PIPELINE_ROLES.length) * 2 * NODE_SPACING_X, y: baseY };
  return { x: baseX, y: baseY };
}

/**
 * Apply a workflow event to the graph state.
 * @param {import('./store.svelte.js').WorkflowStore} store
 * @param {import('./events.js').WorkflowEvent} event
 */
export function applyEventToGraph(store, event) {
  const { graphNodes, graphEdges } = store;

  switch (event.type) {

    // ═══════════════════════════════════════════
    // AGENT_STARTED
    // ═══════════════════════════════════════════
    case 'AGENT_STARTED': {
      const { agentId, role, round, inputArtifactIds, profile, model, isA2A, agentUrl } = event.payload;

      if (!graphNodes.has(agentId)) {
        const nodeType = role === 'input' ? 'input' : isA2A ? 'a2a_agent' : 'agent';
        graphNodes.set(agentId, {
          id: agentId,
          type: nodeType,
          data: {
            role,
            label: role === 'input' ? 'Input' : isA2A ? `${role} (A2A · Round ${round})` : `${role} (Round ${round})`,
            status: 'active',
            round,
            isActive: true,
            hasFeedbackLoop: false,
            profile: profile || undefined,
            model: model || undefined,
            agentUrl: agentUrl || undefined,
          },
          position: getInitialPosition(nodeType, role, round),
        });
      } else {
        // Node already exists (Retry/Loop) → set status to active, update profile
        const node = graphNodes.get(agentId);
        node.data = {
          ...node.data,
          status: 'active',
          isActive: true,
          round,
          ...(profile ? { profile } : {}),
          ...(model ? { model } : {}),
          ...(agentUrl ? { agentUrl } : {}),
        };
      }

      // Create edges: previous agent/input → this agent
      // Uses the shared PIPELINE_ROLES constant so all roles (including
      // fact-checker, analyst, creative) get correct predecessor edges.
      const currentIdx = PIPELINE_ROLES.indexOf(role);

      if (currentIdx > 0) {
        // Find the previous agent node in this round
        const prevRole = PIPELINE_ROLES[currentIdx - 1];
        const prevAgentId = `${prevRole}_r${round}`;
        if (graphNodes.has(prevAgentId)) {
          const edgeId = `${prevAgentId}->${agentId}`;
          graphEdges.set(edgeId, {
            id: edgeId,
            source: prevAgentId,
            target: agentId,
            type: 'flow',
            data: { type: 'flow', isActive: true },
          });
        }
      } else if (currentIdx === 0) {
        // First pipeline agent (strategist) — connect to decision node of previous round if it exists
        const prevDecisionId = `decision_r${round - 1}`;
        if (round > 1 && graphNodes.has(prevDecisionId)) {
          const edgeId = `${prevDecisionId}->${agentId}`;
          graphEdges.set(edgeId, {
            id: edgeId,
            source: prevDecisionId,
            target: agentId,
            type: 'flow',
            data: { type: 'flow', isActive: true },
          });
        } else {
          // Round 1 — connect to input node
          for (const [, node] of graphNodes) {
            if (node.type === 'input') {
              const edgeId = `${node.id}->${agentId}`;
              graphEdges.set(edgeId, {
                id: edgeId,
                source: node.id,
                target: agentId,
                type: 'flow',
                data: { type: 'flow', isActive: true },
              });
              break;
            }
          }
        }
      } else {
        // Unknown/A2A role — connect to the last known pipeline agent in this round.
        // Walk backwards through the pipeline to find the latest completed agent.
        let connected = false;
        for (let i = PIPELINE_ROLES.length - 1; i >= 0 && !connected; i--) {
          const candidateId = `${PIPELINE_ROLES[i]}_r${round}`;
          if (graphNodes.has(candidateId)) {
            const edgeId = `${candidateId}->${agentId}`;
            graphEdges.set(edgeId, {
              id: edgeId,
              source: candidateId,
              target: agentId,
              type: 'flow',
              data: { type: 'flow', isActive: true },
            });
            connected = true;
          }
        }
        // Fallback: connect to input if no pipeline agent found
        if (!connected) {
          for (const [, node] of graphNodes) {
            if (node.type === 'input') {
              const edgeId = `${node.id}->${agentId}`;
              graphEdges.set(edgeId, {
                id: edgeId,
                source: node.id,
                target: agentId,
                type: 'flow',
                data: { type: 'flow', isActive: true },
              });
              break;
            }
          }
        }
      }
      break;
    }

    // ═══════════════════════════════════════════
    // AGENT_COMPLETED
    // ═══════════════════════════════════════════
    case 'AGENT_COMPLETED': {
      const { agentId } = event.payload;

      const node = graphNodes.get(agentId);
      if (node) {
        node.data = { ...node.data, status: 'completed', isActive: false };
      }

      // Deactivate incoming edges
      for (const [id, edge] of graphEdges) {
        if (edge.target === agentId && edge.data?.isActive) {
          edge.data = { ...edge.data, isActive: false };
        }
      }
      break;
    }

    // ═══════════════════════════════════════════
    // ARTIFACT_PRODUCED
    // ═══════════════════════════════════════════
    case 'ARTIFACT_PRODUCED': {
      const { artifactId, type, producerAgentId, round, summary, tokenCount } = event.payload;

      graphNodes.set(artifactId, {
        id: artifactId,
        type: 'artifact',
        data: { artifactType: type, summary, tokenCount, status: 'draft', round },
        position: getInitialPosition('artifact', type, round),
      });

      const edgeId = `${producerAgentId}->${artifactId}`;
      graphEdges.set(edgeId, {
        id: edgeId,
        source: producerAgentId,
        target: artifactId,
        type: 'flow',
        data: { type: 'flow', isActive: false },
      });
      break;
    }

    // ═══════════════════════════════════════════
    // USER_CLARIFICATION_REQUESTED  ←── Non-linear!
    // ═══════════════════════════════════════════
    case 'USER_CLARIFICATION_REQUESTED': {
      const { requestId, requestingAgentId, requestingAgentRole, question } = event.payload;
      const userNodeId = `user_action_${requestId}`;

      graphNodes.set(userNodeId, {
        id: userNodeId,
        type: 'user_action',
        data: {
          actionType: 'clarify',
          label: question,
          status: 'waiting',
          requestedBy: requestingAgentRole,
          isBlocking: true,
        },
        position: getInitialPosition('user_action', requestingAgentRole, event.payload.round || 1),
      });

      // Edge: Agent → User (dashed, orange)
      const requestEdgeId = `${requestingAgentId}->${userNodeId}`;
      graphEdges.set(requestEdgeId, {
        id: requestEdgeId,
        source: requestingAgentId,
        target: userNodeId,
        type: 'user_request',
        data: { type: 'user_request', isActive: true, label: 'Query' },
      });

      // Edge: User → Agent (prepared, still inactive)
      const responseEdgeId = `${userNodeId}->${requestingAgentId}`;
      graphEdges.set(responseEdgeId, {
        id: responseEdgeId,
        source: userNodeId,
        target: requestingAgentId,
        type: 'user_response',
        data: { type: 'user_response', isActive: false, label: 'Response' },
      });
      break;
    }

    // ═══════════════════════════════════════════
    // USER_CLARIFICATION_RECEIVED
    // ═══════════════════════════════════════════
    case 'USER_CLARIFICATION_RECEIVED': {
      const { requestId, respondingToAgentId } = event.payload;
      const userNodeId = `user_action_${requestId}`;

      const userNode = graphNodes.get(userNodeId);
      if (userNode) {
        userNode.data = { ...userNode.data, status: 'resolved' };
      }

      // Deactivate request edge
      const requestEdgeId = `${respondingToAgentId}->${userNodeId}`;
      const requestEdge = graphEdges.get(requestEdgeId);
      if (requestEdge) {
        requestEdge.data = { ...requestEdge.data, isActive: false };
      }

      // Activate response edge (briefly, for animation)
      const responseEdgeId = `${userNodeId}->${respondingToAgentId}`;
      const responseEdge = graphEdges.get(responseEdgeId);
      if (responseEdge) {
        responseEdge.data = { ...responseEdge.data, isActive: true };
        setTimeout(() => {
          const re = graphEdges.get(responseEdgeId);
          if (re) re.data = { ...re.data, isActive: false };
        }, 2000);
      }
      break;
    }

    // ═══════════════════════════════════════════
    // FEEDBACK_LOOP_INITIATED  ←── Non-linear!
    // ═══════════════════════════════════════════
    case 'FEEDBACK_LOOP_INITIATED': {
      const { loopId, fromAgentId, toAgentId, reason, iteration } = event.payload;

      const edgeId = `feedback_${loopId}_${iteration}`;
      graphEdges.set(edgeId, {
        id: edgeId,
        source: fromAgentId,
        target: toAgentId,
        type: 'feedback',
        data: { type: 'feedback', isActive: true, label: `${reason} (Retry ${iteration})` },
      });

      const targetNode = graphEdges.get(toAgentId);
      if (targetNode && targetNode.type === 'agent') {
        targetNode.data = { ...targetNode.data, hasFeedbackLoop: true };
      }
      break;
    }

    // ═══════════════════════════════════════════
    // USER_OUT_OF_BAND_INPUT  ←── Non-linear!
    // ═══════════════════════════════════════════
    case 'USER_OUT_OF_BAND_INPUT': {
      const { inputId, targetAgentId, content } = event.payload;
      const sideNodeId = `side_input_${inputId}`;

      // Side-Input-Node (small, on the edge)
      const targetRole = targetAgentId.split('_')[0];
      const targetRound = parseInt(targetAgentId.split('_r')[1]) || 1;
      graphNodes.set(sideNodeId, {
        id: sideNodeId,
        type: 'user_action',
        data: {
          actionType: 'provide_context',
          label: content.length > 40 ? content.substring(0, 40) + '...' : content,
          fullContent: content,
          status: 'resolved',
          requestedBy: 'user',
          isBlocking: false,
          isOOB: true,
        },
        position: getInitialPosition('user_action', targetRole, targetRound),
      });

      // If target agent doesn't exist yet → placeholder
      if (!graphNodes.has(targetAgentId)) {
        graphNodes.set(`pending_target_${targetAgentId}`, {
          id: `pending_target_${targetAgentId}`,
          type: 'placeholder',
          data: { label: 'Waiting for agent...', role: targetAgentId.split('_')[0] },
        });
      }

      const actualTargetId = graphNodes.has(targetAgentId)
        ? targetAgentId
        : `pending_target_${targetAgentId}`;

      const edgeId = `${sideNodeId}->${actualTargetId}`;
      graphEdges.set(edgeId, {
        id: edgeId,
        source: sideNodeId,
        target: actualTargetId,
        type: 'user_response',
        data: { type: 'user_response', isActive: true, label: 'Extra info', isOOB: true },
      });
      break;
    }

    // ═══════════════════════════════════════════
    // OOB_CONSUMED
    // ═══════════════════════════════════════════
    case 'OOB_CONSUMED': {
      const { oobIds } = event.payload;

      for (const [id, edge] of graphEdges) {
        if (edge.data?.isOOB && oobIds.some(oid => edge.source.includes(oid))) {
          edge.data = { ...edge.data, isActive: false, isConsumed: true };
        }
      }
      break;
    }

    // ═══════════════════════════════════════════
    // ROUND_COMPLETED
    // ═══════════════════════════════════════════
    case 'ROUND_COMPLETED': {
      const { round } = event.payload;
      const decisionId = `decision_r${round}`;

      // Mark round artifacts as final
      for (const [id, node] of graphNodes) {
        if (node.data?.round === round && node.type === 'artifact') {
          node.data = { ...node.data, status: 'final' };
        }
      }

      // Create decision node for this round
      if (!graphNodes.has(decisionId)) {
        graphNodes.set(decisionId, {
          id: decisionId,
          type: 'decision',
          data: {
            round,
            consensus: event.payload.consensus ?? null,
            threshold: event.payload.threshold ?? 0.8,
            status: 'completed',
          },
          position: getInitialPosition('decision', 'moderator', round),
        });
      }

      // Create edge from moderator artifact to decision node
      const modArtifactId = `moderator_output_r${round}`;
      const edgeId = `${modArtifactId}->${decisionId}`;
      if (!graphEdges.has(edgeId)) {
        graphEdges.set(edgeId, {
          id: edgeId,
          source: modArtifactId,
          target: decisionId,
          type: 'flow',
          data: { type: 'flow', isActive: false },
        });
      }
      break;
    }

    // ═══════════════════════════════════════════
    // CONSENSUS_CHECK  ←── Intermediate evaluation
    // ═══════════════════════════════════════════
    case 'CONSENSUS_CHECK': {
      const { decisionId, round, consensus, threshold, passed } = event.payload;

      if (graphNodes.has(decisionId)) {
        const node = graphNodes.get(decisionId);
        node.data = { ...node.data, consensus, threshold, status: passed ? 'passed' : 'below' };
      } else {
        graphNodes.set(decisionId, {
          id: decisionId,
          type: 'decision',
          data: { round, consensus, threshold, status: passed ? 'passed' : 'below' },
          position: getInitialPosition('decision', 'moderator', round),
        });
      }
      break;
    }

    // ═══════════════════════════════════════════
    // AGENT_ACTIVITY  ←── Visual indicator
    // ═══════════════════════════════════════════
    case 'AGENT_ACTIVITY': {
      const { agentId, activity, detail } = event.payload;

      const node = graphNodes.get(agentId);
      if (node) {
        node.data = { ...node.data, activity, activityDetail: detail };
      }

      // Clear activity from all other agents to prevent stale "Thinking…" display
      for (const [id, n] of graphNodes) {
        if (id !== agentId && n.data?.activity) {
          n.data = { ...n.data, activity: null, activityDetail: null };
        }
      }
      break;
    }

    // ═══════════════════════════════════════════
    // WORKFLOW_COMPLETED
    // ═══════════════════════════════════════════
    case 'WORKFLOW_COMPLETED': {
      for (const [id, node] of graphNodes) {
        if (node.data?.status === 'active' || node.data?.status === 'running') {
          node.data = { ...node.data, status: 'completed', isActive: false, activity: null, activityDetail: null };
        }
      }

      for (const [id, edge] of graphEdges) {
        if (edge.data?.isActive || edge.type === 'flow') {
          edge.data = { ...edge.data, isActive: false, status: 'completed' };
        }
      }
      break;
    }

    default:
      break;
  }
}
