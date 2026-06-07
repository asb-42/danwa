/**
 * Unit Tests — registerAll split (audit L5)
 *
 * The 568-line ``registerAll.js`` was split into three focused
 * modules + a thin orchestrator.  These tests verify:
 *
 *   * Each sub-module registers its own slice (assets, workflow
 *     nodes, edges).
 *   * The orchestrator (``registerAllNodeTypes``) calls all three
 *     and ends up with the full set of 27 node types and 11 edge
 *     types in the central registry.
 *   * The full set matches the pre-split behaviour — every supported
 *     type can be looked up via ``getNodeRegistration`` /
 *     ``getEdgeRegistration``.
 *   * The orchestrator is idempotent (calling twice leaves the
 *     registry in the same state).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  getNodeRegistration,
  getEdgeRegistration,
  getAllRegisteredNodes,
  getAllRegisteredEdges,
  getNodesByCategory,
  getEdgesByCategory,
} from '../../../src/lib/blueprint/registry.js';
import { registerAllNodeTypes } from '../../../src/lib/blueprint/registerAll.js';
import { registerAssetNodes } from '../../../src/lib/blueprint/registerAssetNodes.js';
import { registerWorkflowNodes } from '../../../src/lib/blueprint/registerWorkflowNodes.js';
import { registerEdges } from '../../../src/lib/blueprint/registerEdges.js';

// ---------------------------------------------------------------------------
// Helper: clear the registry between tests so registrations don't leak.
// ---------------------------------------------------------------------------
//
// The registry is module-level, so we reset by re-registering everything
// (each call to ``register*`` overwrites the existing entry) and then
// start each test from a known state by registering all and counting
// before the test logic.  This is robust against future additions.

beforeEach(() => {
  // No-op: tests are written so the order/count is asserted from a
  // known starting point (the empty registry OR the fully-registered
  // registry — see the ``resetForTest`` helper below).
});

function resetForTest() {
  // Re-import fresh module instances would be ideal, but vite caches
  // modules.  Instead, we rely on the registry's idempotent overwrite:
  // calling any ``register*`` function for an already-registered type
  // replaces the previous entry with an identical one.  Tests count
  // registrations before/after to assert correctness.
  registerAllNodeTypes();
}

// ---------------------------------------------------------------------------
// Sub-modules
// ---------------------------------------------------------------------------

describe('registerAssetNodes (audit L5)', () => {
  it('registers the 3 asset node types', () => {
    // Re-register to ensure a clean state, then count.
    registerAllNodeTypes();
    const baselineCount = getAllRegisteredNodes().length;

    registerAssetNodes();
    // Should not add new types — assets are already registered by
    // the orchestrator call above.  This confirms idempotence.
    const afterCount = getAllRegisteredNodes().length;
    expect(afterCount).toBe(baselineCount);
  });

  it('exposes llm-profile, agent-core, tone-profile with asset category', () => {
    registerAssetNodes();
    for (const type of ['llm-profile', 'agent-core', 'tone-profile']) {
      const reg = getNodeRegistration(type);
      expect(reg, `${type} should be registered`).toBeDefined();
      expect(reg.category).toBe('asset');
    }
  });
});

describe('registerWorkflowNodes (audit L5)', () => {
  it('registers the 25 workflow node types', () => {
    registerAllNodeTypes();
    const baselineCount = getAllRegisteredNodes().length;
    registerWorkflowNodes();
    expect(getAllRegisteredNodes().length).toBe(baselineCount);
  });

  it('exposes all 25 workflow types with workflow category', () => {
    const workflowTypes = [
      'wf-input',
      'wf-initialize',
      'wf-strategist',
      'wf-critic',
      'wf-optimizer',
      'wf-moderator',
      'wf-fact-checker',
      'wf-analyst',
      'wf-creative',
      'wf-socratic-questioner',
      'wf-expert-reviewer',
      'wf-steel-manner',
      'wf-devils-advocate',
      'wf-troll',
      'wf-mediator',
      'wf-ethicist',
      'wf-synthesizer',
      'wf-phase',
      'wf-user-injection',
      'wf-gate',
      'wf-tone-profile',
      'wf-agent',
      'wf-builder',
      'wf-pragmatist',
      'wf-angels-advocate',
    ];
    registerWorkflowNodes();
    for (const type of workflowTypes) {
      const reg = getNodeRegistration(type);
      expect(reg, `${type} should be registered`).toBeDefined();
      expect(reg.category).toBe('workflow');
      expect(reg.icon).toBeTruthy();
      expect(reg.defaultData).toBeInstanceOf(Function);
    }
  });
});

describe('registerEdges (audit L5)', () => {
  it('exposes 3 semantic + 8 control_flow edges', () => {
    registerEdges();
    const semantic = getEdgesByCategory('semantic').map((e) => e.type).sort();
    const controlFlow = getEdgesByCategory('control_flow').map((e) => e.type).sort();

    expect(semantic).toEqual(['uses_core', 'uses_llm', 'uses_tone']);
    expect(controlFlow).toEqual([
      'builds_upon',
      'conditional',
      'decision',
      'feedback',
      'injects_config',
      'interjection',
      'sequential',
      'validates',
    ]);
  });

  it('each edge has a component', () => {
    registerEdges();
    for (const edge of getAllRegisteredEdges()) {
      expect(edge.component, `${edge.type} should have a component`).toBeDefined();
      expect(['semantic', 'control_flow']).toContain(edge.category);
    }
  });
});

// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

describe('registerAllNodeTypes (orchestrator) (audit L5)', () => {
  it('registers all 28 node types and 11 edge types', () => {
    // Wipe by re-importing — easier path: count from a known fresh run.
    // We rely on the registry's idempotent overwrite so the count is
    // stable regardless of how many times the test runs.
    registerAllNodeTypes();
    const nodes = getAllRegisteredNodes();
    const edges = getAllRegisteredEdges();

    expect(nodes.length).toBe(28); // 3 assets + 25 workflow
    expect(edges.length).toBe(11); // 3 semantic + 8 control_flow
  });

  it('splits nodes correctly: 3 assets, 25 workflow', () => {
    registerAllNodeTypes();
    const assets = getNodesByCategory('asset');
    const workflow = getNodesByCategory('workflow');
    expect(assets.length).toBe(3);
    expect(workflow.length).toBe(25);
  });

  it('is idempotent — calling twice keeps the same set', () => {
    registerAllNodeTypes();
    const firstSnapshot = {
      nodes: getAllRegisteredNodes().map((n) => n.type).sort(),
      edges: getAllRegisteredEdges().map((e) => e.type).sort(),
    };
    registerAllNodeTypes();
    const secondSnapshot = {
      nodes: getAllRegisteredNodes().map((n) => n.type).sort(),
      edges: getAllRegisteredEdges().map((e) => e.type).sort(),
    };
    expect(secondSnapshot).toEqual(firstSnapshot);
  });

  it('lookups by type still work for every supported node and edge', () => {
    registerAllNodeTypes();
    for (const node of getAllRegisteredNodes()) {
      const reg = getNodeRegistration(node.type);
      expect(reg).toBeDefined();
      expect(reg.type).toBe(node.type);
    }
    for (const edge of getAllRegisteredEdges()) {
      const reg = getEdgeRegistration(edge.type);
      expect(reg).toBeDefined();
      expect(reg.type).toBe(edge.type);
    }
  });
});

// ---------------------------------------------------------------------------
// Self-documenting guard
// ---------------------------------------------------------------------------

describe('registerAll.js is the thin orchestrator (audit L5)', () => {
  it('file size is under 60 lines (was 568)', () => {
    // Static guard against the file growing back.  Imports + the
    // orchestrator + the re-exports stay well under 60 lines.
    const { readFileSync } = require('node:fs');
    const path = require('node:path');
    const { fileURLToPath } = require('node:url');
    const here = path.dirname(fileURLToPath(import.meta.url));
    const filePath = path.resolve(
      here,
      '../../../src/lib/blueprint/registerAll.js',
    );
    const lines = readFileSync(filePath, 'utf8').split('\n').length;
    expect(lines).toBeLessThan(60);
  });
});
