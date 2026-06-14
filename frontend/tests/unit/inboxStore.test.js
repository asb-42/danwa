/**
 * Unit Tests — Case-Space Inbox store
 *
 * Tests the in-memory cache for the Inbox of the Case-Space UI
 * (see plans/2026-06-14_case-space-workspace.md, Phase 2.6).
 *
 * The store is a Svelte 5 runes singleton, so the tests can read
 * it directly without mounting Svelte components.
 *
 * The API wrapper is mocked to avoid network in tests.  The
 * focus is on the *store behaviour*: dedup, selection, bulk
 * actions, partial-success.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../src/lib/api/inbox.js', () => ({
  getInbox: vi.fn(),
  bulkMove: vi.fn(),
  bulkTag: vi.fn(),
  bulkArchive: vi.fn(),
  isInboxDisabled: vi.fn(() => true),
}));

import {
  getInbox,
  bulkMove,
  bulkTag,
  bulkArchive,
} from '../../src/lib/api/inbox.js';

import {
  inboxStore,
  load,
  toggleSelected,
  toggleSelectAll,
  clearSelection,
  setActiveTab,
  moveSelectedTo,
  tagSelected,
  archiveSelected,
  reset,
} from '../../src/lib/stores/inboxStore.svelte.js';

const TID = 'tenant-x';
const SUMMARY = {
  tenant_id: TID,
  items: [
    { id: 'd-untagged', kind: 'untagged', case_id: 'c1', title: 'No tags', tags: [], message: 'm' },
    { id: 'd-recent', kind: 'recently_completed', case_id: 'c1', title: 'Fresh', tags: ['a'], message: 'm' },
    { id: 'd-stale', kind: 'stale_running', case_id: 'c1', title: 'Stuck', tags: [], message: 'm', age_hours: 48 },
  ],
  counts: { untagged: 1, recently_completed: 1, stale_running: 1 },
  is_all_clear: false,
  generated_at: '2026-06-14T10:00:00Z',
};

beforeEach(() => {
  reset();
  vi.clearAllMocks();
});

// ─── load ─────────────────────────────────────────────────────────────

describe('load', () => {
  it('populates summary on first call', async () => {
    getInbox.mockResolvedValueOnce(SUMMARY);
    await load(TID);
    expect(inboxStore.summary).toEqual(SUMMARY);
    expect(inboxStore.activeTenantId).toBe(TID);
    expect(inboxStore.error).toBeNull();
  });

  it('dedupes concurrent calls for the same tenant', async () => {
    // Two parallel load() calls for the same tenant must result in
    // a single network request.  We assert the side-effect (only one
    // getInbox call) rather than the promise identity, which is
    // brittle under ESM module-state evaluation order.
    let resolveLoad;
    getInbox.mockReturnValueOnce(new Promise((r) => { resolveLoad = r; }));
    const p1 = load(TID);
    const p2 = load(TID);
    expect(getInbox).toHaveBeenCalledTimes(1);
    resolveLoad(SUMMARY);
    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1).toEqual(SUMMARY);
    expect(r2).toEqual(SUMMARY);
  });

  it('sets inboxDisabled when the API throws a 404-shaped error', async () => {
    getInbox.mockRejectedValueOnce(new Error('404 DANWA_ENABLE_CASE_SPACE_INBOX'));
    const result = await load(TID);
    expect(result).toBeNull();
    expect(inboxStore.error).toBeTruthy();
    expect(inboxStore.inboxDisabled).toBe(true);
  });
});

// ─── Selection ────────────────────────────────────────────────────────

describe('selection', () => {
  beforeEach(async () => {
    getInbox.mockResolvedValueOnce(SUMMARY);
    await load(TID);
  });

  it('toggleSelected adds and removes ids idempotently', () => {
    toggleSelected('d-untagged');
    expect(inboxStore.selectedIds.has('d-untagged')).toBe(true);
    toggleSelected('d-untagged');
    expect(inboxStore.selectedIds.has('d-untagged')).toBe(false);
  });

  it('clearSelection empties the set', () => {
    toggleSelected('d-untagged');
    toggleSelected('d-recent');
    expect(inboxStore.selectedIds.size).toBe(2);
    clearSelection();
    expect(inboxStore.selectedIds.size).toBe(0);
  });

  it('toggleSelectAll selects all currently-filtered items', () => {
    setActiveTab('untagged');
    toggleSelectAll();
    expect(inboxStore.selectedIds.has('d-untagged')).toBe(true);
    expect(inboxStore.selectedIds.has('d-recent')).toBe(false);
  });

  it('toggleSelectAll again deselects all (idempotent toggle)', () => {
    setActiveTab('untagged');
    toggleSelectAll();
    toggleSelectAll();
    expect(inboxStore.selectedIds.size).toBe(0);
  });

  it('setActiveTab clears the selection (tab-scoped selection)', () => {
    toggleSelected('d-untagged');
    setActiveTab('recently_completed');
    expect(inboxStore.selectedIds.size).toBe(0);
  });
});

// ─── filteredItems ───────────────────────────────────────────────────

describe('filteredItems', () => {
  beforeEach(async () => {
    getInbox.mockResolvedValueOnce(SUMMARY);
    await load(TID);
  });

  it('returns all items when activeTab is empty', () => {
    expect(inboxStore.filteredItems).toHaveLength(3);
  });

  it('returns only the matching kind when activeTab is set', () => {
    setActiveTab('stale_running');
    const items = inboxStore.filteredItems;
    expect(items).toHaveLength(1);
  });

  it('dedupes by id when the same debate matches multiple kinds', () => {
    // A debate can be both 'untagged' AND 'recently_completed' in the
    // backend payload.  The "all" view must not surface the same id
    // twice, or InboxView's {#each (item.id)} throws
    // each_key_duplicate.
    const overlap = {
      tenant_id: TID,
      items: [
        { id: 'd-dup', kind: 'untagged', case_id: 'c1', title: 'A', tags: [], message: 'm' },
        { id: 'd-dup', kind: 'recently_completed', case_id: 'c1', title: 'A', tags: [], message: 'm' },
        { id: 'd-dup', kind: 'stale_running', case_id: 'c1', title: 'A', tags: [], message: 'm' },
      ],
      counts: {},
      is_all_clear: false,
      generated_at: '2026-06-14T10:00:00Z',
    };
    getInbox.mockResolvedValueOnce(overlap);
    return load(TID).then(() => {
      const items = inboxStore.filteredItems;
      expect(items).toHaveLength(1);
      // Kinds are merged, comma-separated.
      const kinds = items[0].kind.split(',').map((s) => s.trim()).sort();
      expect(kinds).toEqual(['recently_completed', 'stale_running', 'untagged']);
    });
  });

  it('dedupes by id per-tab when a debate matches the active tab twice', () => {
    // Defensive: even with the activeTab filter on, the backend
    // might return the same id twice.  filteredItems should still
    // surface it once.
    const overlap = {
      tenant_id: TID,
      items: [
        { id: 'd-dup', kind: 'untagged', case_id: 'c1', title: 'A', tags: [], message: 'm' },
        { id: 'd-dup', kind: 'untagged', case_id: 'c1', title: 'A', tags: [], message: 'm' },
      ],
      counts: {},
      is_all_clear: false,
      generated_at: '2026-06-14T10:00:00Z',
    };
    getInbox.mockResolvedValueOnce(overlap);
    return load(TID).then(() => {
      setActiveTab('untagged');
      expect(inboxStore.filteredItems).toHaveLength(1);
    });
    expect(items[0].id).toBe('d-stale');
  });
});

// ─── Bulk actions ────────────────────────────────────────────────────

describe('bulk actions', () => {
  beforeEach(async () => {
    getInbox.mockResolvedValueOnce(SUMMARY);
    await load(TID);
  });

  it('moveSelectedTo calls bulkMove with the selected ids and target', async () => {
    bulkMove.mockResolvedValueOnce({ succeeded: ['d-untagged'], failed: [] });
    getInbox.mockResolvedValueOnce(SUMMARY); // post-action re-fetch
    toggleSelected('d-untagged');
    const result = await moveSelectedTo('c-target');
    expect(bulkMove).toHaveBeenCalledWith(['d-untagged'], 'c-target');
    expect(result.succeeded).toEqual(['d-untagged']);
    // Selection pruned
    expect(inboxStore.selectedIds.has('d-untagged')).toBe(false);
  });

  it('tagSelected calls bulkTag with selected ids and tag list', async () => {
    bulkTag.mockResolvedValueOnce({ succeeded: ['d-untagged'], failed: [] });
    getInbox.mockResolvedValueOnce(SUMMARY);
    toggleSelected('d-untagged');
    await tagSelected(['new', 'existing']);
    expect(bulkTag).toHaveBeenCalledWith(['d-untagged'], ['new', 'existing']);
  });

  it('archiveSelected calls bulkArchive with selected ids', async () => {
    bulkArchive.mockResolvedValueOnce({ succeeded: ['d-stale'], failed: [] });
    getInbox.mockResolvedValueOnce(SUMMARY);
    toggleSelected('d-stale');
    await archiveSelected();
    expect(bulkArchive).toHaveBeenCalledWith(['d-stale']);
  });

  it('no-op when nothing is selected', async () => {
    const result = await moveSelectedTo('c-x');
    expect(bulkMove).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it('partial failure: failed ids stay in selection, succeeded are pruned', async () => {
    bulkMove.mockResolvedValueOnce({
      succeeded: ['d-untagged'],
      failed: [{ id: 'd-recent', reason: 'cross_tenant' }],
    });
    getInbox.mockResolvedValueOnce(SUMMARY);
    toggleSelected('d-untagged');
    toggleSelected('d-recent');
    await moveSelectedTo('c-target');
    expect(inboxStore.selectedIds.has('d-untagged')).toBe(false); // pruned
    expect(inboxStore.selectedIds.has('d-recent')).toBe(true);     // kept
    expect(inboxStore.lastBulkResult.failed).toHaveLength(1);
  });

  it('rejects a missing targetCaseId in moveSelectedTo', async () => {
    toggleSelected('d-untagged');
    const result = await moveSelectedTo('');
    expect(bulkMove).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });
});

// ─── reset ───────────────────────────────────────────────────────────

describe('reset', () => {
  it('clears all state', async () => {
    getInbox.mockResolvedValueOnce(SUMMARY);
    await load(TID);
    toggleSelected('d-untagged');
    setActiveTab('untagged');
    reset();
    expect(inboxStore.summary).toBeNull();
    expect(inboxStore.activeTenantId).toBeNull();
    expect(inboxStore.activeTab).toBe('');
    expect(inboxStore.selectedIds.size).toBe(0);
    expect(inboxStore.error).toBeNull();
    expect(inboxStore.inboxDisabled).toBe(false);
  });
});
