/**
 * Graph Reducer — Event → Graph Mutation
 *
 * The heart of the workflow visualization. Each event type knows exactly
 * how it changes the graph (nodes and edges).
 *
 * IMPORTANT: Svelte writable stores only notify subscribers when the value
 * reference changes. We MUST create new Map copies in every update callback
 * (same pattern as $state(new Set()) reactivity in Svelte 5).
 */

import { get } from 'svelte/store';
import { graphNodes, graphEdges } from './store.js';

// ── Initial position calculation ──────────────────────────────────
// Gives each node a reasonable starting position so the graph is
// readable even before ELK layout runs. ELK will refine these.
const ROLE_ORDER = ['strategist', 'critic', 'optimizer', 'moderator'];
const NODE_SPACING_X = 220;
const ROUND_SPACING_Y = 200;
const ARTIFACT_ROLE_MAP = {
  strategy: 'strategist',
  critique: 'critic',
  synthesis: 'optimizer',
  consensus: 'moderator',
};

function getInitialPosition(nodeType, role, round) {
  if (role === 'input') return { x: -200, y: 0 };
  const r = role in ARTIFACT_ROLE_MAP ? ARTIFACT_ROLE_MAP[role] : role;
  const col = ROLE_ORDER.indexOf(r);
  const c = col >= 0 ? col : 0;
  const baseX = c * 2 * NODE_SPACING_X;
  const baseY = ((round || 1) - 1) * ROUND_SPACING_Y;
  if (nodeType === 'artifact') return { x: baseX + NODE_SPACING_X, y: baseY + 30 };
  if (nodeType === 'decision') return { x: ROLE_ORDER.length * 2 * NODE_SPACING_X + 80, y: baseY };
  if (nodeType === 'user_action') return { x: baseX + NODE_SPACING_X / 2, y: baseY - 90 };
  // A2A agents are positioned after the moderator column
  if (nodeType === 'a2a_agent') return { x: (ROLE_ORDER.length) * 2 * NODE_SPACING_X, y: baseY };
  return { x: baseX, y: baseY };
}

/**
 * Apply a workflow event to the graph state.
 * @param {import('./events.js').WorkflowEvent} event
 */
