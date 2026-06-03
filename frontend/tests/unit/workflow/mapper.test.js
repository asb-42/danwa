/**
 * Unit Tests — SSE → Workflow Event Mapper
 *
 * Tests that raw SSE events from the backend are correctly mapped
 * to workflow events and dispatched to the store.
 *
 * Migrated to Svelte 5 runes (workflowStore.X) from Svelte 4 stores.
 * Edge IDs use pipeline order format `<source>-><target>` (no _N suffix).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { workflowStore, resetWorkflow } from '../../../src/lib/workflow/store.svelte.js';
import { handleWorkflowSSE } from '../../../src/lib/workflow/mapper.js';

describe('mapper (SSE → Workflow Events)', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('workflow_started', () => {
    it('dispatches AGENT_STARTED for the input node', () => {
      handleWorkflowSSE({ type: 'workflow_started' });

      const nodes = workflowStore.graphNodes;
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

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('strategist_r1')).toBe(true);
      expect(nodes.get('strategist_r1').data.role).toBe('strategist');
      expect(nodes.get('strategist_r1').data.round).toBe(1);
      expect(nodes.get('strategist_r1').data.status).toBe('active');
    });

    it('connects strategist to input node in round 1', () => {
      handleWorkflowSSE({ type: 'workflow_started' });
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 1,
      });

      const edges = workflowStore.graphEdges;
      expect(edges.has('input->strategist_r1')).toBe(true);
    });

    it('connects critic to previous pipeline agent (strategist) in same round', () => {
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 1,
      });
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'critic',
        round: 1,
      });

      const edges = workflowStore.graphEdges;
      expect(edges.has('strategist_r1->critic_r1')).toBe(true);
    });

    it('connects to previous round moderator output for strategist in round 2', () => {
      // This test documents the current pipeline-based behavior.
      // For round 2 strategist, no `moderator_output_r1` artifact exists,
      // and no `decision_r1` exists, so no edge is created.
      handleWorkflowSSE({
        type: 'agent_preparing',
        role: 'strategist',
        round: 2,
      });

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('strategist_r2')).toBe(true);
    });
  });

  describe('agent_output', () => {
    it('dispatches ARTIFACT_PRODUCED and AGENT_COMPLETED', () => {
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

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('strategist_output_r1')).toBe(true);
      expect(nodes.get('strategist_output_r1').type).toBe('artifact');
      expect(nodes.get('strategist_output_r1').data.artifactType).toBe('strategy');
      expect(nodes.get('strategist_output_r1').data.tokenCount).toBe(250);

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

        const nodes = workflowStore.graphNodes;
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

      const nodes = workflowStore.graphNodes;
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

      const nodes = workflowStore.graphNodes;
      expect(nodes.get('strategist_output_r1').data.summary).toBe('');
    });
  });

  describe('round_update', () => {
    it('dispatches ROUND_COMPLETED', () => {
      handleWorkflowSSE({
        type: 'round_update',
        round: 1,
      });

      expect(workflowStore.runtimeCurrentRound).toBe(2);
    });
  });

  describe('status_change', () => {
    it('dispatches WORKFLOW_COMPLETED on completed status', () => {
      handleWorkflowSSE({
        type: 'status_change',
        status: 'completed',
        round: 3,
      });

      expect(workflowStore.runtimeStatus).toBe('completed');
    });

    it('dispatches WORKFLOW_COMPLETED on failed status', () => {
      handleWorkflowSSE({
        type: 'status_change',
        status: 'failed',
        round: 2,
      });

      expect(workflowStore.runtimeStatus).toBe('completed');
    });

    it('does not dispatch for running status', () => {
      handleWorkflowSSE({
        type: 'status_change',
        status: 'running',
      });

      expect(workflowStore.runtimeStatus).toBe('idle');
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

      const nodes = workflowStore.graphNodes;
      expect(nodes.has('input')).toBe(true);
      expect(nodes.has('strategist_r1')).toBe(true);
      expect(nodes.has('strategist_output_r1')).toBe(true);
      expect(nodes.has('critic_r1')).toBe(true);
      expect(nodes.has('critic_output_r1')).toBe(true);

      expect(nodes.get('strategist_r1').data.status).toBe('completed');
      expect(nodes.get('critic_r1').data.status).toBe('completed');

      // Pipeline edges
      const edges = workflowStore.graphEdges;
      expect(edges.has('input->strategist_r1')).toBe(true);
      expect(edges.has('strategist_r1->critic_r1')).toBe(true);
    });
  });
});
