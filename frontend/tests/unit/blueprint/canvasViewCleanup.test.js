/**
 * Unit Tests — BlueprintCanvasView unmount cleanup (audit M6)
 *
 * The view is a .svelte file that runs in the browser, so this test
 * environment (node + vitest) cannot mount it.  Instead we statically
 * assert that the source contains the Svelte 5 $effect-unmount
 * cleanup pattern that calls ``canvasStore.reset()`` — if anyone
 * removes the cleanup, the race condition returns and the next
 * BlueprintCanvas visit will see stale state.
 */

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const viewPath = resolve(here, '../../../src/views/BlueprintCanvasView.svelte');
const viewSource = readFileSync(viewPath, 'utf8');

describe('BlueprintCanvasView — unmount cleanup (audit M6)', () => {
  it('declares a $effect that returns canvasStore.reset() as cleanup', () => {
    // The cleanup must use Svelte 5's $effect-returning-cleanup syntax.
    // Look for: $effect(() => { return () => canvasStore.reset(); });
    // allowing for whitespace/newlines.
    const pattern = /\$effect\s*\(\s*\(\s*\)\s*=>\s*\{\s*return\s+\(\s*\)\s*=>\s*canvasStore\.reset\s*\(\s*\)\s*;?\s*\}?\s*\)/m;
    expect(viewSource).toMatch(pattern);
  });

  it('resets on unmount, not on first mount', () => {
    // The cleanup function should be returned from the $effect, NOT
    // called eagerly.  This guarantees the reset runs on unmount, not
    // when the view is first rendered.
    const pattern = /return\s+\(\s*\)\s*=>\s*canvasStore\.reset\s*\(\s*\)/;
    expect(viewSource).toMatch(pattern);
  });

  it('mentions the audit reference so future readers know why it exists', () => {
    // Self-documenting: the comment must reference audit M6.
    expect(viewSource).toMatch(/audit M6|M6/);
  });
});
