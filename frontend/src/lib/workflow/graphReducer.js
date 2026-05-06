/**
 * Graph Reducer — Event → Graph Mutation
 *
 * The heart of the workflow visualization. Each event type knows exactly
 * how it changes the graph (nodes and edges).
 */

import { get } from 'svelte/store';
import { graphNodes, graphEdges } from './store.js';

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
      const { agentId, role, round, inputArtifactIds } = event.payload;

      graphNodes.update(nodes => {
        if (!nodes.has(agentId)) {
          nodes.set(agentId, {
            id: agentId,
            type: 'agent',
            data: {
              role,
              label: `${role} (Round ${round})`,
              status: 'active',
              round,
              isActive: true,
              hasFeedbackLoop: false,
            },
          });
        } else {
          // Node already exists (Retry/Loop) → set status to active
          const node = nodes.get(agentId);
          node.data.status = 'active';
          node.data.isActive = true;
          node.data.round = round;
        }
        return nodes;
      });

      // Create edges from input artifacts to this agent
      graphEdges.update(edges => {
        inputArtifactIds.forEach((artifactId, idx) => {
          const edgeId = `${artifactId}->${agentId}_${idx}`;
          edges.set(edgeId, {
            id: edgeId,
            source: artifactId,
            target: agentId,
            type: 'flow',
            data: { type: 'flow', isActive: true },
          });
        });
        return edges;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // AGENT_COMPLETED
    // ═══════════════════════════════════════════
    case 'AGENT_COMPLETED': {
      const { agentId } = event.payload;

      graphNodes.update(nodes => {
        const node = nodes.get(agentId);
        if (node) {
          node.data.status = 'completed';
          node.data.isActive = false;
        }
        return nodes;
      });

      // Deactivate incoming edges
      graphEdges.update(edges => {
        edges.forEach((edge) => {
          if (edge.target === agentId && edge.data?.isActive) {
            edge.data.isActive = false;
          }
        });
        return edges;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // ARTIFACT_PRODUCED
    // ═══════════════════════════════════════════
    case 'ARTIFACT_PRODUCED': {
      const { artifactId, type, producerAgentId, round, summary, tokenCount } = event.payload;

      graphNodes.update(nodes => {
        nodes.set(artifactId, {
          id: artifactId,
          type: 'artifact',
          data: { artifactType: type, summary, tokenCount, status: 'draft', round },
        });
        return nodes;
      });

      graphEdges.update(edges => {
        const edgeId = `${producerAgentId}->${artifactId}`;
        edges.set(edgeId, {
          id: edgeId,
          source: producerAgentId,
          target: artifactId,
          type: 'flow',
          data: { type: 'flow', isActive: false },
        });
        return edges;
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
        nodes.set(userNodeId, {
          id: userNodeId,
          type: 'user_action',
          data: {
            actionType: 'clarify',
            label: question,
            status: 'waiting',
            requestedBy: requestingAgentRole,
            isBlocking: true,
          },
        });
        return nodes;
      });

      graphEdges.update(edges => {
        // Edge: Agent → User (dashed, orange)
        const requestEdgeId = `${requestingAgentId}->${userNodeId}`;
        edges.set(requestEdgeId, {
          id: requestEdgeId,
          source: requestingAgentId,
          target: userNodeId,
          type: 'user_request',
          data: { type: 'user_request', isActive: true, label: 'Query' },
        });

        // Edge: User → Agent (prepared, still inactive)
        const responseEdgeId = `${userNodeId}->${requestingAgentId}`;
        edges.set(responseEdgeId, {
          id: responseEdgeId,
          source: userNodeId,
          target: requestingAgentId,
          type: 'user_response',
          data: { type: 'user_response', isActive: false, label: 'Response' },
        });
        return edges;
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
        const userNode = nodes.get(userNodeId);
        if (userNode) userNode.data.status = 'resolved';
        return nodes;
      });

      graphEdges.update(edges => {
        // Deactivate request edge
        const requestEdgeId = `${respondingToAgentId}->${userNodeId}`;
        const requestEdge = edges.get(requestEdgeId);
        if (requestEdge) requestEdge.data.isActive = false;

        // Activate response edge (briefly, for animation)
        const responseEdgeId = `${userNodeId}->${respondingToAgentId}`;
        const responseEdge = edges.get(responseEdgeId);
        if (responseEdge) {
          responseEdge.data.isActive = true;
          setTimeout(() => { responseEdge.data.isActive = false; }, 2000);
        }
        return edges;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // FEEDBACK_LOOP_INITIATED  ←── Non-linear!
    // ═══════════════════════════════════════════
    case 'FEEDBACK_LOOP_INITIATED': {
      const { loopId, fromAgentId, toAgentId, reason, iteration } = event.payload;

      graphEdges.update(edges => {
        const edgeId = `feedback_${loopId}_${iteration}`;
        edges.set(edgeId, {
          id: edgeId,
          source: fromAgentId,
          target: toAgentId,
          type: 'feedback',
          data: { type: 'feedback', isActive: true, label: `${reason} (Retry ${iteration})` },
        });
        return edges;
      });

      graphNodes.update(nodes => {
        const targetNode = nodes.get(toAgentId);
        if (targetNode && targetNode.type === 'agent') {
          targetNode.data.hasFeedbackLoop = true;
        }
        return nodes;
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
        // Side-Input-Node (small, on the edge)
        nodes.set(sideNodeId, {
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
        });

        // If target agent doesn't exist yet → placeholder
        if (!nodes.has(targetAgentId)) {
          nodes.set(`pending_target_${targetAgentId}`, {
            id: `pending_target_${targetAgentId}`,
            type: 'placeholder',
            data: { label: 'Waiting for agent...', role: targetAgentId.split('_')[0] },
          });
        }
        return nodes;
      });

      graphEdges.update(edges => {
        const nodes = get(graphNodes);
        const actualTargetId = nodes.has(targetAgentId)
          ? targetAgentId
          : `pending_target_${targetAgentId}`;

        const edgeId = `${sideNodeId}->${actualTargetId}`;
        edges.set(edgeId, {
          id: edgeId,
          source: sideNodeId,
          target: actualTargetId,
          type: 'user_response',
          data: { type: 'user_response', isActive: true, label: 'Extra info', isOOB: true },
        });
        return edges;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // OOB_CONSUMED
    // ═══════════════════════════════════════════
    case 'OOB_CONSUMED': {
      const { oobIds } = event.payload;

      graphEdges.update(edges => {
        edges.forEach((edge) => {
          if (edge.data?.isOOB && oobIds.some(id => edge.source.includes(id))) {
            edge.data.isActive = false;
            edge.data.isConsumed = true;
          }
        });
        return edges;
      });
      break;
    }

    // ═══════════════════════════════════════════
    // ROUND_COMPLETED
    // ═══════════════════════════════════════════
    case 'ROUND_COMPLETED': {
      const { round } = event.payload;

      graphNodes.update(nodes => {
        nodes.forEach((node) => {
          if (node.data?.round === round && node.type === 'artifact') {
            node.data.status = 'final';
          }
        });
        return nodes;
      });
      break;
    }

    default:
      break;
  }
}
