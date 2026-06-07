/**
 * Unit Tests — BlueprintCanvasView unsaved-changes guard (audit M7)
 *
 * The view is a .svelte file that runs in the browser, so this test
 * environment (node + vitest) cannot mount it.  Instead we statically
 * assert that the source contains the dirty-check guard + ConfirmDialog
 * pattern that prompts the user before ``loadFromLayout`` discards
 * unsaved edits.
 */

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const viewPath = resolve(here, '../../../src/views/BlueprintCanvasView.svelte');
const viewSource = readFileSync(viewPath, 'utf8');

describe('BlueprintCanvasView — unsaved-changes guard (audit M7)', () => {
  it('declares a pendingLoad state for the ConfirmDialog payload', () => {
    expect(viewSource).toMatch(/pendingLoad\s*=\s*\$state\s*\(\s*null\s*\)/);
  });

  it('imports the ConfirmDialog component', () => {
    expect(viewSource).toMatch(/import\s+ConfirmDialog\s+from\s+['"]\.\.\/components\/ConfirmDialog\.svelte['"]/);
  });

  it('renders a <ConfirmDialog> bound to pendingLoad !== null', () => {
    // The dialog is shown when pendingLoad is set, hidden otherwise.
    const pattern = /<ConfirmDialog[\s\S]*?open=\{pendingLoad\s*!==\s*null\}[\s\S]*?\/>/m;
    expect(viewSource).toMatch(pattern);
  });

  it('provides onConfirm/onCancel handlers for the dialog', () => {
    const dialogBlock = viewSource.match(/<ConfirmDialog[\s\S]*?\/>/m);
    expect(dialogBlock).not.toBeNull();
    expect(dialogBlock[0]).toMatch(/onConfirm=\{confirmPendingLoad\}/);
    expect(dialogBlock[0]).toMatch(/onCancel=\{cancelPendingLoad\}/);
  });

  it('wires the dirty-check guard for all three load callsites', () => {
    // Route-driven load (loadLayout / loadWorkflow) + user-action load
    // (handleLoadLayout, handleInstantiatedWithGuard).  Each must
    // either check isDirty or delegate to a guard wrapper.
    expect(viewSource).toMatch(/loadLayoutWithGuard\s*\(\s*layoutId\s*\)/);
    expect(viewSource).toMatch(/loadWorkflowWithGuard\s*\(\s*routeParams\[1\]\s*\)/);
    expect(viewSource).toMatch(/onSuccess=\{handleInstantiatedWithGuard\}/);
    // handleLoadLayout delegates to loadLayoutWithGuard
    expect(viewSource).toMatch(/loadLayoutWithGuard\s*\(\s*layout\.id\s*\)/);
  });

  it('has a confirmPendingLoad action that runs the queued action', () => {
    expect(viewSource).toMatch(/async\s+function\s+confirmPendingLoad\s*\(\s*\)\s*\{/);
    expect(viewSource).toMatch(/pendingLoad\s*\?\.\s*action/);
  });

  it('mentions the audit reference so future readers know why it exists', () => {
    // The comment must reference audit M7.
    expect(viewSource).toMatch(/audit M7|M7/);
  });
});