export function applyEventToGraph(event) {
  switch (event.type) {

    // ═══════════════════════════════════════════
    // AGENT_STARTED
    // ═══════════════════════════════════════════
    case 'AGENT_STARTED': {
      const { agentId, role, round, inputArtifactIds, profile, model, isA2A, agentUrl } = event.payload;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        if (!copy.has(agentId)) {
          const nodeType = role === 'input' ? 'input' : isA2A ? 'a2a_agent' : 'agent';
          copy.set(agentId, {
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
          const node = { ...copy.get(agentId) };
          node.data = {
            ...node.data,
            status: 'active',
            isActive: true,
            round,
            ...(profile ? { profile } : {}),
            ...(model ? { model } : {}),
            ...(agentUrl ? { agentUrl } : {}),
          };
          copy.set(agentId, node);
        }
        return copy;
      });

      // Create edges: previous agent/input → this agent
      // We connect agent-to-agent immediately because artifact nodes may not
      // exist yet (they're created by ARTIFACT_PRODUCED which fires later).
      graphEdges.update(edges => {
        const copy = new Map(edges);
        const nodes = get(graphNodes);
        const pipelineOrder = ['strategist', 'critic', 'optimizer', 'moderator'];
        const currentIdx = pipelineOrder.indexOf(role);

        if (currentIdx > 0) {
          // Find the previous agent node in this round
          const prevRole = pipelineOrder[currentIdx - 1];
          const prevAgentId = `${prevRole}_r${round}`;
          if (nodes.has(prevAgentId)) {
            const edgeId = `${prevAgentId}->${agentId}`;
            copy.set(edgeId, {
              id: edgeId,
              source: prevAgentId,
              target: agentId,
              type: 'flow',
              data: { type: 'flow', isActive: true },
            });
          }
        } else if (currentIdx === 0) {
          // First agent (strategist) — connect to decision node of previous round if it exists
          const prevDecisionId = `decision_r${round - 1}`;
          if (round > 1 && nodes.has(prevDecisionId)) {
            const edgeId = `${prevDecisionId}->${agentId}`;
            copy.set(edgeId, {
              id: edgeId,
              source: prevDecisionId,
              target: agentId,
              type: 'flow',
              data: { type: 'flow', isActive: true },
            });
          } else {
            // Round 1 — connect to input node
            for (const [, node] of nodes) {
              if (node.type === 'input') {
                const edgeId = `${node.id}->${agentId}`;
                copy.set(edgeId, {
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
        } else if (!pipelineOrder.includes(role)) {
          // A2A or custom agent → connect to moderator of this round
          const modAgentId = `moderator_r${round}`;
          if (nodes.has(modAgentId)) {
            const edgeId = `${modAgentId}->${agentId}`;
            copy.set(edgeId, {
              id: edgeId,
              source: modAgentId,
              target: agentId,
              type: 'flow',
              data: { type: 'flow', isActive: true },
            });
          }
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // AGENT_COMPLETED
    // ═══════════════════════════════════════════
    case 'AGENT_COMPLETED': {
      const { agentId } = event.payload;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        const node = copy.get(agentId);
        if (node) {
          copy.set(agentId, {
            ...node,
            data: { ...node.data, status: 'completed', isActive: false },
          });
        }
        return copy;
      });

      // Deactivate incoming edges
      graphEdges.update(edges => {
        const copy = new Map(edges);
        for (const [id, edge] of copy) {
          if (edge.target === agentId && edge.data?.isActive) {
            copy.set(id, { ...edge, data: { ...edge.data, isActive: false } });
          }
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // ARTIFACT_PRODUCED
    // ═══════════════════════════════════════════
    case 'ARTIFACT_PRODUCED': {
      const { artifactId, type, producerAgentId, round, summary, tokenCount } = event.payload;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        copy.set(artifactId, {
          id: artifactId,
          type: 'artifact',
          data: { artifactType: type, summary, tokenCount, status: 'draft', round },
          position: getInitialPosition('artifact', type, round),
        });
        return copy;
      });

      graphEdges.update(edges => {
        const copy = new Map(edges);
        const edgeId = `${producerAgentId}->${artifactId}`;
        copy.set(edgeId, {
          id: edgeId,
          source: producerAgentId,
          target: artifactId,
          type: 'flow',
          data: { type: 'flow', isActive: false },
        });
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // USER_CLARIFICATION_REQUESTED  ←── Non-linear!
    // ═══════════════════════════════════════════
    case 'USER_CLARIFICATION_REQUESTED': {
      const { requestId, requestingAgentId, requestingAgentRole, question } = event.payload;
      const userNodeId = `user_action_${requestId}`;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        copy.set(userNodeId, {
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
        return copy;
      });

      graphEdges.update(edges => {
        const copy = new Map(edges);
        // Edge: Agent → User (dashed, orange)
        const requestEdgeId = `${requestingAgentId}->${userNodeId}`;
        copy.set(requestEdgeId, {
          id: requestEdgeId,
          source: requestingAgentId,
          target: userNodeId,
          type: 'user_request',
          data: { type: 'user_request', isActive: true, label: 'Query' },
        });

        // Edge: User → Agent (prepared, still inactive)
        const responseEdgeId = `${userNodeId}->${requestingAgentId}`;
        copy.set(responseEdgeId, {
          id: responseEdgeId,
          source: userNodeId,
          target: requestingAgentId,
          type: 'user_response',
          data: { type: 'user_response', isActive: false, label: 'Response' },
        });
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // USER_CLARIFICATION_RECEIVED
    // ═══════════════════════════════════════════
    case 'USER_CLARIFICATION_RECEIVED': {
      const { requestId, respondingToAgentId } = event.payload;
      const userNodeId = `user_action_${requestId}`;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        const userNode = copy.get(userNodeId);
        if (userNode) {
          copy.set(userNodeId, { ...userNode, data: { ...userNode.data, status: 'resolved' } });
        }
        return copy;
      });

      graphEdges.update(edges => {
        const copy = new Map(edges);
        // Deactivate request edge
        const requestEdgeId = `${respondingToAgentId}->${userNodeId}`;
        const requestEdge = copy.get(requestEdgeId);
        if (requestEdge) {
          copy.set(requestEdgeId, { ...requestEdge, data: { ...requestEdge.data, isActive: false } });
        }

        // Activate response edge (briefly, for animation)
        const responseEdgeId = `${userNodeId}->${respondingToAgentId}`;
        const responseEdge = copy.get(responseEdgeId);
        if (responseEdge) {
          copy.set(responseEdgeId, { ...responseEdge, data: { ...responseEdge.data, isActive: true } });
          setTimeout(() => {
            graphEdges.update(e => {
              const c = new Map(e);
              const re = c.get(responseEdgeId);
              if (re) c.set(responseEdgeId, { ...re, data: { ...re.data, isActive: false } });
              return c;
            });
          }, 2000);
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // FEEDBACK_LOOP_INITIATED  ←── Non-linear!
    // ═══════════════════════════════════════════
    case 'FEEDBACK_LOOP_INITIATED': {
      const { loopId, fromAgentId, toAgentId, reason, iteration } = event.payload;

      graphEdges.update(edges => {
        const copy = new Map(edges);
        const edgeId = `feedback_${loopId}_${iteration}`;
        copy.set(edgeId, {
          id: edgeId,
          source: fromAgentId,
          target: toAgentId,
          type: 'feedback',
          data: { type: 'feedback', isActive: true, label: `${reason} (Retry ${iteration})` },
        });
        return copy;
      });

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        const targetNode = copy.get(toAgentId);
        if (targetNode && targetNode.type === 'agent') {
          copy.set(toAgentId, { ...targetNode, data: { ...targetNode.data, hasFeedbackLoop: true } });
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // USER_OUT_OF_BAND_INPUT  ←── Non-linear!
    // ═══════════════════════════════════════════
    case 'USER_OUT_OF_BAND_INPUT': {
      const { inputId, targetAgentId, content } = event.payload;
      const sideNodeId = `side_input_${inputId}`;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        // Side-Input-Node (small, on the edge)
        const targetRole = targetAgentId.split('_')[0];
        const targetRound = parseInt(targetAgentId.split('_r')[1]) || 1;
        copy.set(sideNodeId, {
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
        if (!copy.has(targetAgentId)) {
          copy.set(`pending_target_${targetAgentId}`, {
            id: `pending_target_${targetAgentId}`,
            type: 'placeholder',
            data: { label: 'Waiting for agent...', role: targetAgentId.split('_')[0] },
          });
        }
        return copy;
      });

      graphEdges.update(edges => {
        const copy = new Map(edges);
        const nodes = get(graphNodes);
        const actualTargetId = nodes.has(targetAgentId)
          ? targetAgentId
          : `pending_target_${targetAgentId}`;

        const edgeId = `${sideNodeId}->${actualTargetId}`;
        copy.set(edgeId, {
          id: edgeId,
          source: sideNodeId,
          target: actualTargetId,
          type: 'user_response',
          data: { type: 'user_response', isActive: true, label: 'Extra info', isOOB: true },
        });
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // OOB_CONSUMED
    // ═══════════════════════════════════════════
    case 'OOB_CONSUMED': {
      const { oobIds } = event.payload;

      graphEdges.update(edges => {
        const copy = new Map(edges);
        for (const [id, edge] of copy) {
          if (edge.data?.isOOB && oobIds.some(oid => edge.source.includes(oid))) {
            copy.set(id, { ...edge, data: { ...edge.data, isActive: false, isConsumed: true } });
          }
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // ROUND_COMPLETED
    // ═══════════════════════════════════════════
    case 'ROUND_COMPLETED': {
      const { round } = event.payload;
      const decisionId = `decision_r${round}`;

      // Mark round artifacts as final
      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        for (const [id, node] of copy) {
          if (node.data?.round === round && node.type === 'artifact') {
            copy.set(id, { ...node, data: { ...node.data, status: 'final' } });
          }
        }
        // Create decision node for this round
        if (!copy.has(decisionId)) {
          copy.set(decisionId, {
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
        return copy;
      });

      // Create edge from moderator artifact to decision node
      graphEdges.update(edges => {
        const copy = new Map(edges);
        const modArtifactId = `moderator_output_r${round}`;
        const edgeId = `${modArtifactId}->${decisionId}`;
        if (!copy.has(edgeId)) {
          copy.set(edgeId, {
            id: edgeId,
            source: modArtifactId,
            target: decisionId,
            type: 'flow',
            data: { type: 'flow', isActive: false },
          });
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // CONSENSUS_CHECK  ←── Intermediate evaluation
    // ═══════════════════════════════════════════
    case 'CONSENSUS_CHECK': {
      const { decisionId, round, consensus, threshold, passed } = event.payload;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        if (copy.has(decisionId)) {
          const node = copy.get(decisionId);
          copy.set(decisionId, {
            ...node,
            data: { ...node.data, consensus, threshold, status: passed ? 'passed' : 'below' },
          });
        } else {
          copy.set(decisionId, {
            id: decisionId,
            type: 'decision',
            data: { round, consensus, threshold, status: passed ? 'passed' : 'below' },
            position: getInitialPosition('decision', 'moderator', round),
          });
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // AGENT_ACTIVITY  ←── Visual indicator
    // ═══════════════════════════════════════════
    case 'AGENT_ACTIVITY': {
      const { agentId, activity, detail } = event.payload;

      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        const node = copy.get(agentId);
        if (node) {
          copy.set(agentId, {
            ...node,
            data: { ...node.data, activity, activityDetail: detail },
          });
        }
        return copy;
      });

      // Clear activity from all other agents to prevent stale "Thinking…" display
      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        for (const [id, node] of copy) {
          if (id !== agentId && node.data?.activity) {
            copy.set(id, {
              ...node,
              data: { ...node.data, activity: null, activityDetail: null },
            });
          }
        }
        return copy;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // WORKFLOW_COMPLETED
    // ═══════════════════════════════════════════
    case 'WORKFLOW_COMPLETED': {
      graphNodes.update(nodes => {
        const copy = new Map(nodes);
        for (const [id, node] of copy) {
          if (node.data?.status === 'active' || node.data?.status === 'running') {
            copy.set(id, {
              ...node,
              data: { ...node.data, status: 'completed', isActive: false, activity: null, activityDetail: null },
            });
          }
        }
        return copy;
      });

      graphEdges.update(edges => {
        const copy = new Map(edges);
        for (const [id, edge] of copy) {
          if (edge.data?.isActive || edge.type === 'flow') {
            copy.set(id, {
              ...edge,
              data: { ...edge.data, isActive: false, status: 'completed' },
            });
          }
        }
        return copy;
      });
      break;
    }

    default:
      break;
  }
}
