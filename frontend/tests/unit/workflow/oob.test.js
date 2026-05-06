/**
 * Unit Tests — OOB Queue & Router
 *
 * Tests OOB input submission, consumption, staleness, and race-condition routing.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import {
  graphNodes,
  graphEdges,
  runtime,
  oobQueue,
  resetWorkflow,
} from '../../../src/lib/workflow/store.js';
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
      const id = submitOOBInput({
        content: 'Additional context',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      expect(id).toBeTruthy();
      expect(id).toMatch(/^oob_/);

      const q = get(oobQueue);
      expect(q.items).toHaveLength(1);
      expect(q.items[0].id).toBe(id);
      expect(q.items[0].content).toBe('Additional context');
      expect(q.items[0].status).toBe('pending');
    });

    it('indexes OOB by target for fast lookup', () => {
      submitOOBInput({
        content: 'test',
        target: { type: 'specific_agent', agentRole: 'critic', round: 1 },
        urgency: 'append',
      });

      const q = get(oobQueue);
      expect(q.indexByTarget.has('specific:critic:1')).toBe(true);
      expect(q.indexByTarget.get('specific:critic:1')).toHaveLength(1);
    });

    it('dispatches a USER_OUT_OF_BAND_INPUT event', () => {
      // Set up a target agent node so resolveTargetAgentId finds it
      graphNodes.update(nodes => {
        nodes.set('strategist_r1', {
          id: 'strategist_r1',
          type: 'agent',
          data: { role: 'strategist', round: 1, status: 'active' },
        });
        return nodes;
      });

      submitOOBInput({
        content: 'test context',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'inject_now',
      });

      // The event should have been dispatched and added to eventLog
      // We can verify indirectly by checking if a side_input node was created
      const nodes = get(graphNodes);
      const sideInputNodes = Array.from(nodes.values()).filter(
        n => n.id.startsWith('side_input_oob_')
      );
      expect(sideInputNodes.length).toBeGreaterThan(0);
    });

    it('generates unique IDs for multiple submissions', () => {
      const id1 = submitOOBInput({
        content: 'first',
        target: { type: 'current_active' },
        urgency: 'append',
      });
      const id2 = submitOOBInput({
        content: 'second',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      expect(id1).not.toBe(id2);
    });
  });

  describe('consumeOOBForAgent', () => {
    it('returns pending OOBs for a specific agent and round', () => {
      submitOOBInput({
        content: 'for strategist r1',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      const results = consumeOOBForAgent('strategist', 1);
      expect(results).toHaveLength(1);
      expect(results[0].content).toBe('for strategist r1');
    });

    it('does not return consumed OOBs', () => {
      const id = submitOOBInput({
        content: 'test',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      markOOBConsumed(id, 'strategist_r1');

      const results = consumeOOBForAgent('strategist', 1);
      expect(results).toHaveLength(0);
    });

    it('returns "next_agent" OOBs when previous role targeted next', () => {
      // "next_agent" from strategist should be consumed by critic
      submitOOBInput({
        content: 'for next after strategist',
        target: { type: 'next_agent', currentAgentRole: 'strategist' },
        urgency: 'append',
      });

      const results = consumeOOBForAgent('critic', 1);
      expect(results).toHaveLength(1);
    });

    it('returns "all_future" OOBs from earlier or same round', () => {
      submitOOBInput({
        content: 'for all future from round 1',
        target: { type: 'all_future', fromRound: 1 },
        urgency: 'append',
      });

      const results = consumeOOBForAgent('optimizer', 2);
      expect(results).toHaveLength(1);
    });

    it('returns "current_active" OOBs for any agent', () => {
      submitOOBInput({
        content: 'for current active',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      const results = consumeOOBForAgent('moderator', 1);
      expect(results).toHaveLength(1);
    });

    it('deduplicates OOBs matched by multiple rules', () => {
      // A specific OOB should only appear once even if multiple rules match
      submitOOBInput({
        content: 'specific',
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
        urgency: 'append',
      });

      const results = consumeOOBForAgent('strategist', 1);
      const ids = results.map(r => r.id);
      const uniqueIds = new Set(ids);
      expect(ids.length).toBe(uniqueIds.size);
    });
  });

  describe('markOOBConsumed', () => {
    it('marks an OOB as consumed with agent ID and timestamp', () => {
      const id = submitOOBInput({
        content: 'test',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      markOOBConsumed(id, 'strategist_r1');

      const q = get(oobQueue);
      const oob = q.items.find(o => o.id === id);
      expect(oob.status).toBe('consumed');
      expect(oob.consumedBy).toBe('strategist_r1');
      expect(oob.consumedAt).toBeDefined();
    });

    it('does not throw for non-existent OOB ID', () => {
      expect(() => {
        markOOBConsumed('nonexistent_id', 'agent');
      }).not.toThrow();
    });
  });

  describe('getPendingOOBCount', () => {
    it('returns count of pending OOBs', () => {
      submitOOBInput({
        content: 'one',
        target: { type: 'current_active' },
        urgency: 'append',
      });
      submitOOBInput({
        content: 'two',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      expect(getPendingOOBCount()).toBe(2);
    });

    it('does not count consumed OOBs', () => {
      const id = submitOOBInput({
        content: 'test',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      markOOBConsumed(id, 'agent');
      expect(getPendingOOBCount()).toBe(0);
    });
  });

  describe('clearStaleOOB', () => {
    it('marks old pending OOBs as stale', () => {
      // Submit an OOB and manually backdate its timestamp
      const id = submitOOBInput({
        content: 'old context',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      // Backdate the timestamp
      oobQueue.update(q => {
        const oob = q.items.find(o => o.id === id);
        oob.timestamp = Date.now() - 60000; // 1 minute ago
        return q;
      });

      clearStaleOOB(30000); // 30 second threshold

      const q = get(oobQueue);
      const oob = q.items.find(o => o.id === id);
      expect(oob.status).toBe('stale');
    });

    it('does not mark recent OOBs as stale', () => {
      submitOOBInput({
        content: 'recent',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      clearStaleOOB(60000); // 60 second threshold

      const q = get(oobQueue);
      expect(q.items[0].status).toBe('pending');
    });

    it('does not mark consumed OOBs as stale', () => {
      const id = submitOOBInput({
        content: 'consumed',
        target: { type: 'current_active' },
        urgency: 'append',
      });

      markOOBConsumed(id, 'agent');

      // Backdate
      oobQueue.update(q => {
        const oob = q.items.find(o => o.id === id);
        oob.timestamp = Date.now() - 120000;
        return q;
      });

      clearStaleOOB(30000);

      const q = get(oobQueue);
      const oob = q.items.find(o => o.id === id);
      expect(oob.status).toBe('consumed'); // Not stale
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

      const result = routeOOB(oob);
      expect(result.type).toBe('specific_agent');
      expect(result.agentRole).toBe('strategist');
    });

    it('forwards to next_agent when target agent is already completed', () => {
      graphNodes.update(nodes => {
        nodes.set('strategist_r1', {
          id: 'strategist_r1',
          type: 'agent',
          data: { role: 'strategist', round: 1, status: 'completed' },
        });
        return nodes;
      });

      const oob = {
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
      };

      const result = routeOOB(oob);
      expect(result.type).toBe('next_agent');
      expect(result.currentAgentRole).toBe('strategist');
    });

    it('returns original target when agent is active', () => {
      graphNodes.update(nodes => {
        nodes.set('strategist_r1', {
          id: 'strategist_r1',
          type: 'agent',
          data: { role: 'strategist', round: 1, status: 'active' },
        });
        return nodes;
      });

      const oob = {
        target: { type: 'specific_agent', agentRole: 'strategist', round: 1 },
      };

      const result = routeOOB(oob);
      expect(result.type).toBe('specific_agent');
      expect(result.agentRole).toBe('strategist');
    });
  });

  describe('routeOOB — current_active', () => {
    it('resolves to specific_agent when an agent is active', () => {
      runtime.update(r => ({
        ...r,
        status: 'running',
        activeNodeId: 'strategist_r1',
        currentRound: 1,
      }));

      const oob = {
        target: { type: 'current_active' },
      };

      const result = routeOOB(oob);
      expect(result.type).toBe('specific_agent');
      expect(result.agentRole).toBe('strategist');
      expect(result.round).toBe(1);
    });

    it('routes to next_agent from input when nobody is active', () => {
      const oob = {
        target: { type: 'current_active' },
      };

      const result = routeOOB(oob);
      expect(result.type).toBe('next_agent');
      expect(result.currentAgentRole).toBe('input');
    });
  });

  describe('routeOOB — pass-through', () => {
    it('passes through next_agent target unchanged', () => {
      const oob = {
        target: { type: 'next_agent', currentAgentRole: 'strategist' },
      };

      const result = routeOOB(oob);
      expect(result).toEqual(oob.target);
    });

    it('passes through all_future target unchanged', () => {
      const oob = {
        target: { type: 'all_future', fromRound: 1 },
      };

      const result = routeOOB(oob);
      expect(result).toEqual(oob.target);
    });
  });
});
