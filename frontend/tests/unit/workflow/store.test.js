/**
 * Unit Tests — Workflow Store Integration & Snapshot System
 *
 * Tests the dispatchEvent entry point, resetWorkflow, derived stores,
 * and the snapshot system.
 *
 * Migrated to Svelte 5 runes (workflowStore.X) from Svelte 4 stores.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { workflowStore, dispatchEvent, resetWorkflow } from '../../../src/lib/workflow/store.svelte.js';

describe('Workflow Store — dispatchEvent integration', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('dispatchEvent', () => {
    it('adds events to the audit log', () => {
      dispatchEvent({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      const log = workflowStore.eventLog;
      expect(log).toHaveLength(1);
      expect(log[0].type).toBe('AGENT_STARTED');
    });

    it('accumulates multiple events in the audit log', () => {
      dispatchEvent({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      dispatchEvent({
        type: 'AGENT_COMPLETED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          outputArtifactId: 'strategy_r1',
          durationMs: 3000,
        },
      });

      const log = workflowStore.eventLog;
      expect(log).toHaveLength(2);
    });

    it('updates graph nodes via graphReducer', () => {
      dispatchEvent({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      expect(workflowStore.graphNodes.has('strategist_r1')).toBe(true);
    });

    it('updates runtime via runtimeReducer', () => {
      dispatchEvent({
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
    });

    it('creates snapshot on ROUND_COMPLETED', () => {
      dispatchEvent({
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

      dispatchEvent({
        type: 'ROUND_COMPLETED',
        payload: {
          round: 1,
          finalArtifactId: 'consensus_r1',
          pathTaken: [],
        },
      });

      const snaps = workflowStore.roundSnapshots;
      expect(snaps).toHaveLength(1);
      expect(snaps[0].round).toBe(1);
      expect(snaps[0].title).toBe('Round 1');
      expect(snaps[0].nodes.length).toBeGreaterThan(0);
      expect(snaps[0].completedAt).toBeDefined();
    });
  });

  describe('resetWorkflow', () => {
    it('clears all stores to initial state', () => {
      dispatchEvent({
        type: 'AGENT_STARTED',
        payload: {
          agentId: 'strategist_r1',
          role: 'strategist',
          round: 1,
          inputArtifactIds: [],
          timestamp: Date.now(),
        },
      });

      dispatchEvent({
        type: 'ROUND_COMPLETED',
        payload: {
          round: 1,
          finalArtifactId: 'consensus_r1',
          pathTaken: [],
        },
      });

      resetWorkflow();

      expect(workflowStore.graphNodes.size).toBe(0);
      expect(workflowStore.graphEdges.size).toBe(0);
      expect(workflowStore.runtimeStatus).toBe('idle');
      expect(workflowStore.runtimeCurrentRound).toBe(0);
      expect(workflowStore.runtimeActiveNodeId).toBeNull();
      expect(workflowStore.roundSnapshots).toHaveLength(0);
      expect(workflowStore.eventLog).toHaveLength(0);
      expect(workflowStore.oobQueueItems).toHaveLength(0);
    });
  });

  describe('derived stores', () => {
    describe('flowNodes', () => {
      it('converts graphNodes to Svelte Flow format', () => {
        dispatchEvent({
          type: 'AGENT_STARTED',
          payload: {
            agentId: 'strategist_r1',
            role: 'strategist',
            round: 1,
            inputArtifactIds: [],
            timestamp: Date.now(),
          },
        });

        const nodes = workflowStore.flowNodes;
        expect(nodes).toHaveLength(1);
        expect(nodes[0].id).toBe('strategist_r1');
        expect(nodes[0].type).toBe('agent');
        expect(nodes[0].position).toBeDefined();
        expect(nodes[0].className).toBeDefined();
      });

      it('overlays runtime isActive on matching node', () => {
        dispatchEvent({
          type: 'AGENT_STARTED',
          payload: {
            agentId: 'strategist_r1',
            role: 'strategist',
            round: 1,
            inputArtifactIds: [],
            timestamp: Date.now(),
          },
        });

        const nodes = workflowStore.flowNodes;
        expect(nodes[0].data.isActive).toBe(true);
      });
    });

    describe('flowEdges', () => {
      it('converts graphEdges to Svelte Flow format', () => {
        // Need an input node first so pipeline-based edge gets created
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
        dispatchEvent({
          type: 'AGENT_STARTED',
          payload: {
            agentId: 'strategist_r1',
            role: 'strategist',
            round: 1,
            inputArtifactIds: [],
            timestamp: Date.now(),
          },
        });

        const edges = workflowStore.flowEdges;
        expect(edges.length).toBeGreaterThan(0);
        expect(edges[0].source).toBeDefined();
        expect(edges[0].target).toBeDefined();
        expect(edges[0].className).toBeDefined();
      });
    });

    describe('pendingOOBCount', () => {
      it('counts pending OOB items', () => {
        workflowStore.oobQueueItems.push(
          { id: '1', status: 'pending' },
          { id: '2', status: 'consumed' },
          { id: '3', status: 'pending' }
        );

        expect(workflowStore.pendingOOBCount).toBe(2);
      });
    });
  });
});

describe('Snapshot System', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  it('snapshots include deep copies of nodes with isActive=false', () => {
    dispatchEvent({
      type: 'AGENT_STARTED',
      payload: {
        agentId: 'strategist_r1',
        role: 'strategist',
        round: 1,
        inputArtifactIds: [],
        timestamp: Date.now(),
      },
    });

    dispatchEvent({
      type: 'ROUND_COMPLETED',
      payload: {
        round: 1,
        finalArtifactId: 'consensus_r1',
        pathTaken: [],
      },
    });

    const snaps = workflowStore.roundSnapshots;
    const snapshotNode = snaps[0].nodes.find(n => n.id === 'strategist_r1');
    expect(snapshotNode.data.isActive).toBe(false);
    expect(snapshotNode.data.status).toBe('completed');
  });

  it('snapshots include deep copies of edges with isActive=false', () => {
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
    dispatchEvent({
      type: 'AGENT_STARTED',
      payload: {
        agentId: 'strategist_r1',
        role: 'strategist',
        round: 1,
        inputArtifactIds: [],
        timestamp: Date.now(),
      },
    });

    dispatchEvent({
      type: 'ROUND_COMPLETED',
      payload: {
        round: 1,
        finalArtifactId: 'consensus_r1',
        pathTaken: [],
      },
    });

    const snaps = workflowStore.roundSnapshots;
    snaps[0].edges.forEach(edge => {
      expect(edge.data.isActive).toBe(false);
    });
  });

  it('resets executionPath after snapshot creation', () => {
    dispatchEvent({
      type: 'AGENT_STARTED',
      payload: {
        agentId: 'strategist_r1',
        role: 'strategist',
        round: 1,
        inputArtifactIds: [],
        timestamp: Date.now(),
      },
    });

    dispatchEvent({
      type: 'ROUND_COMPLETED',
      payload: {
        round: 1,
        finalArtifactId: 'consensus_r1',
        pathTaken: [],
      },
    });

    expect(workflowStore.runtimeExecutionPath).toEqual([]);
  });

  it('accumulates multiple round snapshots', () => {
    dispatchEvent({
      type: 'ROUND_COMPLETED',
      payload: { round: 1, finalArtifactId: 'c1', pathTaken: [] },
    });

    dispatchEvent({
      type: 'ROUND_COMPLETED',
      payload: { round: 2, finalArtifactId: 'c2', pathTaken: [] },
    });

    const snaps = workflowStore.roundSnapshots;
    expect(snaps).toHaveLength(2);
    expect(snaps[0].round).toBe(1);
    expect(snaps[1].round).toBe(2);
  });
});
