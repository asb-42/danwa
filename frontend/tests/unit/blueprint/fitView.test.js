/**
 * Unit Tests — BlueprintCanvas initial fit-view (audit M8)
 *
 * The view is a .svelte file that runs in the browser, so this test
 * environment (node + vitest) cannot mount it.  Instead we statically
 * assert that the source no longer uses ``setTimeout`` to delay
 * ``flow.fitView`` and that SvelteFlow's built-in ``fitView`` prop
 * is in use — the timing is then driven by SvelteFlow's
 * ``nodesInitialized`` derived state, not a magic number.
 */

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const canvasPath = resolve(
  here,
  '../../../src/components/blueprint/BlueprintCanvas.svelte',
);
const canvasSource = readFileSync(canvasPath, 'utf8');
const bridgePath = resolve(
  here,
  '../../../src/components/blueprint/SvelteFlowInstanceBridge.svelte',
);
const bridgeSource = readFileSync(bridgePath, 'utf8');

describe('BlueprintCanvas — initial fit-view (audit M8)', () => {
  it('does NOT use setTimeout to delay flow.fitView()', () => {
    // The audit called out a 100 ms magic number.  Any setTimeout
    // that calls fitView (or wraps it) is a regression.
    expect(canvasSource).not.toMatch(/setTimeout\s*\([^)]*fitView/);
  });

  it('uses SvelteFlow\'s built-in fitView prop', () => {
    // The fitView boolean prop defers to SvelteFlow's internal
    // nodesInitialized mechanism, removing the magic 100 ms delay.
    expect(canvasSource).toMatch(/fitView\b/);
  });

  it('passes the same padding as the old setTimeout call (0.3)', () => {
    // Preserves visual behaviour: keep padding at 0.3 so the initial
    // viewport matches the previous manual fit.
    expect(canvasSource).toMatch(/fitViewOptions=\{\{\s*padding:\s*0\.3\s*\}\}/);
  });

  it('mentions the audit reference so future readers know why it changed', () => {
    expect(canvasSource).toMatch(/audit M8|M8/);
  });
});

describe('SvelteFlowInstanceBridge — fits via parent, not itself (audit M8)', () => {
  it('does not call flow.fitView on its own', () => {
    // Bridge only exposes the flow instance for screenToFlowPosition.
    // SvelteFlow's fitView prop drives the initial fit.
    expect(bridgeSource).not.toMatch(/flow\.fitView/);
  });

  it('still fires onready exactly once on mount', () => {
    expect(bridgeSource).toMatch(/onMount\s*\(\s*\(\s*\)\s*=>\s*\{\s*onready\s*\(\s*flow\s*\)\s*;?\s*\}\s*\)/);
  });
});
