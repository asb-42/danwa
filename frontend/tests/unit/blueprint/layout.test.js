/**
 * Unit Tests — Blueprint Canvas ELK Layout (multi-phase containers)
 *
 * Tests:
 * - calculateBlueprintLayout with phase containers
 * - Children assigned parentId are placed inside the phase
 * - Top-level nodes and phase nodes coexist
 * - Phase containers have correct layoutOptions
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the ELK service to avoid Web Worker dependency
vi.mock('../../../src/lib/elk-service.js', () => ({
  runLayout: vi.fn(async (graph) => {
    // Simulate ELK returning positions for all nodes
    const nodes = extractAllNodes(graph);
    const result = buildMockResult(nodes);
    return result;
  }),
}));

/**
 * Recursively extract all nodes from the ELK graph.
 */
function extractAllNodes(graph) {
  const nodes = [];
  function walk(node) {
    if (node.id !== 'blueprint-root') {
      nodes.push(node);
    }
    if (node.children) {
      for (const child of node.children) {
        walk(child);
      }
    }
  }
  walk(graph);
  return nodes;
}

/**
 * Build a mock ELK result with positions for each node.
 */
function buildMockResult(nodes, prefix = '') {
  const result = {};
  let index = 0;
  for (const node of nodes) {
    result[node.id] = {
      id: node.id,
      x: index * 150,
      y: 50,
      width: node.width || 200,
      height: node.height || 100,
    };
    if (node.children) {
      const childResults = buildMockResult(node.children, `${prefix}${node.id}/`);
      Object.assign(result, childResults);
    }
    index++;
  }
  // Build nested result
  return buildNested(nodes);
}

function buildNested(nodes) {
  const topLevel = [];
  for (const node of nodes) {
    const entry = {
      id: node.id,
      x: node.x ?? 0,
      y: node.y ?? 0,
      width: node.width ?? 200,
      height: node.height ?? 100,
    };
    if (node.children && node.children.length > 0) {
      entry.children = node.children.map((c) => ({
        id: c.id,
        x: 20,
        y: 20,
        width: c.width ?? 200,
        height: c.height ?? 100,
      }));
    }
    topLevel.push(entry);
  }
  return {
    id: 'blueprint-root',
    x: 0,
    y: 0,
    width: 800,
    height: 600,
    children: topLevel,
  };
}

