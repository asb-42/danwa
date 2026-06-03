/**
 * Unit Tests — OOB Queue & Router
 *
 * Tests OOB input submission, consumption, staleness, and race-condition routing.
 *
 * Migrated to Svelte 5 runes (workflowStore.X) from Svelte 4 stores.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { workflowStore, resetWorkflow } from '../../../src/lib/workflow/store.svelte.js';
import {
  submitOOBInput,
  consumeOOBForAgent,
  markOOBConsumed,
  getPendingOOBCount,
  clearStaleOOB,
} from '../../../src/lib/workflow/oob.js';
import { routeOOB } from '../../../src/lib/workflow/oobRouter.js';

describe('OOB Queue (oob.js)', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('submitOOBInput', () => {
    it('adds an OOB input to the queue with pending status', () => {
      const id = submitOOBInput(workflowStore, {
        content: 'Additional context',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      expect(id).toBeTruthy();
      expect(id).toMatch(/^oob_/);

      const items = workflowStore.oobQueueItems;
      expect(items).toHaveLength(1);
      expect(items[0].id).toBe(id);
      expect(items[0].content).toBe('Additional context');
      expect(items[0].status).toBe('pending');
    });

    it('indexes OOB by target for fast lookup', () => {
      submitOOBInput(workflowStore, {
        content: 'test',
        target: { type: 'specific_agent', agentRole: 'critic', round: 1 },
        urgency: 'append',
      });

      const idx = workflowStore.oobQueueIndexByTarget;
      expect(idx.has('specific:critic:1')).toBe(true);
      expect(idx.get('specific:critic:1')).toHaveLength(1);
    });

    it('dispatches a USER_OUT_OF_BAND_INPUT event', () => {
      // Set up a target agent node so resolveTargetAgentId finds it
      workflowStore.graphNodes.set('strategist_r1', {
        id: 'strategist_r1',
        type: 'agent',
        data: { role: 'strategist', round: 1, status: 'active' },
      });

      submitOOBInput(workflowStore, {
        content: 'test context',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'inject_now',
      });

      const nodes = workflowStore.graphNodes;
      const sideInputNodes = Array.from(nodes.values()).filter(
        n => n.id.startsWith('side_input_oob_')
      );
      expect(sideInputNodes.length).toBeGreaterThan(0);
    });

    it('generates unique IDs for multiple submissions', () => {
      const id1 = submitOOBInput(workflowStore, {
        content: 'first',
        target: { type: 'current_active' },
        urgency: 'append',
      });
      const id2 = submitOOBInput(workflowStore, {
        content: 'second',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      expect(id1).not.toBe(id2);
    });
  });

  describe('consumeOOBForAgent', () => {
    it('returns pending OOBs for a specific agent and round', () => {
      submitOOBInput(workflowStore, {
        content: 'for strategist r1',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      const results = consumeOOBForAgent(workflowStore, 'strategist', 1);
      expect(results).toHaveLength(1);
      expect(results[0].content).toBe('for strategist r1');
    });

    it('does not return consumed OOBs', () => {
      const id = submitOOBInput(workflowStore, {
        content: 'test',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      markOOBConsumed(workflowStore, id, 'strategist_r1');

      const results = consumeOOBForAgent(workflowStore, 'strategist', 1);
      expect(results).toHaveLength(0);
    });

    it('returns "next_agent" OOBs when previous role targeted next', () => {
      submitOOBInput(workflowStore, {
        content: 'for next after strategist',
        target: { type: 'next_agent', currentAgentRole: 'strategist' },
        urgency: 'append',
      });

      const results = consumeOOBForAgent(workflowStore, 'critic', 1);
      expect(results).toHaveLength(1);
    });

    it('returns "all_future" OOBs from earlier or same round', () => {
      submitOOBInput(workflowStore, {
        content: 'for all future from round 1',
        target: { type: 'all_future', fromRound: 1 },
        urgency: 'append',
      });

      const results = consumeOOBForAgent(workflowStore, 'optimizer', 2);
      expect(results).toHaveLength(1);
    });

    it('returns "current_active" OOBs for any agent', () => {
      submitOOBInput(workflowStore, {
        content: 'for current active',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      const results = consumeOOBForAgent(workflowStore, 'moderator', 1);
      expect(results).toHaveLength(1);
    });

    it('deduplicates OOBs matched by multiple rules', () => {
      submitOOBInput(workflowStore, {
        content: 'specific',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      const results = consumeOOBForAgent(workflowStore, 'strategist', 1);
      const ids = results.map(r => r.id);
      const uniqueIds = new Set(ids);
      expect(ids.length).toBe(uniqueIds.size);
    });
  });

  describe('markOOBConsumed', () => {
    it('marks an OOB as consumed with agent ID and timestamp', () => {
      const id = submitOOBInput(workflowStore, {
        content: 'test',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      markOOBConsumed(workflowStore, id, 'strategist_r1');

      const oob = workflowStore.oobQueueItems.find(o => o.id === id);
      expect(oob.status).toBe('consumed');
      expect(oob.consumedBy).toBe('strategist_r1');
      expect(oob.consumedAt).toBeDefined();
    });

    it('does not throw for non-existent OOB ID', () => {
      expect(() => {
        markOOBConsumed(workflowStore, 'nonexistent_id', 'agent');
      }).not.toThrow();
    });
  });

  describe('getPendingOOBCount', () => {
    it('returns count of pending OOBs', () => {
      submitOOBInput(workflowStore, {
        content: 'one',
        target: { type: 'current_active' },
        urgency: 'append',
      });
      submitOOBInput(workflowStore, {
        content: 'two',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      expect(getPendingOOBCount(workflowStore)).toBe(2);
    });

    it('does not count consumed OOBs', () => {
      const id = submitOOBInput(workflowStore, {
        content: 'test',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      markOOBConsumed(workflowStore, id, 'agent');
      expect(getPendingOOBCount(workflowStore)).toBe(0);
    });
  });

  describe('clearStaleOOB', () => {
    it('marks old pending OOBs as stale', () => {
      const id = submitOOBInput(workflowStore, {
        content: 'old context',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      // Backdate the timestamp via direct mutation
      const oob = workflowStore.oobQueueItems.find(o => o.id === id);
      oob.timestamp = Date.now() - 60000;

      clearStaleOOB(workflowStore, 30000);

      const updated = workflowStore.oobQueueItems.find(o => o.id === id);
      expect(updated.status).toBe('stale');
    });

    it('does not mark recent OOBs as stale', () => {
      submitOOBInput(workflowStore, {
        content: 'recent',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      clearStaleOOB(workflowStore, 60000);

      expect(workflowStore.oobQueueItems[0].status).toBe('pending');
    });

    it('does not mark consumed OOBs as stale', () => {
      const id = submitOOBInput(workflowStore, {
        content: 'consumed',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      markOOBConsumed(workflowStore, id, 'agent');

      const oob = workflowStore.oobQueueItems.find(o => o.id === id);
      oob.timestamp = Date.now() - 120000;

      clearStaleOOB(workflowStore, 30000);

      const updated = workflowStore.oobQueueItems.find(o => o.id === id);
      expect(updated.status).toBe('consumed');
    });
  });
});

describe('OOB Router (oobRouter.js)', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('routeOOB — specific_agent', () => {
    it('returns original target when agent does not exist yet (queue for later)', () => {
      const oob = {
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
      };

      const result = routeOOB(workflowStore, oob);
      expect(result.type).toBe('specific_agent');
      expect(result.agentRole).toBe('strategist');
    });

    it('forwards to next_agent when target agent is already completed', () => {
      workflowStore.graphNodes.set('strategist_r1', {
        id: 'strategist_r1',
        type: 'agent',
        data: { role: 'strategist', round: 1, status: 'completed' },
      });

      const oob = {
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
      };

      const result = routeOOB(workflowStore, oob);
      expect(result.type).toBe('next_agent');
      expect(result.currentAgentRole).toBe('strategist');
    });

    it('returns original target when agent is active', () => {
      workflowStore.graphNodes.set('strategist_r1', {
        id: 'strategist_r1',
        type: 'agent',
        data: { role: 'strategist', round: 1, status: 'active' },
      });

      const oob = {
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
      };

      const result = routeOOB(workflowStore, oob);
      expect(result.type).toBe('specific_agent');
      expect(result.agentRole).toBe('strategist');
    });
  });

  describe('routeOOB — current_active', () => {
    it('resolves to specific_agent when an agent is active', () => {
      workflowStore.runtimeStatus = 'running';
      workflowStore.runtimeActiveNodeId = 'strategist_r1';
      workflowStore.runtimeCurrentRound = 1;

      const oob = {
        target: { type: 'current_active' },
      };

      const result = routeOOB(workflowStore, oob);
      expect(result.type).toBe('specific_agent');
      expect(result.agentRole).toBe('strategist');
      expect(result.round).toBe(1);
    });

    it('routes to next_agent from input when nobody is active', () => {
      const oob = {
        target: { type: 'current_active' },
      };

      const result = routeOOB(workflowStore, oob);
      expect(result.type).toBe('next_agent');
      expect(result.currentAgentRole).toBe('input');
    });
  });

  describe('routeOOB — pass-through', () => {
    it('passes through next_agent target unchanged', () => {
      const oob = {
        target: { type: 'next_agent', currentAgentRole: 'strategist' },
      };

      const result = routeOOB(workflowStore, oob);
      expect(result).toEqual(oob.target);
    });

    it('passes through all_future target unchanged', () => {
      const oob = {
        target: { type: 'all_future', fromRound: 1 },
      };

      const result = routeOOB(workflowStore, oob);
      expect(result).toEqual(oob.target);
    });
  });
});
