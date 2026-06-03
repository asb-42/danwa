/**
 * Unit Tests — Runtime Reducer (Event → Runtime Status Update)
 *
 * Tests that each workflow event correctly updates the runtime state.
 * Migrated to Svelte 5 runes (workflowStore.X) from Svelte 4 stores.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { workflowStore, resetWorkflow, dispatchEvent } from '../../../src/lib/workflow/store.svelte.js';
import { applyEventToRuntime } from '../../../src/lib/workflow/runtimeReducer.js';

describe('runtimeReducer', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('AGENT_STARTED', () => {
    it('sets status to running and activeNodeId to agent', () => {
      applyEventToRuntime(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      expect(workflowStore.runtimeStatus).toBe('running');
      expect(workflowStore.runtimeActiveNodeId).toBe('strategist_r1');
      expect(workflowStore.runtimeActiveEdgeId).toBeNull();
    });

    it('appends agent to executionPath', () => {
      applyEventToRuntime(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToRuntime(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      expect(workflowStore.runtimeExecutionPath).toEqual(['strategist_r1', 'critic_r1']);
    });
  });

  describe('AGENT_COMPLETED', () => {
    it('clears activeNodeId', () => {
      applyEventToRuntime(workflowStore, {
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToRuntime(workflowStore, {
        type: 'AGENT_COMPLETED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          outputArtifactId: 'strategy_r1',
          durationMs: 5000,
        },
      });

      expect(workflowStore.runtimeActiveNodeId).toBeNull();
    });
  });

  describe('USER_CLARIFICATION_REQUESTED', () => {
    it('sets status to waiting_for_user and blocking request id', () => {
      applyEventToRuntime(workflowStore, {
        type: 'USER_CLARIFICATION_REQUESTED',
        payload: {
          requestId: 'req_001',
          requestingAgentId: 'critic_r1',
          requestingAgentRole: 'critic',
          question: 'What jurisdiction?',
          blocking: true,
          round: 1,
        },
      });

      expect(workflowStore.runtimeStatus).toBe('waiting_for_user');
      expect(workflowStore.runtimeBlockingUserRequestId).toBe('req_001');
      expect(workflowStore.runtimeActiveNodeId).toBe('user_action_req_001');
    });
  });

  describe('USER_CLARIFICATION_RECEIVED', () => {
    it('resets status to running and clears blocking state', () => {
      applyEventToRuntime(workflowStore, {
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

      applyEventToRuntime(workflowStore, {
        type: 'USER_CLARIFICATION_RECEIVED',
        payload: {
          requestId: 'req_001',
          response: 'German law',
          respondingToAgentId: 'critic_r1',
          round: 1,
        },
      });

      expect(workflowStore.runtimeStatus).toBe('running');
      expect(workflowStore.runtimeBlockingUserRequestId).toBeNull();
      // Active node reverts to the responding agent (processing the answer)
      expect(workflowStore.runtimeActiveNodeId).toBe('critic_r1');
    });
  });

  describe('ROUND_COMPLETED', () => {
    it('increments currentRound and clears active state', () => {
      applyEventToRuntime(workflowStore, {
        type: 'ROUND_COMPLETED',
        payload: {
          round: 1,
          finalArtifactId: 'consensus_r1',
          pathTaken: [],
        },
      });

      expect(workflowStore.runtimeCurrentRound).toBe(2);
      expect(workflowStore.runtimeActiveNodeId).toBeNull();
      expect(workflowStore.runtimeActiveEdgeId).toBeNull();
    });
  });

  describe('WORKFLOW_COMPLETED', () => {
    it('sets status to completed and clears active state', () => {
      applyEventToRuntime(workflowStore, {
        type: 'WORKFLOW_COMPLETED',
        payload: {
          finalConsensusId: 'final',
          totalRounds: 3,
          totalDurationMs: 45000,
        },
      });

      expect(workflowStore.runtimeStatus).toBe('completed');
      expect(workflowStore.runtimeActiveNodeId).toBeNull();
      expect(workflowStore.runtimeActiveEdgeId).toBeNull();
    });
  });

  describe('unknown event type', () => {
    it('does not modify runtime for unknown events', () => {
      const beforeStatus = workflowStore.runtimeStatus;
      const beforePath = workflowStore.runtimeExecutionPath;
      applyEventToRuntime(workflowStore, { type: 'UNKNOWN_EVENT', payload: {} });
      expect(workflowStore.runtimeStatus).toBe(beforeStatus);
      expect(workflowStore.runtimeExecutionPath).toEqual(beforePath);
    });
  });
});
