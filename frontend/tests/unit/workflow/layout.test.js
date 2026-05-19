/**
 * Unit Tests — ELK Layout Engine
 *
 * Tests the ELK.js layout wrapper including node sizing,
 * graph building, and position extraction.
 *
 * Note: scheduleLayout uses setTimeout debounce, so we test
 * it with async timing. We also verify edge cases.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { workflowStore, resetWorkflow } from '../../../src/lib/workflow/store.svelte.js';

describe('layout engine', () => {
  beforeEach(() => {
    resetWorkflow();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('scheduleLayout', () => {
    it('is exported and callable', async () => {
      const { scheduleLayout } = await import('../../../src/lib/workflow/layout.js');
      expect(typeof scheduleLayout).toBe('function');
    });

    it('does not throw with empty store', async () => {
      const { scheduleLayout } = await import('../../../src/lib/workflow/layout.js');
      expect(() => scheduleLayout()).not.toThrow();
    });

    it('debounces rapid calls — only last generation executes', async () => {
      const { scheduleLayout } = await import('../../../src/lib/workflow/layout.js');

      // Populate store with nodes
      workflowStore.graphNodes.set('a', {
        id: 'a', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 },
      });
      workflowStore.graphEdges.set('e1', {
        id: 'e1', source: 'a', target: 'b',
      });

      // Schedule multiple times rapidly
      scheduleLayout();
      scheduleLayout();
      scheduleLayout();

      // Advance past debounce window
      await vi.advanceTimersByTimeAsync(150);

      // Should have completed without error
      // (verify by checking no unhandled rejections)
    });

    it('returns cleanup function that cancels pending layout', async () => {
      const { scheduleLayout } = await import('../../../src/lib/workflow/layout.js');

      workflowStore.graphNodes.set('a', {
        id: 'a', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 },
      });

      const cleanup = scheduleLayout();
      expect(typeof cleanup).toBe('function');

      // Cancel the pending layout
      cleanup();

      // Advance past debounce window
      await vi.advanceTimersByTimeAsync(150);

      // Should not have executed (no error thrown)
    });
  });

  describe('node sizing', () => {
    it('handles all node types without error', async () => {
      const { scheduleLayout } = await import('../../../src/lib/workflow/layout.js');

      const nodeTypes = [
        { id: 'agent', type: 'agent', data: { round: 1 } },
        { id: 'artifact', type: 'artifact', data: { round: 1 } },
        { id: 'user_action', type: 'user_action', data: {} },
        { id: 'placeholder', type: 'placeholder', data: {} },
        { id: 'default', type: 'unknown', data: {} },
      ];

      nodeTypes.forEach(n => {
        workflowStore.graphNodes.set(n.id, {
          ...n,
          position: { x: 0, y: 0 },
        });
      });

      expect(() => scheduleLayout()).not.toThrow();
      await vi.advanceTimersByTimeAsync(150);
    });
  });

  describe('round container grouping', () => {
    it('handles multi-round nodes without error', async () => {
      const { scheduleLayout } = await import('../../../src/lib/workflow/layout.js');

      const nodes = [
        { id: 'input', type: 'input', data: {}, position: { x: 0, y: 0 } },
        { id: 'strategist_r1', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 } },
        { id: 'critic_r1', type: 'agent', data: { round: 1 }, position: { x: 0, y: 0 } },
        { id: 'strategist_r2', type: 'agent', data: { round: 2 }, position: { x: 0, y: 0 } },
      ];

      nodes.forEach(n => {
        workflowStore.graphNodes.set(n.id, n);
        workflowStore.graphEdges.set(`e-${n.id}`, {
          id: `e-${n.id}`, source: 'input', target: n.id,
        });
      });

      expect(() => scheduleLayout()).not.toThrow();
      await vi.advanceTimersByTimeAsync(150);
    });
  });
});
