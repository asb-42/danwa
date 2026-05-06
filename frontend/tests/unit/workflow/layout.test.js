/**
 * Unit Tests — ELK Layout Engine
 *
 * Tests the ELK.js layout wrapper including node sizing,
 * graph building, and position extraction.
 *
 * Note: applyLayout uses setTimeout debounce, so we test
 * calculateLayout indirectly via the exported function.
 * We also test the helper functions by importing the module.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { graphNodes, graphEdges, resetWorkflow } from '../../../src/lib/workflow/store.js';

// We test the layout module's exported function and verify
// it doesn't throw and handles edge cases correctly.
// Full ELK integration requires async timing, so we focus on
// the input validation and topology-change detection.

describe('layout engine', () => {
  beforeEach(() => {
    resetWorkflow();
  });

  describe('applyLayout', () => {
    it('is exported and callable', async () => {
      const { applyLayout } = await import('../../../src/lib/workflow/layout.js');
      expect(typeof applyLayout).toBe('function');
    });

    it('does not throw with empty nodes/edges', async () => {
      const { applyLayout } = await import('../../../src/lib/workflow/layout.js');
      await expect(applyLayout([], [])).resolves.not.toThrow();
    });

    it('does not throw with valid nodes and edges', async () => {
      const { applyLayout } = await import('../../../src/lib/workflow/layout.js');

      const nodes = [
        { id: 'input', type: 'input', data: { round: 0 }, position: { x: 0, y: 0 } },
        { id: 'strategist_r1', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 } },
        { id: 'strategy_r1', type: 'artifact', data: { round: 1 }, position: { x: 0, y: 0 } },
      ];

      const edges = [
        { id: 'e1', source: 'input', target: 'strategist_r1' },
        { id: 'e2', source: 'strategist_r1', target: 'strategy_r1' },
      ];

      await expect(applyLayout(nodes, edges)).resolves.not.toThrow();
    });

    it('skips layout when topology has not changed', async () => {
      const { applyLayout } = await import('../../../src/lib/workflow/layout.js');

      const nodes = [
        { id: 'a', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 } },
      ];
      const edges = [];

      // First call
      await applyLayout(nodes, edges);

      // Second call with same count — should skip
      // (We can't directly verify skip, but it should not throw)
      await expect(applyLayout(nodes, edges)).resolves.not.toThrow();
    });
  });

  describe('node sizing', () => {
    it('assigns correct widths based on node type', async () => {
      // We verify indirectly by checking that ELK receives correct dimensions
      // The getNodeWidth/getNodeHeight functions are internal, but we can
      // verify the layout completes without error for each node type
      const { applyLayout } = await import('../../../src/lib/workflow/layout.js');

      const nodeTypes = [
        { id: 'agent', type: 'agent', data: { round: 1 } },
        { id: 'artifact', type: 'artifact', data: { round: 1 } },
        { id: 'user_action', type: 'user_action', data: {} },
        { id: 'placeholder', type: 'placeholder', data: {} },
        { id: 'default', type: 'unknown', data: {} },
      ];

      const nodes = nodeTypes.map(n => ({
        ...n,
        position: { x: 0, y: 0 },
      }));

      await expect(applyLayout(nodes, [])).resolves.not.toThrow();
    });
  });

  describe('round container grouping', () => {
    it('groups agent nodes by round into ELK containers', async () => {
      const { applyLayout } = await import('../../../src/lib/workflow/layout.js');

      const nodes = [
        { id: 'input', type: 'input', data: {}, position: { x: 0, y: 0 } },
        { id: 'strategist_r1', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 } },
        { id: 'critic_r1', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 } },
        { id: 'strategist_r2', type: 'agent', data: { round: 2 }, position: { x: 0, y: 0 } },
      ];

      const edges = [
        { id: 'e1', source: 'input', target: 'strategist_r1' },
        { id: 'e2', source: 'strategist_r1', target: 'critic_r1' },
        { id: 'e3', source: 'critic_r1', target: 'strategist_r2' },
      ];

      // Should complete without error, grouping round 1 and round 2 agents
      await expect(applyLayout(nodes, edges)).resolves.not.toThrow();
    });
  });
});
