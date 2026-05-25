/**
 * Unit Tests — Blueprint Canvas Store (multi-phase debate)
 *
 * Tests:
 * - canvasStore.toLayoutJson() parent_id serialization
 * - canvasStore.loadFromLayout() parentId deserialization
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { canvasStore } from '../../../src/lib/blueprint/store.svelte.js';

describe('BluePrint Canvas Store — parentId serialization', () => {
  beforeEach(() => {
    canvasStore.reset();
  });

  describe('toLayoutJson', () => {
    it('includes parent_id when node has parentId', () => {
      canvasStore.addNode({
        id: 'strat-1',
        type: 'wf-strategist',
        position: { x: 50, y: 30 },
        parentId: 'phase-1',
        data: {
          label: 'Strategist',
          blueprint_id: 'bp-1',
          agent_blueprint_id: 'bp-1',
        },
      });

      const json = canvasStore.toLayoutJson();
      const node = json.nodes.find((n) => n.id === 'strat-1');
      expect(node).toBeDefined();
      expect(node.parent_id).toBe('phase-1');
    });

    it('sets parent_id to null when node has no parentId', () => {
      canvasStore.addNode({
        id: 'input-1',
        type: 'wf-input',
        position: { x: 0, y: 0 },
        data: { label: 'Input', blueprint_id: 'input-1' },
      });

      const json = canvasStore.toLayoutJson();
      const node = json.nodes.find((n) => n.id === 'input-1');
      expect(node.parent_id).toBeNull();
    });

    it('serializes multiple nodes with different parents', () => {
      canvasStore.addNode({
        id: 'strat-1', type: 'wf-strategist', position: { x: 10, y: 10 },
        parentId: 'phase-1', data: { label: 'S', blueprint_id: 'bp-1', agent_blueprint_id: 'bp-1' },
      });
      canvasStore.addNode({
        id: 'critic-1', type: 'wf-critic', position: { x: 20, y: 20 },
        parentId: 'phase-1', data: { label: 'C', blueprint_id: 'bp-2', agent_blueprint_id: 'bp-2' },
      });
      canvasStore.addNode({
        id: 'input-1', type: 'wf-input', position: { x: 0, y: 0 },
        data: { label: 'Input', blueprint_id: 'input-1' },
      });

      const json = canvasStore.toLayoutJson();
      const phase1Children = json.nodes.filter((n) => n.parent_id === 'phase-1');
      const noParent = json.nodes.filter((n) => n.parent_id === null);

      expect(phase1Children).toHaveLength(2);
      expect(noParent).toHaveLength(1);
    });
  });

  describe('loadFromLayout', () => {
    it('restores parentId from parent_id in layout JSON', () => {
      const layoutJson = {
        nodes: [
          {
            id: 'phase-1', type: 'wf-phase', x: 0, y: 0,
            label: 'Opening', data: { label: 'Opening', blueprint_id: 'phase-1' },
          },
          {
            id: 'strat-1', type: 'wf-strategist', x: 50, y: 30,
            parent_id: 'phase-1',
            label: 'Strategist',
            agent_blueprint_id: 'bp-1',
            data: { label: 'Strategist', blueprint_id: 'bp-1', agent_blueprint_id: 'bp-1' },
          },
        ],
        edges: [],
      };

      canvasStore.loadFromLayout(layoutJson);
      const strat = canvasStore.nodes.find((n) => n.id === 'strat-1');
      expect(strat).toBeDefined();
      expect(strat.parentId).toBe('phase-1');
    });

    it('sets parentId to null when parent_id is absent', () => {
      const layoutJson = {
        nodes: [
          {
            id: 'input-1', type: 'wf-input', x: 0, y: 0,
            label: 'Input', data: { label: 'Input', blueprint_id: 'input-1' },
          },
        ],
        edges: [],
      };

      canvasStore.loadFromLayout(layoutJson);
      const input = canvasStore.nodes.find((n) => n.id === 'input-1');
      expect(input.parentId).toBeNull();
    });

    it('loads wf-phase node type correctly', () => {
      const layoutJson = {
        nodes: [
          {
            id: 'phase-1', type: 'wf-phase', x: 0, y: 0,
            label: 'Opening', data: { label: 'Opening', config: { roles: ['wf-strategist'] } },
          },
        ],
        edges: [],
      };

      canvasStore.loadFromLayout(layoutJson);
      const phase = canvasStore.nodes.find((n) => n.id === 'phase-1');
      expect(phase).toBeDefined();
      expect(phase.type).toBe('wf-phase');
    });

    it('loads all 8 new agent types correctly', () => {
      const newTypes = [
        'wf-socratic-questioner',
        'wf-expert-reviewer',
        'wf-steel-manner',
        'wf-devils-advocate',
        'wf-troll',
        'wf-mediator',
        'wf-ethicist',
        'wf-synthesizer',
      ];
      const layoutJson = {
        nodes: newTypes.map((t, i) => ({
          id: `node-${i}`,
          type: t,
          x: i * 100, y: 0,
          label: t,
          agent_blueprint_id: `bp-${i}`,
          data: { label: t, agent_blueprint_id: `bp-${i}` },
        })),
        edges: [],
      };

      canvasStore.loadFromLayout(layoutJson);
      newTypes.forEach((t) => {
        const node = canvasStore.nodes.find((n) => n.type === t);
        expect(node).toBeDefined();
      });
    });

    it('restores children with parent_id under a phase', () => {
      const layoutJson = {
        nodes: [
          {
            id: 'phase-1', type: 'wf-phase', x: 0, y: 0,
            label: 'Debate Phase', data: { label: 'Debate Phase' },
          },
          {
            id: 'sq-1', type: 'wf-socratic-questioner', x: 30, y: 20,
            parent_id: 'phase-1',
            label: 'Socratic', agent_blueprint_id: 'bp-sq',
            data: { label: 'Socratic', agent_blueprint_id: 'bp-sq' },
          },
          {
            id: 'eth-1', type: 'wf-ethicist', x: 30, y: 80,
            parent_id: 'phase-1',
            label: 'Ethicist', agent_blueprint_id: 'bp-eth',
            data: { label: 'Ethicist', agent_blueprint_id: 'bp-eth' },
          },
        ],
        edges: [],
      };

      canvasStore.loadFromLayout(layoutJson);
      const children = canvasStore.nodes.filter((n) => n.parentId === 'phase-1');
      expect(children).toHaveLength(2);
    });
  });

  describe('updateNode', () => {
    it('updates position and parentId atomically', () => {
      canvasStore.addNode({
        id: 'strat-1', type: 'wf-strategist',
        position: { x: 0, y: 0 },
        data: { label: 'S', blueprint_id: 'bp-1' },
      });

      canvasStore.updateNode('strat-1', { x: 100, y: 50 }, 'phase-1');
      const node = canvasStore.nodes.find((n) => n.id === 'strat-1');
      expect(node.position).toEqual({ x: 100, y: 50 });
      expect(node.parentId).toBe('phase-1');
    });

    it('clears parentId when set to null', () => {
      canvasStore.addNode({
        id: 'strat-1', type: 'wf-strategist', parentId: 'phase-1',
        position: { x: 10, y: 10 },
        data: { label: 'S', blueprint_id: 'bp-1' },
      });

      canvasStore.updateNode('strat-1', { x: 200, y: 200 }, null);
      const node = canvasStore.nodes.find((n) => n.id === 'strat-1');
      expect(node.parentId).toBeNull();
    });
  });
});
