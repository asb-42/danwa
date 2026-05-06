/**
 * Unit Tests — Runtime Reducer (Event → Runtime Status Update)
 *
 * Tests that each workflow event correctly updates the runtime state.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { runtime, resetWorkflow } from '../../../src/lib/workflow/store.js';
import { applyEventToRuntime } from '../../../src/lib/workflow/runtimeReducer.js';

describe('runtimeReducer', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('AGENT_STARTED', () => {
    it('sets status to running and activeNodeId to agent', () => {
      applyEventToRuntime({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      const rt = get(runtime);
      expect(rt.status).toBe('running');
      expect(rt.activeNodeId).toBe('strategist_r1');
      expect(rt.activeEdgeId).toBeNull();
    });

    it('appends agent to executionPath', () => {
      applyEventToRuntime({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToRuntime({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'critic_r1',
          role: 'critic',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      const rt = get(runtime);
      expect(rt.executionPath).toEqual(['strategist_r1', 'critic_r1']);
    });
  });

  describe('AGENT_COMPLETED', () => {
    it('clears activeNodeId', () => {
      // Start an agent first
      applyEventToRuntime({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      applyEventToRuntime({
        type: 'AGENT_COMPLETED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          outputArtifactId: 'strategy_r1',
          durationMs: 5000,
        },
      });

      const rt = get(runtime);
      expect(rt.activeNodeId).toBeNull();
    });
  });

  describe('USER_CLARIFICATION_REQUESTED', () => {
    it('sets status to waiting_for_user and blocking request id', () => {
      applyEventToRuntime({
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

      const rt = get(runtime);
      expect(rt.status).toBe('waiting_for_user');
      expect(rt.blockingUserRequestId).toBe('req_001');
      expect(rt.activeNodeId).toBe('user_action_req_001');
    });
  });

  describe('USER_CLARIFICATION_RECEIVED', () => {
    it('resets status to running and clears blocking state', () => {
      // First request clarification
      applyEventToRuntime({
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

      applyEventToRuntime({
        type: 'USER_CLARIFICATION_RECEIVED',
        payload: {
          requestId: 'req_001',
          response: 'German law',
          respondingToAgentId: 'critic_r1',
          round: 1,
        },
      });

      const rt = get(runtime);
      expect(rt.status).toBe('running');
      expect(rt.blockingUserRequestId).toBeNull();
      expect(rt.activeNodeId).toBeNull();
    });
  });

  describe('ROUND_COMPLETED', () => {
    it('increments currentRound and clears active state', () => {
      applyEventToRuntime({
        type: 'ROUND_COMPLETED',
        payload: {
          round: 1,
          finalArtifactId: 'consensus_r1',
          pathTaken: [],
        },
      });

      const rt = get(runtime);
      expect(rt.currentRound).toBe(2);
      expect(rt.activeNodeId).toBeNull();
      expect(rt.activeEdgeId).toBeNull();
    });
  });

  describe('WORKFLOW_COMPLETED', () => {
    it('sets status to completed and clears active state', () => {
      applyEventToRuntime({
        type: 'WORKFLOW_COMPLETED',
        payload: {
          finalConsensusId: 'final',
          totalRounds: 3,
          totalDurationMs: 45000,
        },
      });

      const rt = get(runtime);
      expect(rt.status).toBe('completed');
      expect(rt.activeNodeId).toBeNull();
      expect(rt.activeEdgeId).toBeNull();
    });
  });

  describe('unknown event type', () => {
    it('does not modify runtime for unknown events', () => {
      const before = get(runtime);
      applyEventToRuntime({ type: 'UNKNOWN_EVENT', payload: {} });
      const after = get(runtime);
      expect(after).toEqual(before);
    });
  });
});
