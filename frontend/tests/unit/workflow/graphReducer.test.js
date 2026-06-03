/**
 * Unit Tests — Graph Reducer (Event → Graph Mutation)
 *
 * Tests that each workflow event type correctly mutates the graph nodes/edges.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { workflowStore, resetWorkflow } from '../../../src/lib/workflow/store.svelte.js';
import { applyEventToGraph } from '../../../src/lib/workflow/graphReducer.js';

describe('graphReducer', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  // ─── AGENT_STARTED ───

  describe('AGENT_STARTED', () => {
    it('creates a new agent node when it does not exist', () => {
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: ['input'],
          timestamp: Date.now(),
        },
      });

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('strategist_r1')).toBe(true);

      const node = nodes.get('strategist_r1');
      expect(node.type).toBe('agent');
      expect(node.data.role).toBe('strategist');
      expect(node.data.status).toBe('active');
      expect(node.data.round).toBe(1);
      expect(node.data.isActive).toBe(true);
    });

    it('creates edges from previous pipeline agent to this agent', () => {
      // First, start the previous agent in the pipeline (strategist)
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      // Now start critic — pipeline logic creates edge strategist_r1 → critic_r1
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      const edges = workflowStore.graphEdges;
      expect(edges.has('strategist_r1->critic_r1')).toBe(true);

      const edge = edges.get('strategist_r1->critic_r1');
      expect(edge.source).toBe('strategist_r1');
      expect(edge.target).toBe('critic_r1');
      expect(edge.type).toBe('flow');
      expect(edge.data.isActive).toBe(true);
    });

    it('reactivates an existing agent node (retry/loop scenario)', () => {
      // First start
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      // Mark as completed
      applyEventToGraph(workflowStore, {
        type: 'AGENT_COMPLETED',
        payload: { agentId: 'critic_r1', role: 'critic', round: 1 },
      });

      // Restart (retry)
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      const node = workflowStore.graphNodes.get('critic_r1');
      expect(node.data.status).toBe('active');
      expect(node.data.isActive).toBe(true);
    });

    it('creates a single pipeline edge from previous agent', () => {
      // Pipeline logic creates exactly one edge per AGENT_STARTED, not per input artifact
      // Start strategist first to seed the pipeline
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      // Start critic with multiple inputArtifactIds — only one edge should be created
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          inputArtifactIds: ['strategist_output_r1', 'extra_input'],
          timestamp: Date.now(),
        },
      });

      const edges = workflowStore.graphEdges;
      expect(edges.size).toBe(1);
      expect(edges.has('strategist_r1->critic_r1')).toBe(true);
    });
  });

  // ─── AGENT_COMPLETED ───

  describe('AGENT_COMPLETED', () => {
    it('sets agent node status to completed and inactive', () => {
      // First create the node
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'AGENT_COMPLETED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          outputArtifactId: 'strategy_r1',
          durationMs: 5000,
        },
      });

      const node = workflowStore.graphNodes.get('strategist_r1');
      expect(node.data.status).toBe('completed');
      expect(node.data.isActive).toBe(false);
    });

    it('deactivates incoming edges', () => {
      // Set up a pipeline: strategist → critic
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'AGENT_COMPLETED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          outputArtifactId: 'critique_r1',
          durationMs: 5000,
        },
      });

      const edge = workflowStore.graphEdges.get('strategist_r1->critic_r1');
      expect(edge.data.isActive).toBe(false);
    });

    it('does not throw if agent node does not exist', () => {
      expect(() => {
        applyEventToGraph(workflowStore, {
          type: 'AGENT_COMPLETED',
          payload: {
            agentId: 'nonexistent',
            role: 'strategist',
            round: 1,
            outputArtifactId: 'x',
            durationMs: 0,
          },
        });
      }).not.toThrow();
    });
  });

  // ─── ARTIFACT_PRODUCED ───

  describe('ARTIFACT_PRODUCED', () => {
    it('creates an artifact node', () => {
      applyEventToGraph(workflowStore, {
        type: 'ARTIFACT_PRODUCED',
        payload: {
          artifactId: 'strategy_r1',
          type: 'strategy',
          producerAgentId: 'strategist_r1',
          round: 1,
          summary: 'Initial strategy for the case',
          tokenCount: 150,
        },
      });

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('strategy_r1')).toBe(true);

      const node = nodes.get('strategy_r1');
      expect(node.type).toBe('artifact');
      expect(node.data.artifactType).toBe('strategy');
      expect(node.data.summary).toBe('Initial strategy for the case');
      expect(node.data.tokenCount).toBe(150);
      expect(node.data.status).toBe('draft');
    });

    it('creates an edge from producer agent to artifact', () => {
      applyEventToGraph(workflowStore, {
        type: 'ARTIFACT_PRODUCED',
        payload: {
          artifactId: 'strategy_r1',
          type: 'strategy',
          producerAgentId: 'strategist_r1',
          round: 1,
          summary: 'test',
          tokenCount: 100,
        },
      });

      const edges = workflowStore.graphEdges;
      expect(edges.has('strategist_r1->strategy_r1')).toBe(true);

      const edge = edges.get('strategist_r1->strategy_r1');
      expect(edge.source).toBe('strategist_r1');
      expect(edge.target).toBe('strategy_r1');
      expect(edge.type).toBe('flow');
    });
  });

  // ─── USER_CLARIFICATION_REQUESTED ───

  describe('USER_CLARIFICATION_REQUESTED', () => {
    it('creates a user_action node with blocking status', () => {
      applyEventToGraph(workflowStore, {
        type: 'USER_CLARIFICATION_REQUESTED',
        payload: {
          requestId: 'req_001',
          requestingAgentId: 'critic_r1',
          requestingAgentRole: 'critic',
          question: 'What is the jurisdiction?',
          blocking: true,
          round: 1,
        },
      });

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('user_action_req_001')).toBe(true);

      const node = nodes.get('user_action_req_001');
      expect(node.type).toBe('user_action');
      expect(node.data.status).toBe('waiting');
      expect(node.data.isBlocking).toBe(true);
      expect(node.data.requestedBy).toBe('critic');
    });

    it('creates request and response edges', () => {
      applyEventToGraph(workflowStore, {
        type: 'USER_CLARIFICATION_REQUESTED',
        payload: {
          requestId: 'req_001',
          requestingAgentId: 'critic_r1',
          requestingAgentRole: 'critic',
          question: 'What is the jurisdiction?',
          blocking: true,
          round: 1,
        },
      });

      const edges = workflowStore.graphEdges;
      // Request edge: Agent → User
      expect(edges.has('critic_r1->user_action_req_001')).toBe(true);
      const reqEdge = edges.get('critic_r1->user_action_req_001');
      expect(reqEdge.type).toBe('user_request');
      expect(reqEdge.data.isActive).toBe(true);

      // Response edge: User → Agent (prepared, inactive)
      expect(edges.has('user_action_req_001->critic_r1')).toBe(true);
      const respEdge = edges.get('user_action_req_001->critic_r1');
      expect(respEdge.type).toBe('user_response');
      expect(respEdge.data.isActive).toBe(false);
    });
  });

  // ─── USER_CLARIFICATION_RECEIVED ───

  describe('USER_CLARIFICATION_RECEIVED', () => {
    it('sets user node status to resolved', () => {
      // First create the request
      applyEventToGraph(workflowStore, {
        type: 'USER_CLARIFICATION_REQUESTED',
        payload: {
          requestId: 'req_001',
          requestingAgentId: 'critic_r1',
          requestingAgentRole: 'critic',
          question: 'What is the jurisdiction?',
          blocking: true,
          round: 1,
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'USER_CLARIFICATION_RECEIVED',
        payload: {
          requestId: 'req_001',
          response: 'German law applies',
          respondingToAgentId: 'critic_r1',
          round: 1,
        },
      });

      const node = workflowStore.graphNodes.get('user_action_req_001');
      expect(node.data.status).toBe('resolved');
    });

    it('deactivates request edge and activates response edge', () => {
      applyEventToGraph(workflowStore, {
        type: 'USER_CLARIFICATION_REQUESTED',
        payload: {
          requestId: 'req_001',
          requestingAgentId: 'critic_r1',
          requestingAgentRole: 'critic',
          question: 'test',
          blocking: true,
          round: 1,
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'USER_CLARIFICATION_RECEIVED',
        payload: {
          requestId: 'req_001',
          response: 'answer',
          respondingToAgentId: 'critic_r1',
          round: 1,
        },
      });

      const edges = workflowStore.graphEdges;
      const reqEdge = edges.get('critic_r1->user_action_req_001');
      expect(reqEdge.data.isActive).toBe(false);

      const respEdge = edges.get('user_action_req_001->critic_r1');
      expect(respEdge.data.isActive).toBe(true);
    });
  });

  // ─── FEEDBACK_LOOP_INITIATED ───

  describe('FEEDBACK_LOOP_INITIATED', () => {
    it('creates a feedback edge between agents', () => {
      applyEventToGraph(workflowStore, {
        type: 'FEEDBACK_LOOP_INITIATED',
        payload: {
          loopId: 'loop_001',
          fromAgentId: 'critic_r1',
          toAgentId: 'strategist_r1',
          reason: 'Needs more detail',
          round: 1,
          iteration: 1,
        },
      });

      const edges = workflowStore.graphEdges;
      expect(edges.has('feedback_loop_001_1')).toBe(true);

      const edge = edges.get('feedback_loop_001_1');
      expect(edge.source).toBe('critic_r1');
      expect(edge.target).toBe('strategist_r1');
      expect(edge.type).toBe('feedback');
      expect(edge.data.isActive).toBe(true);
      expect(edge.data.label).toContain('Needs more detail');
    });

    it('marks target agent node with hasFeedbackLoop', () => {
      // Create the target agent first
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'FEEDBACK_LOOP_INITIATED',
        payload: {
          loopId: 'loop_001',
          fromAgentId: 'critic_r1',
          toAgentId: 'strategist_r1',
          reason: 'Needs more detail',
          round: 1,
          iteration: 1,
        },
      });

      const node = workflowStore.graphNodes.get('strategist_r1');
      expect(node.data.hasFeedbackLoop).toBe(true);
    });
  });

  // ─── USER_OUT_OF_BAND_INPUT ───

  describe('USER_OUT_OF_BAND_INPUT', () => {
    it('creates a side-input user_action node', () => {
      applyEventToGraph(workflowStore, {
        type: 'USER_OUT_OF_BAND_INPUT',
        payload: {
          inputId: 'oob_001',
          targetAgentId: 'strategist_r1',
          content: 'Additional context from user',
          round: 1,
        },
      });

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('side_input_oob_001')).toBe(true);

      const node = nodes.get('side_input_oob_001');
      expect(node.type).toBe('user_action');
      expect(node.data.isOOB).toBe(true);
      expect(node.data.isBlocking).toBe(false);
      expect(node.data.fullContent).toBe('Additional context from user');
    });

    it('truncates long content in label', () => {
      const longContent = 'A'.repeat(100);
      applyEventToGraph(workflowStore, {
        type: 'USER_OUT_OF_BAND_INPUT',
        payload: {
          inputId: 'oob_002',
          targetAgentId: 'strategist_r1',
          content: longContent,
          round: 1,
        },
      });

      const node = workflowStore.graphNodes.get('side_input_oob_002');
      expect(node.data.label.length).toBeLessThanOrEqual(43); // 40 + '...'
      expect(node.data.label).toContain('...');
    });

    it('creates placeholder when target agent does not exist', () => {
      applyEventToGraph(workflowStore, {
        type: 'USER_OUT_OF_BAND_INPUT',
        payload: {
          inputId: 'oob_003',
          targetAgentId: 'future_agent',
          content: 'test',
          round: 1,
        },
      });

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('pending_target_future_agent')).toBe(true);
      expect(nodes.get('pending_target_future_agent').type).toBe('placeholder');
    });

    it('creates OOB edge to existing target agent', () => {
      // Create target agent first
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'USER_OUT_OF_BAND_INPUT',
        payload: {
          inputId: 'oob_004',
          targetAgentId: 'strategist_r1',
          content: 'test context',
          round: 1,
        },
      });

      const edges = workflowStore.graphEdges;
      const edgeId = 'side_input_oob_004->strategist_r1';
      expect(edges.has(edgeId)).toBe(true);

      const edge = edges.get(edgeId);
      expect(edge.data.isOOB).toBe(true);
      expect(edge.data.isActive).toBe(true);
    });
  });

  // ─── OOB_CONSUMED ───

  describe('OOB_CONSUMED', () => {
    it('deactivates and marks OOB edges as consumed', () => {
      // Create agent and OOB
      applyEventToGraph(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'USER_OUT_OF_BAND_INPUT',
        payload: {
          inputId: 'oob_001',
          targetAgentId: 'strategist_r1',
          content: 'test',
          round: 1,
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'OOB_CONSUMED',
        payload: {
          oobIds: ['oob_001'],
          byAgentId: 'strategist_r1',
        },
      });

      const edges = workflowStore.graphEdges;
      const edge = edges.get('side_input_oob_001->strategist_r1');
      expect(edge.data.isActive).toBe(false);
      expect(edge.data.isConsumed).toBe(true);
    });
  });

  // ─── ROUND_COMPLETED ───

  describe('ROUND_COMPLETED', () => {
    it('marks artifacts from the round as final', () => {
      applyEventToGraph(workflowStore, {
        type: 'ARTIFACT_PRODUCED',
        payload: {
          artifactId: 'strategy_r1',
          type: 'strategy',
          producerAgentId: 'strategist_r1',
          round: 1,
          summary: 'test',
          tokenCount: 100,
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'ROUND_COMPLETED',
        payload: {
          round: 1,
          finalArtifactId: 'consensus_r1',
          pathTaken: [],
        },
      });

      const node = workflowStore.graphNodes.get('strategy_r1');
      expect(node.data.status).toBe('final');
    });

    it('does not affect artifacts from other rounds', () => {
      applyEventToGraph(workflowStore, {
        type: 'ARTIFACT_PRODUCED',
        payload: {
          artifactId: 'strategy_r2',
          type: 'strategy',
          producerAgentId: 'strategist_r2',
          round: 2,
          summary: 'test',
          tokenCount: 100,
        },
      });

      applyEventToGraph(workflowStore, {
        type: 'ROUND_COMPLETED',
        payload: {
          round: 1,
          finalArtifactId: 'consensus_r1',
          pathTaken: [],
        },
      });

      const node = workflowStore.graphNodes.get('strategy_r2');
      expect(node.data.status).toBe('draft');
    });
  });

  // ─── Unknown event type ───

  describe('unknown event type', () => {
    it('does not throw for unknown event types', () => {
      expect(() => {
        applyEventToGraph(workflowStore, {
          type: 'UNKNOWN_EVENT',
          payload: {},
        });
      }).not.toThrow();
    });
  });
});
