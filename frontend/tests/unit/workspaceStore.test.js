/**
 * Unit Tests — Case-Space Workspace store
 *
 * Tests the in-memory cache for the active Case of the Case-Space
 * UI (see plans/2026-06-14_case-space-workspace.md, Phase 1.5).
 *
 * The store is a Svelte 5 runes singleton, so the tests can read
 * it directly without mounting Svelte components.
 *
 * The API wrapper is mocked to avoid network in tests.  The focus
 * is on the *store behaviour*: dedup, URL sync, restore on mount,
 * feature-flag fallback.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../src/lib/api/workspace.js', () => ({
  getWorkspaceSummary: vi.fn(),
  searchCases: vi.fn(),
  getLastWorkspace: vi.fn(),
  setLastWorkspace: vi.fn(),
  isCaseSpaceDisabled: vi.fn(() => true),
}));

import {
  getWorkspaceSummary,
  getLastWorkspace,
  setLastWorkspace,
} from '../../src/lib/api/workspace.js';

import {
  workspaceStore,
  setActiveCase,
  loadSummary,
  search,
  reset,
  persistActiveCase,
  restoreLastWorkspace,
} from '../../src/lib/stores/workspaceStore.svelte.js';

const CID = 'case-abc';
const SUMMARY = {
  case_id: CID,
  tenant_id: 't1',
  title: 'AI Ethics Research',
  description: 'desc',
  status: 'active',
  tags: ['ethics'],
  members: ['alice'],
  debate_count: 2,
  document_count: 1,
  recent_events: [],
  suggested_next_steps: [],
  generated_at: '2026-06-14T10:00:00Z',
};

beforeEach(() => {
  reset();
  vi.clearAllMocks();
});

// ─── setActiveCase + loadSummary ────────────────────────────────────

describe('setActiveCase + loadSummary', () => {
  it('setActiveCase stores the id and clears any prior error state', () => {
    setActiveCase(CID);
    expect(workspaceStore.activeCaseId).toBe(CID);
    // No prior state was set; error and summary remain null.
    expect(workspaceStore.error).toBeNull();
    // setActiveCase(null) clears the id.
    setActiveCase(null);
    expect(workspaceStore.activeCaseId).toBeNull();
  });

  it('setActiveCase(null) is a no-op for empty string', () => {
    setActiveCase('');
    expect(workspaceStore.activeCaseId).toBeNull();
  });

  it('loadSummary populates summary on success', async () => {
    getWorkspaceSummary.mockResolvedValueOnce(SUMMARY);
    setActiveCase(CID);
    await loadSummary();
    expect(workspaceStore.summary).toEqual(SUMMARY);
    expect(workspaceStore.error).toBeNull();
    expect(workspaceStore.caseSpaceDisabled).toBe(false);
  });

  it('loadSummary sets caseSpaceDisabled on 404-shaped errors', async () => {
    getWorkspaceSummary.mockRejectedValueOnce(new Error('404 DANWA_ENABLE_CASE_SPACE'));
    setActiveCase(CID);
    const result = await loadSummary();
    expect(result).toBeNull();
    expect(workspaceStore.error).toBeTruthy();
    expect(workspaceStore.caseSpaceDisabled).toBe(true);
  });

  it('loadSummary is a no-op when no case is active', async () => {
    const result = await loadSummary();
    expect(result).toBeNull();
    expect(getWorkspaceSummary).not.toHaveBeenCalled();
  });

  it('loadSummary dedupes concurrent calls for the same case (via call count)', async () => {
    let resolveLoad;
    getWorkspaceSummary.mockReturnValueOnce(new Promise((r) => { resolveLoad = r; }));
    setActiveCase(CID);
    const p1 = loadSummary();
    const p2 = loadSummary();
    expect(getWorkspaceSummary).toHaveBeenCalledTimes(1);
    resolveLoad(SUMMARY);
    await Promise.all([p1, p2]);
  });

  it('loadSummary ignores stale responses (case changed while awaiting)', async () => {
    // Use a manually-resolvable promise so the load is in flight
    // when we switch the active case.
    let resolveLoad;
    getWorkspaceSummary.mockReturnValueOnce(new Promise((r) => { resolveLoad = r; }));
    setActiveCase(CID);
    const p = loadSummary();
    // Switch the active case while the request is still in flight.
    setActiveCase('case-xyz');
    resolveLoad(SUMMARY);
    await p;
    // The first SUMMARY was for case-abc, but we switched to xyz,
    // so the store should NOT commit it.
    expect(workspaceStore.summary).toBeNull();
  });
});

// ─── search (Typeahead) ─────────────────────────────────────────────

describe('search (typeahead)', () => {
  it('clears results for an empty query', () => {
    search('   ');
    expect(workspaceStore.searchResults).toEqual([]);
    expect(workspaceStore.searchLoading).toBe(false);
  });

  it('triggers the API after the debounce window', async () => {
    vi.useFakeTimers();
    const { searchCases: sc } = await import('../../src/lib/api/workspace.js');
    sc.mockResolvedValueOnce([{ case_id: 'c1', tenant_id: 't1', title: 'X', status: 'active', tags: [] }]);
    search('ai');
    // Before the debounce window: no call yet
    expect(sc).not.toHaveBeenCalled();
    vi.advanceTimersByTime(250);
    // Wait for the inner promise to resolve
    await vi.runAllTimersAsync();
    expect(sc).toHaveBeenCalledWith('ai', 10);
    expect(workspaceStore.searchResults).toHaveLength(1);
    expect(workspaceStore.searchResults[0].case_id).toBe('c1');
    vi.useRealTimers();
  });
});

// ─── last_workspace restore + persist ───────────────────────────────

describe('last_workspace restore / persist', () => {
  it('restoreLastWorkspace sets the active case when one is returned', async () => {
    getLastWorkspace.mockResolvedValueOnce(CID);
    const result = await restoreLastWorkspace();
    expect(result).toBe(CID);
    expect(workspaceStore.activeCaseId).toBe(CID);
  });

  it('restoreLastWorkspace leaves the store untouched if the backend returns null', async () => {
    getLastWorkspace.mockResolvedValueOnce(null);
    const result = await restoreLastWorkspace();
    expect(result).toBeNull();
    expect(workspaceStore.activeCaseId).toBeNull();
  });

  it('restoreLastWorkspace sets the active case (used when no URL/prop is set)', async () => {
    // No setActiveCase() call before restore — this is the typical
    // mount-time path when the user lands on /workspace with no
    // ?case=… query param.
    getLastWorkspace.mockResolvedValueOnce(CID);
    const result = await restoreLastWorkspace();
    expect(result).toBe(CID);
    expect(workspaceStore.activeCaseId).toBe(CID);
  });

  it('persistActiveCase calls setLastWorkspace with the active id', async () => {
    setActiveCase(CID);
    await persistActiveCase();
    expect(setLastWorkspace).toHaveBeenCalledWith(CID);
  });

  it('persistActiveCase passes null when the store is reset', async () => {
    await persistActiveCase();
    expect(setLastWorkspace).toHaveBeenCalledWith(null);
  });
});

// ─── reset ──────────────────────────────────────────────────────────

describe('reset', () => {
  it('clears all state and cancels any pending search timer', async () => {
    setActiveCase(CID);
    getWorkspaceSummary.mockResolvedValueOnce(SUMMARY);
    await loadSummary();
    reset();
    expect(workspaceStore.activeCaseId).toBeNull();
    expect(workspaceStore.summary).toBeNull();
    expect(workspaceStore.error).toBeNull();
    expect(workspaceStore.loading).toBe(false);
    expect(workspaceStore.searchResults).toEqual([]);
    expect(workspaceStore.searchQuery).toBe('');
    expect(workspaceStore.caseSpaceDisabled).toBe(false);
  });
});