describe('Blueprint Layout — Phase Containers', () => {
  let calculateBlueprintLayout;

  beforeEach(async () => {
    vi.clearAllMocks();
    // Re-import to get fresh mock state
    const mod = await import('../../../src/lib/blueprint/layout.js');
    calculateBlueprintLayout = mod.calculateBlueprintLayout;
  });

  it('returns positions map for empty nodes', async () => {
    const positions = await calculateBlueprintLayout([], []);
    expect(positions).toBeInstanceOf(Map);
    expect(positions.size).toBe(0);
  });

  it('handles nodes without phases', async () => {
    const nodes = [
      { id: 'input-1', type: 'wf-input', position: { x: 0, y: 0 }, data: {} },
      { id: 'strat-1', type: 'wf-strategist', position: { x: 100, y: 0 }, data: {} },
    ];
    const edges = [{ id: 'e1', source: 'input-1', target: 'strat-1' }];
    const positions = await calculateBlueprintLayout(nodes, edges);
    expect(positions.has('input-1')).toBe(true);
    expect(positions.has('strat-1')).toBe(true);
  });

  it('places child nodes inside phase containers', async () => {
    const nodes = [
      { id: 'phase-1', type: 'wf-phase', position: { x: 0, y: 0 }, data: {} },
      {
        id: 'strat-1', type: 'wf-strategist',
        position: { x: 0, y: 0 },
        parentId: 'phase-1', data: {},
      },
      {
        id: 'critic-1', type: 'wf-critic',
        position: { x: 0, y: 0 },
        parentId: 'phase-1', data: {},
      },
    ];
    const edges = [
      { id: 'e1', source: 'strat-1', target: 'critic-1' },
    ];

    const positions = await calculateBlueprintLayout(nodes, edges);
    expect(positions.has('phase-1')).toBe(true);
    expect(positions.has('strat-1')).toBe(true);
    expect(positions.has('critic-1')).toBe(true);
  });

  it('handles nodes with parentId in data.parentId fallback', async () => {
    const nodes = [
      { id: 'phase-1', type: 'wf-phase', position: { x: 0, y: 0 }, data: {} },
      {
        id: 'strat-1', type: 'wf-strategist',
        position: { x: 0, y: 0 },
        data: { parentId: 'phase-1' },
      },
    ];
    const edges = [];

    const positions = await calculateBlueprintLayout(nodes, edges);
    expect(positions.has('phase-1')).toBe(true);
    expect(positions.has('strat-1')).toBe(true);
  });

  it('supports multiple phases with separate children', async () => {
    const nodes = [
      { id: 'phase-1', type: 'wf-phase', position: { x: 0, y: 0 }, data: {} },
      { id: 'phase-2', type: 'wf-phase', position: { x: 300, y: 0 }, data: {} },
      {
        id: 'strat-1', type: 'wf-strategist',
        position: { x: 0, y: 0 },
        parentId: 'phase-1', data: {},
      },
      {
        id: 'critic-1', type: 'wf-critic',
        position: { x: 0, y: 0 },
        parentId: 'phase-1', data: {},
      },
      {
        id: 'da-1', type: 'wf-devils-advocate',
        position: { x: 0, y: 0 },
        parentId: 'phase-2', data: {},
      },
      {
        id: 'med-1', type: 'wf-mediator',
        position: { x: 0, y: 0 },
        parentId: 'phase-2', data: {},
      },
    ];
    const edges = [
      { id: 'e1', source: 'phase-1', target: 'phase-2' },
    ];

    const positions = await calculateBlueprintLayout(nodes, edges);
    expect(positions.has('phase-1')).toBe(true);
    expect(positions.has('phase-2')).toBe(true);
    expect(positions.has('strat-1')).toBe(true);
    expect(positions.has('critic-1')).toBe(true);
    expect(positions.has('da-1')).toBe(true);
    expect(positions.has('med-1')).toBe(true);
  });

  it('uses INCLUDE_CHILDREN hierarchy handling when phases present', async () => {
    const { runLayout } = await import('../../../src/lib/elk-service.js');

    const nodes = [
      { id: 'phase-1', type: 'wf-phase', position: { x: 0, y: 0 }, data: {} },
      {
        id: 'strat-1', type: 'wf-strategist',
        position: { x: 0, y: 0 },
        parentId: 'phase-1', data: {},
      },
    ];
    const edges = [];

    await calculateBlueprintLayout(nodes, edges);
    const elkGraph = runLayout.mock.calls[0][0];

    // Check that hierarchyHandling is set
    expect(elkGraph.layoutOptions).toHaveProperty('elk.hierarchyHandling', 'INCLUDE_CHILDREN');

    // Check that phase has children
    const phaseElk = elkGraph.children.find((c) => c.id === 'phase-1');
    expect(phaseElk).toBeDefined();
    expect(phaseElk.children).toHaveLength(1);
    expect(phaseElk.children[0].id).toBe('strat-1');
  });

  it('does not use INCLUDE_CHILDREN when no phases present', async () => {
    const { runLayout } = await import('../../../src/lib/elk-service.js');

    const nodes = [
      { id: 'input-1', type: 'wf-input', position: { x: 0, y: 0 }, data: {} },
    ];
    const edges = [];

    await calculateBlueprintLayout(nodes, edges);
    const elkGraph = runLayout.mock.calls[0][0];

    expect(elkGraph.layoutOptions).not.toHaveProperty('elk.hierarchyHandling');
  });

  it('handles new agent types mixed with phases', async () => {
    const newTypes = [
      'wf-socratic-questioner', 'wf-expert-reviewer', 'wf-steel-manner',
      'wf-devils-advocate', 'wf-troll', 'wf-mediator', 'wf-ethicist', 'wf-synthesizer',
    ];

    const nodes = [
      { id: 'phase-1', type: 'wf-phase', position: { x: 0, y: 0 }, data: {} },
      ...newTypes.map((t, i) => ({
        id: `node-${i}`, type: t,
        position: { x: i * 50, y: 0 },
        parentId: 'phase-1', data: {},
      })),
    ];
    const edges = [];

    const positions = await calculateBlueprintLayout(nodes, edges);
    expect(positions.has('phase-1')).toBe(true);
    for (let i = 0; i < newTypes.length; i++) {
      expect(positions.has(`node-${i}`)).toBe(true);
    }
  });
});
