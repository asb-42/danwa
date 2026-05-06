/**
 * Unit Tests — SSE → Workflow Event Mapper
 *
 * Tests that raw SSE events from the backend are correctly mapped
 * to workflow events and dispatched to the store.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
  graphNodes,
  graphEdges,
  runtime,
  eventLog,
  resetWorkflow,
} from '../../../src/lib/workflow/store.js';
import { handleWorkflowSSE } from '../../../src/lib/workflow/mapper.js';

describe('mapper (SSE → Workflow Events)', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('workflow_started', () => {
    it('dispatches AGENT_STARTED for the input node', () => {
      handleWorkflowSSE({ type: 'workflow_started' });

      const nodes = get(graphNodes);
      expect(nodes.has('input')).toBe(true);
      expect(nodes.get('input').data.role).toBe('input');
      expect(nodes.get('input').data.round).toBe(0);
    });
  });

  describe('agent_preparing', () => {
    it('dispatches AGENT_STARTED with correct agent ID and role', () => {
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 1,
      });

      const nodes = get(graphNodes);
      expect(nodes.has('strategist_r1')).toBe(true);
      expect(nodes.get('strategist_r1').data.role).toBe('strategist');
      expect(nodes.get('strategist_r1').data.round).toBe(1);
      expect(nodes.get('strategist_r1').data.status).toBe('active');
    });

    it('sets input artifact for first strategist in round 1', () => {
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 1,
      });

      const edges = get(graphEdges);
      expect(edges.has('input->strategist_r1_0')).toBe(true);
    });

    it('sets input artifact from previous agent in same round', () => {
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'critic',
        round: 1,
      });

      const edges = get(graphEdges);
      expect(edges.has('strategist_output_r1->critic_r1_0')).toBe(true);
    });

    it('sets input artifact from previous round moderator output', () => {
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 2,
      });

      const edges = get(graphEdges);
      expect(edges.has('moderator_output_r1->strategist_r2_0')).toBe(true);
    });
  });

  describe('agent_output', () => {
    it('dispatches ARTIFACT_PRODUCED and AGENT_COMPLETED', () => {
      // First start the agent
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 1,
      });

      handleWorkflowSSE({
        type: 'agent_output',
        role: 'strategist',
        round: 1,
        content: 'This is the strategy output with detailed analysis...',
        tokens: 250,
        duration_ms: 3500,
      });

      // Check artifact was created (mapper uses ${role}_output_r${round})
      const nodes = get(graphNodes);
      expect(nodes.has('strategist_output_r1')).toBe(true);
      expect(nodes.get('strategist_output_r1').type).toBe('artifact');
      expect(nodes.get('strategist_output_r1').data.artifactType).toBe('strategy');
      expect(nodes.get('strategist_output_r1').data.tokenCount).toBe(250);

      // Check agent was marked completed
      expect(nodes.get('strategist_r1').data.status).toBe('completed');
      expect(nodes.get('strategist_r1').data.isActive).toBe(false);
    });

    it('maps roles to correct artifact types', () => {
      const roleArtifactMap = {
        strategist: 'strategy',
        critic: 'critique',
        optimizer: 'synthesis',
        moderator: 'consensus',
      };

      for (const [role, artifactType] of Object.entries(roleArtifactMap)) {
        resetWorkflow();

        handleWorkflowSSE({
          type: 'agent_output',
          role,
          round: 1,
          content: 'output',
          tokens: 100,
          duration_ms: 1000,
        });

        const nodes = get(graphNodes);
        const artifactId = `${role}_output_r1`;
        expect(nodes.has(artifactId)).toBe(true);
        expect(nodes.get(artifactId).data.artifactType).toBe(artifactType);
      }
    });

    it('truncates content to 100 chars for summary', () => {
      const longContent = 'A'.repeat(200);
      handleWorkflowSSE({
        type: 'agent_output',
        role: 'strategist',
        round: 1,
        content: longContent,
        tokens: 100,
        duration_ms: 1000,
      });

      const nodes = get(graphNodes);
      expect(nodes.get('strategist_output_r1').data.summary.length).toBeLessThanOrEqual(100);
    });

    it('handles missing content gracefully', () => {
      handleWorkflowSSE({
        type: 'agent_output',
        role: 'strategist',
        round: 1,
        tokens: 50,
        duration_ms: 500,
      });

      const nodes = get(graphNodes);
      expect(nodes.get('strategist_output_r1').data.summary).toBe('');
    });
  });

  describe('round_update', () => {
    it('dispatches ROUND_COMPLETED', () => {
      handleWorkflowSSE({
        type: 'round_update',
        round: 1,
      });

      const rt = get(runtime);
      expect(rt.currentRound).toBe(2); // incremented by runtimeReducer
    });
  });

  describe('status_change', () => {
    it('dispatches WORKFLOW_COMPLETED on completed status', () => {
      handleWorkflowSSE({
        type: 'status_change',
        status: 'completed',
        round: 3,
      });

      const rt = get(runtime);
      expect(rt.status).toBe('completed');
    });

    it('dispatches WORKFLOW_COMPLETED on failed status', () => {
      handleWorkflowSSE({
        type: 'status_change',
        status: 'failed',
        round: 2,
      });

      const rt = get(runtime);
      expect(rt.status).toBe('completed');
    });

    it('does not dispatch for running status', () => {
      handleWorkflowSSE({
        type: 'status_change',
        status: 'running',
      });

      const rt = get(runtime);
      expect(rt.status).toBe('idle');
    });
  });

  describe('unknown SSE event type', () => {
    it('does not throw for unknown SSE events', () => {
      expect(() => {
        handleWorkflowSSE({ type: 'unknown_sse_event', data: 'test' });
      }).not.toThrow();
    });
  });

  describe('full workflow simulation', () => {
    it('processes a complete round of SSE events', () => {
      // 1. Workflow starts
      handleWorkflowSSE({ type: 'workflow_started' });

      // 2. Strategist prepares
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 1,
      });

      // 3. Strategist outputs
      handleWorkflowSSE({
        type: 'agent_output',
        role: 'strategist',
        round: 1,
        content: 'Strategy analysis',
        tokens: 200,
        duration_ms: 3000,
      });

      // 4. Critic prepares
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'critic',
        round: 1,
      });

      // 5. Critic outputs
      handleWorkflowSSE({
        type: 'agent_output',
        role: 'critic',
        round: 1,
        content: 'Critique analysis',
        tokens: 150,
        duration_ms: 2500,
      });

      // Verify final state (mapper uses ${role}_output_r${round} for artifact IDs)
      const nodes = get(graphNodes);
      expect(nodes.has('input')).toBe(true);
      expect(nodes.has('strategist_r1')).toBe(true);
      expect(nodes.has('strategist_output_r1')).toBe(true);
      expect(nodes.has('critic_r1')).toBe(true);
      expect(nodes.has('critic_output_r1')).toBe(true);

      // Both agents should be completed
      expect(nodes.get('strategist_r1').data.status).toBe('completed');
      expect(nodes.get('critic_r1').data.status).toBe('completed');

      // Edges should exist
      const edges = get(graphEdges);
      expect(edges.has('input->strategist_r1_0')).toBe(true);
      expect(edges.has('strategist_r1->strategist_output_r1')).toBe(true);
      expect(edges.has('strategist_output_r1->critic_r1_0')).toBe(true);
      expect(edges.has('critic_r1->critic_output_r1')).toBe(true);
    });
  });
});
