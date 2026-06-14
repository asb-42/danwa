/**
 * Unit Tests — Phase-snapshots store
 *
 * Tests the in-memory cache for the workflow-observability phase
 * snapshot history (see
 * `plans/phase5-workflow-observability-ux.md`, A2 / P5.2).
 *
 * The store is a plain JS singleton, so the tests can read it
 * directly without mounting Svelte components.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock the workflowExec helpers so the store does not actually touch
// the network during tests.
vi.mock('../../../src/lib/workflowExec.js', () => ({
  getPhaseSnapshots: vi.fn(),
  getPhaseSnapshotDetail: vi.fn(),
}));

import { getPhaseSnapshots, getPhaseSnapshotDetail } from '../../../src/lib/workflowExec.js';
import { phaseSnapshots } from '../../../src/lib/stores/phaseSnapshotsStore.svelte.js';

const SID = 'session-abc';
const NID = 'node-gate-1';

const FAKE_LIST = [
  { node_id: NID, node_type: 'gate', phase: 1, round: 1, state_size: 128, created_at: '2026-06-14T10:00:00Z' },
  { node_id: 'node-moderator', node_type: 'moderator', phase: 2, round: 1, state_size: 256, created_at: '2026-06-14T10:00:01Z' },
];

const FAKE_DETAIL = {
  node_id: NID,
  node_type: 'gate',
  phase: 1,
  round: 1,
  state: { foo: 'bar' },
  created_at: '2026-06-14T10:00:00Z',
};

beforeEach(() => {
  phaseSnapshots.invalidateAll();
  // `resetAllMocks` clears both call history and mock implementations
  // (including queued `mockResolvedValueOnce` values) — important so
  // a test's mock setup is not contaminated by a previous test's
  // `mockResolvedValueOnce` value.
  vi.resetAllMocks();
});

describe('phaseSnapshots — entry/list/isLoading', () => {
  it('returns an empty entry for an unknown session', () => {
    const entry = phaseSnapshots.entry('never-loaded');
    expect(entry.list).toEqual([]);
    expect(entry.detail).toEqual({});
    expect(entry.loading).toBe(false);
    expect(entry.error).toBeNull();
    expect(entry.loadedAt).toBe(0);
  });

  it('returns an empty entry when sessionId is null/undefined', () => {
    expect(phaseSnapshots.list(null)).toEqual([]);
    expect(phaseSnapshots.list(undefined)).toEqual([]);
    expect(phaseSnapshots.isLoading(null)).toBe(false);
    expect(phaseSnapshots.entry(undefined)).toEqual(expect.objectContaining({ list: [] }));
  });
});

describe('phaseSnapshots — load()', () => {
  it('populates the entry on successful fetch', async () => {
    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);

    const result = await phaseSnapshots.load(SID);

    expect(result).toEqual(FAKE_LIST);
    expect(getPhaseSnapshots).toHaveBeenCalledWith(SID);
    expect(phaseSnapshots.list(SID)).toEqual(FAKE_LIST);
    expect(phaseSnapshots.isLoading(SID)).toBe(false);
    expect(phaseSnapshots.entry(SID).loadedAt).toBeGreaterThan(0);
    expect(phaseSnapshots.entry(SID).error).toBeNull();
  });

  it('sets error and returns [] on failure (never throws)', async () => {
    getPhaseSnapshots.mockRejectedValueOnce(new Error('boom'));

    const result = await phaseSnapshots.load(SID);

    expect(result).toEqual([]);
    expect(phaseSnapshots.entry(SID).error.message).toBe('boom');
    expect(phaseSnapshots.isLoading(SID)).toBe(false);
    expect(phaseSnapshots.list(SID)).toEqual([]);
  });

  it('coerces a non-array response to an empty list', async () => {
    getPhaseSnapshots.mockResolvedValueOnce(null);
    const result = await phaseSnapshots.load(SID);
    expect(result).toEqual([]);
    expect(phaseSnapshots.list(SID)).toEqual([]);
  });

  it('dedupes concurrent loads for the same session', async () => {
    let resolve;
    getPhaseSnapshots.mockReturnValueOnce(new Promise((r) => { resolve = r; }));

    // Kick off two concurrent loads.  The store returns the same
    // in-flight promise for both calls — verifying dedup is best done
    // by checking the underlying fetch was only triggered once.
    const p1 = phaseSnapshots.load(SID);
    const p2 = phaseSnapshots.load(SID);
    expect(getPhaseSnapshots).toHaveBeenCalledTimes(1);

    resolve(FAKE_LIST);
    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1).toEqual(FAKE_LIST);
    expect(r2).toEqual(FAKE_LIST);
  });

  it('a second load() after the first resolves re-fetches', async () => {
    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);
    await phaseSnapshots.load(SID);
    getPhaseSnapshots.mockResolvedValueOnce([...FAKE_LIST, { node_id: 'late' }]);
    const result = await phaseSnapshots.load(SID);
    expect(getPhaseSnapshots).toHaveBeenCalledTimes(2);
    expect(result).toHaveLength(3);
  });

  it('no-op (returns []) when sessionId is empty', async () => {
    expect(await phaseSnapshots.load('')).toEqual([]);
    expect(await phaseSnapshots.load(null)).toEqual([]);
    expect(getPhaseSnapshots).not.toHaveBeenCalled();
  });
});

describe('phaseSnapshots — loadDetail()', () => {
  it('returns undefined when the list has not been loaded yet', async () => {
    getPhaseSnapshotDetail.mockResolvedValueOnce(FAKE_DETAIL);
    const result = await phaseSnapshots.loadDetail(SID, NID);
    expect(result).toBeUndefined();
    expect(getPhaseSnapshotDetail).not.toHaveBeenCalled();
  });

  it('fetches and caches the detail after the list is loaded', async () => {
    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);
    await phaseSnapshots.load(SID);
    getPhaseSnapshotDetail.mockResolvedValueOnce(FAKE_DETAIL);

    const first = await phaseSnapshots.loadDetail(SID, NID);
    expect(first).toEqual(FAKE_DETAIL);
    expect(getPhaseSnapshotDetail).toHaveBeenCalledWith(SID, NID);
    expect(phaseSnapshots.detail(SID, NID)).toEqual(FAKE_DETAIL);

    // Second call should hit the cache, not the network.
    const second = await phaseSnapshots.loadDetail(SID, NID);
    expect(second).toEqual(FAKE_DETAIL);
    expect(getPhaseSnapshotDetail).toHaveBeenCalledTimes(1);
  });

  it('returns null when the backend reports 404 and does not cache it', async () => {
    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);
    await phaseSnapshots.load(SID);
    getPhaseSnapshotDetail.mockResolvedValueOnce(null);

    const result = await phaseSnapshots.loadDetail(SID, 'node-missing');
    expect(result).toBeNull();
    expect(phaseSnapshots.detail(SID, 'node-missing')).toBeUndefined();
  });

  it('returns undefined for empty sessionId/nodeId without network', async () => {
    expect(await phaseSnapshots.loadDetail('', NID)).toBeUndefined();
    expect(await phaseSnapshots.loadDetail(SID, '')).toBeUndefined();
    expect(getPhaseSnapshotDetail).not.toHaveBeenCalled();
  });
});

describe('phaseSnapshots — invalidate()', () => {
  it('drops the cached entry; next load re-fetches', async () => {
    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);
    await phaseSnapshots.load(SID);
    expect(phaseSnapshots.list(SID)).toEqual(FAKE_LIST);

    phaseSnapshots.invalidate(SID);
    expect(phaseSnapshots.entry(SID).loadedAt).toBe(0);
    expect(phaseSnapshots.list(SID)).toEqual([]);

    getPhaseSnapshots.mockResolvedValueOnce([]);
    await phaseSnapshots.load(SID);
    expect(getPhaseSnapshots).toHaveBeenCalledTimes(2);
    expect(phaseSnapshots.list(SID)).toEqual([]);
  });

  it('invalidateAll drops every session', async () => {
    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);
    await phaseSnapshots.load(SID);
    await phaseSnapshots.load('other-sid');

    phaseSnapshots.invalidateAll();
    expect(phaseSnapshots.entry(SID).loadedAt).toBe(0);
    expect(phaseSnapshots.entry('other-sid').loadedAt).toBe(0);
  });
});

describe('phaseSnapshots — subscribe()', () => {
  it('notifies subscribers on load completion', async () => {
    const cb = vi.fn();
    const unsub = phaseSnapshots.subscribe(cb);

    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);
    await phaseSnapshots.load(SID);
    expect(cb).toHaveBeenCalledWith(SID);

    cb.mockClear();
    phaseSnapshots.invalidate(SID);
    expect(cb).toHaveBeenCalledWith(SID);

    unsub();
  });

  it('unsubscribe stops further notifications', async () => {
    const cb = vi.fn();
    const unsub = phaseSnapshots.subscribe(cb);
    unsub();

    getPhaseSnapshots.mockResolvedValueOnce(FAKE_LIST);
    await phaseSnapshots.load(SID);
    expect(cb).not.toHaveBeenCalled();
  });
});
