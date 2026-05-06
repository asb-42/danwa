/**
 * Unit Tests — Workflow Store Integration & Snapshot System
 *
 * Tests the dispatchEvent entry point, resetWorkflow, derived stores,
 * and the snapshot system.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
  graphNodes,
  graphEdges,
  runtime,
  roundSnapshots,
  eventLog,
  oobQueue,
  flowNodes,
  flowEdges,
  pendingOOBCount,
  dispatchEvent,
  resetWorkflow,
} from '../../../src/lib/workflow/store.js';

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

      const log = get(eventLog);
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

      const log = get(eventLog);
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

      const nodes = get(graphNodes);
      expect(nodes.has('strategist_r1')).toBe(true);
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

      const rt = get(runtime);
      expect(rt.status).toBe('running');
      expect(rt.activeNodeId).toBe('strategist_r1');
    });

    it('creates snapshot on ROUND_COMPLETED', () => {
      // Set up some graph state first
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

      const snaps = get(roundSnapshots);
      expect(snaps).toHaveLength(1);
      expect(snaps[0].round).toBe(1);
      expect(snaps[0].title).toBe('Round 1');
      expect(snaps[0].nodes.length).toBeGreaterThan(0);
      expect(snaps[0].completedAt).toBeDefined();
    });
  });

  describe('resetWorkflow', () => {
    it('clears all stores to initial state', () => {
      // Populate stores
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

      // Reset
      resetWorkflow();

      expect(get(graphNodes).size).toBe(0);
      expect(get(graphEdges).size).toBe(0);
      expect(get(runtime).status).toBe('idle');
      expect(get(runtime).currentRound).toBe(0);
      expect(get(runtime).activeNodeId).toBeNull();
      expect(get(roundSnapshots)).toHaveLength(0);
      expect(get(eventLog)).toHaveLength(0);
      expect(get(oobQueue).items).toHaveLength(0);
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

        const nodes = get(flowNodes);
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

        const nodes = get(flowNodes);
        expect(nodes[0].data.isActive).toBe(true);
      });
    });

    describe('flowEdges', () => {
      it('converts graphEdges to Svelte Flow format', () => {
        dispatchEvent({
          type: 'AGENT_STARTED',
          payload: {
            agentId: 'strategist_r1',
            role: 'strategist',
            round: 1,
            inputArtifactIds: ['input'],
            timestamp: Date.now(),
          },
        });

        const edges = get(flowEdges);
        expect(edges.length).toBeGreaterThan(0);
        expect(edges[0].source).toBeDefined();
        expect(edges[0].target).toBeDefined();
        expect(edges[0].className).toBeDefined();
      });
    });

    describe('pendingOOBCount', () => {
      it('counts pending OOB items', () => {
        // Directly manipulate the store for this test
        oobQueue.update(q => {
          q.items.push(
            { id: '1', status: 'pending' },
            { id: '2', status: 'consumed' },
            { id: '3', status: 'pending' }
          );
          return q;
        });

        expect(get(pendingOOBCount)).toBe(2);
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

    const snaps = get(roundSnapshots);
    const snapshotNode = snaps[0].nodes.find(n => n.id === 'strategist_r1');
    expect(snapshotNode.data.isActive).toBe(false);
    expect(snapshotNode.data.status).toBe('completed');
  });

  it('snapshots include deep copies of edges with isActive=false', () => {
    dispatchEvent({
      type: 'AGENT_STARTED',
      payload: {
        agentId: 'strategist_r1',
        role: 'strategist',
        round: 1,
        inputArtifactIds: ['input'],
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

    const snaps = get(roundSnapshots);
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

    const rt = get(runtime);
    expect(rt.executionPath).toEqual([]);
  });

  it('accumulates multiple round snapshots', () => {
    // Round 1
    dispatchEvent({
      type: 'ROUND_COMPLETED',
      payload: { round: 1, finalArtifactId: 'c1', pathTaken: [] },
    });

    // Round 2
    dispatchEvent({
      type: 'ROUND_COMPLETED',
      payload: { round: 2, finalArtifactId: 'c2', pathTaken: [] },
    });

    const snaps = get(roundSnapshots);
    expect(snaps).toHaveLength(2);
    expect(snaps[0].round).toBe(1);
    expect(snaps[1].round).toBe(2);
  });
});
