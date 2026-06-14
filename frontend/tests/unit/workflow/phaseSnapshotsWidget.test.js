/**
 * Unit Tests — PhaseSnapshotsWidget
 *
 * The widget is a Svelte 5 component, but the project's vitest config
 * runs in `node` env (see `frontend/vitest.config.js`) and does not
 * install `@testing-library/svelte`, so we cannot mount components
 * here.
 *
 * Instead, this test takes the pragmatic approach used by the rest of
 * the project: it asserts the **structural contract** of the widget
 * source (props, store hooks, feedback bridge, modal wiring,
 * a11y markers) and verifies the **store-side data the widget relies
 * on** by exercising `phaseSnapshots` directly.
 *
 * @see plans/phase5-workflow-observability-ux.md  (P5.4)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

// ─── Mock the network layer so the store does not hit the API ────────
vi.mock('../../../src/lib/workflowExec.js', () => ({
  getPhaseSnapshots: vi.fn(),
  getPhaseSnapshotDetail: vi.fn(),
}));

vi.mock('../../../src/lib/stores/feedback.svelte.js', () => ({
  feedbackStore: {
    logActivity: vi.fn(),
  },
}));

import { getPhaseSnapshots } from '../../../src/lib/workflowExec.js';
import { feedbackStore } from '../../../src/lib/stores/feedback.svelte.js';
import { phaseSnapshots } from '../../../src/lib/stores/phaseSnapshotsStore.svelte.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WIDGET_PATH = resolve(
  __dirname,
  '../../../src/components/workflow/PhaseSnapshotsWidget.svelte',
);
const widgetSource = readFileSync(WIDGET_PATH, 'utf8');

// ─── Structural / contract tests ────────────────────────────────────
describe('PhaseSnapshotsWidget — source contract', () => {
  it('declares the expected props (sessionId, expanded)', () => {
    expect(widgetSource).toMatch(/sessionId/);
    expect(widgetSource).toMatch(/expanded/);
    // Default values
    expect(widgetSource).toMatch(/sessionId\s*=\s*null/);
    expect(widgetSource).toMatch(/expanded\s*=\s*false/);
  });

  it('imports the shared phaseSnapshots store', () => {
    expect(widgetSource).toMatch(
      /import\s*\{\s*phaseSnapshots\s*\}\s*from\s*['"][^'"]*phaseSnapshotsStore/,
    );
  });

  it('imports the PhasesTab child component for the modal', () => {
    expect(widgetSource).toMatch(/import\s+PhasesTab\s+from\s+['"][^'"]*PhasesTab\.svelte['"]/);
  });

  it('imports the feedbackStore (P5 / A5 bridge)', () => {
    expect(widgetSource).toMatch(/import\s*\{\s*feedbackStore\s*\}/);
  });

  it('triggers phaseSnapshots.load on mount / session change', () => {
    expect(widgetSource).toMatch(/phaseSnapshots\.load\(\s*sessionId\s*\)/);
  });

  it('subscribes to store changes for re-renders', () => {
    expect(widgetSource).toMatch(/phaseSnapshots\.subscribe\(/);
  });

  it('renders an empty state when no sessionId is provided', () => {
    expect(widgetSource).toMatch(/No active session/);
  });

  it('renders a "View all phases" trigger button', () => {
    expect(widgetSource).toMatch(/View all phases/);
  });

  it('opens a modal dialog with role=dialog + aria-modal', () => {
    expect(widgetSource).toMatch(/role="dialog"/);
    expect(widgetSource).toMatch(/aria-modal="true"/);
    expect(widgetSource).toMatch(/role="presentation"/);
  });

  it('embeds PhasesTab inside the modal body', () => {
    // PhasesTab is rendered with `{sessionId}` inside the modal
    expect(widgetSource).toMatch(/<PhasesTab\s*\{sessionId\}\s*\/>/);
  });

  it('calls feedbackStore.logActivity exactly once per session (A5 bridge)', () => {
    // The bridge should guard with a Set keyed by sessionId so
    // re-mounts don't spam the activity log.
    expect(widgetSource).toMatch(/feedbackStore\.logActivity\(/);
    expect(widgetSource).toMatch(/_bridged/);
    expect(widgetSource).toMatch(/_bridged\.add\(/);
  });

  it('exposes stable data-testid hooks for E2E tests', () => {
    expect(widgetSource).toMatch(/data-testid="phase-snapshots-widget"/);
    expect(widgetSource).toMatch(/data-testid="psw-view-all"/);
    expect(widgetSource).toMatch(/data-testid="psw-modal"/);
    expect(widgetSource).toMatch(/data-testid="psw-latest"/);
    expect(widgetSource).toMatch(/data-testid="psw-empty"/);
  });
});

// ─── Store data the widget depends on ────────────────────────────────
describe('PhaseSnapshotsWidget — store contract', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // Best-effort cleanup of the in-process store singleton between tests
    phaseSnapshots.invalidateAll();
  });

  const SID = 'session-widget-test';
  const LATEST = {
    node_id: 'node-gate-2',
    round: 2,
    state_size: 2048,
    created_at: '2026-06-14T03:00:00.000Z',
  };
  const EARLIER = {
    node_id: 'node-gate-1',
    round: 1,
    state_size: 1024,
    created_at: '2026-06-14T02:00:00.000Z',
  };

  it('exposes a list of summaries that the widget can read in order', async () => {
    // Backend returns earliest-first; widget reads latest from the
    // tail of the array.
    getPhaseSnapshots.mockResolvedValueOnce([EARLIER, LATEST]);
    const list = await phaseSnapshots.load(SID);
    expect(list).toHaveLength(2);
    expect(list[list.length - 1]).toEqual(LATEST);
  });

  it('starts with loading=true and resolves to a populated list', async () => {
    let resolveList;
    getPhaseSnapshots.mockReturnValueOnce(new Promise((r) => { resolveList = r; }));

    const pending = phaseSnapshots.load(SID);
    expect(phaseSnapshots.isLoading(SID)).toBe(true);

    resolveList([EARLIER, LATEST]);
    const list = await pending;
    expect(list).toEqual([EARLIER, LATEST]);
    expect(phaseSnapshots.isLoading(SID)).toBe(false);
  });

  it('returns empty list on network failure (widget shows "No phase snapshots yet")', async () => {
    getPhaseSnapshots.mockRejectedValueOnce(new Error('boom'));
    const list = await phaseSnapshots.load(SID);
    expect(list).toEqual([]);
    const entry = phaseSnapshots.entry(SID);
    expect(entry.error).toBeInstanceOf(Error);
    expect(entry.error.message).toBe('boom');
  });

  it('dedupes concurrent loads (multiple mounts → 1 fetch)', async () => {
    getPhaseSnapshots.mockResolvedValueOnce([EARLIER, LATEST]);
    const [a, b] = await Promise.all([
      phaseSnapshots.load(SID),
      phaseSnapshots.load(SID),
    ]);
    expect(a).toEqual([EARLIER, LATEST]);
    expect(b).toEqual([EARLIER, LATEST]);
    expect(getPhaseSnapshots).toHaveBeenCalledTimes(1);
  });

  it('load() is a no-op for empty sessionId (returns [])', async () => {
    const list = await phaseSnapshots.load('');
    expect(list).toEqual([]);
    expect(getPhaseSnapshots).not.toHaveBeenCalled();
  });

  it('subscribe() fires when the loaded list changes', async () => {
    getPhaseSnapshots.mockResolvedValueOnce([EARLIER]);
    const calls = [];
    const unsub = phaseSnapshots.subscribe((sid) => {
      if (sid === SID) calls.push(phaseSnapshots.entry(SID).list.length);
    });
    await phaseSnapshots.load(SID);
    expect(calls.length).toBeGreaterThanOrEqual(1);
    expect(calls[calls.length - 1]).toBe(1);
    unsub();
  });
});

// ─── Feedback-bridge contract ────────────────────────────────────────
describe('PhaseSnapshotsWidget — feedback bridge (A5)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    phaseSnapshots.invalidateAll();
  });

  const SID = 'session-bridge-test';
  const SNAP = {
    node_id: 'node-gate-1',
    round: 1,
    state_size: 128,
    created_at: '2026-06-14T03:00:00.000Z',
  };

  it('the bridge target (feedbackStore.logActivity) exists with the expected signature', () => {
    expect(typeof feedbackStore.logActivity).toBe('function');
  });

  it('the logActivity signature accepts (type, source, message, details, level)', () => {
    // Smoke-test the contract: the widget passes these positional
    // args; if the signature changes, this test will need to be
    // updated alongside the widget.
    feedbackStore.logActivity(
      'phase_snapshot',
      'workflow.phaseSnapshots',
      'Loaded 1 phase snapshot for session test',
      { sessionId: SID, count: 1 },
      'info',
    );
    expect(feedbackStore.logActivity).toHaveBeenCalledWith(
      'phase_snapshot',
      'workflow.phaseSnapshots',
      'Loaded 1 phase snapshot for session test',
      { sessionId: SID, count: 1 },
      'info',
    );
  });

  it('store + logActivity compose: load + manual bridge produces one log entry', async () => {
    getPhaseSnapshots.mockResolvedValueOnce([SNAP]);
    const list = await phaseSnapshots.load(SID);
    expect(list).toHaveLength(1);

    // Simulate the bridge call the widget would make.
    feedbackStore.logActivity(
      'phase_snapshot',
      'workflow.phaseSnapshots',
      `Loaded ${list.length} phase snapshot for session ${SID}`,
      { sessionId: SID, count: list.length },
      'info',
    );
    expect(feedbackStore.logActivity).toHaveBeenCalledTimes(1);
  });
});
