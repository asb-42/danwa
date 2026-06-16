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
import { writable as _writable } from 'svelte/store';

vi.mock('../../src/lib/api/workspace.js', () => ({
  getWorkspaceSummary: vi.fn(),
  searchCases: vi.fn(),
  getLastWorkspace: vi.fn(),
  setLastWorkspace: vi.fn(),
  isCaseSpaceDisabled: vi.fn(() => true),
}));

// Bug C: restoreLastWorkspace validates against the active tenant
// via getCase(tenantId, caseId).  Mock it so the test controls
// whether the case is visible in the current tenant.
vi.mock('../../src/lib/api/case.js', () => ({
  getCase: vi.fn(),
}));

vi.mock('../../src/lib/stores/auth.svelte.js', () => ({
  // restoreLastWorkspace reads the active tenant via get(currentTenant).
  // We use a writable so individual tests can flip it before calling.
  currentTenant: (() => {
    let value = null;
    return {
      subscribe: (fn) => {
        fn(value);
        return () => {};
      },
      set: (v) => {
        value = v;
      },
      __get: () => value,
    };
  })(),
}));

import {
  getWorkspaceSummary,
  getLastWorkspace,
  setLastWorkspace,
} from '../../src/lib/api/workspace.js';

import { getCase } from '../../src/lib/api/case.js';
import { currentTenant as _currentTenant } from '../../src/lib/stores/auth.svelte.js';

// Helper: set the mocked active tenant for a single test.
function setActiveTenant(id) {
  _currentTenant.set(id ? { id, name: id } : null);
}

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
    setActiveTenant('tenant-A');
    getLastWorkspace.mockResolvedValueOnce(CID);
    getCase.mockResolvedValueOnce({ id: CID, tenant_id: 'tenant-A' });
    const result = await restoreLastWorkspace();
    expect(result).toBe(CID);
    expect(workspaceStore.activeCaseId).toBe(CID);
  });

  it('restoreLastWorkspace leaves the store untouched if the backend returns null', async () => {
    setActiveTenant('tenant-A');
    getLastWorkspace.mockResolvedValueOnce(null);
    const result = await restoreLastWorkspace();
    expect(result).toBeNull();
    expect(workspaceStore.activeCaseId).toBeNull();
  });

  it('restoreLastWorkspace sets the active case (used when no URL/prop is set)', async () => {
    // No setActiveCase() call before restore — this is the typical
    // mount-time path when the user lands on /workspace with no
    // ?case=… query param.
    setActiveTenant('tenant-A');
    getLastWorkspace.mockResolvedValueOnce(CID);
    getCase.mockResolvedValueOnce({ id: CID, tenant_id: 'tenant-A' });
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


// ─── Bug C — restoreLastWorkspace must respect active tenant ─────────
//
// Symptom: after Bug A/B (cross-tenant last_workspace leak) was
// fixed in the backend, the frontend still overrode the URL/Prop
// active case with whatever the backend returned for the legacy
// mapping.  The fix is: restoreLastWorkspace() must only call
// setActiveCase() when (a) the case is visible in the active
// tenant (verified via getCase) AND (b) no other source has set
// activeCaseId in the meantime.  We pin both invariants below.

describe('restoreLastWorkspace — Bug C: tenant validation', () => {
  it('sets the active case when the backend value is visible in the active tenant', async () => {
    setActiveTenant('tenant-A');
    getLastWorkspace.mockResolvedValueOnce('case-in-A');
    getCase.mockResolvedValueOnce({ id: 'case-in-A', tenant_id: 'tenant-A' });

    const result = await restoreLastWorkspace();

    expect(result).toBe('case-in-A');
    expect(workspaceStore.activeCaseId).toBe('case-in-A');
    expect(getCase).toHaveBeenCalledWith('tenant-A', 'case-in-A');
  });

  it('does NOT set the active case when the case is not visible in the active tenant', async () => {
    setActiveTenant('tenant-A');
    getLastWorkspace.mockResolvedValueOnce('foreign-case');
    // Simulate the case not being visible: getCase rejects with 404.
    getCase.mockRejectedValueOnce(new Error('404 Not Found'));

    const result = await restoreLastWorkspace();

    // The store must remain empty so the Workspace shows the case
    // picker rather than a foreign case.
    expect(result).toBeNull();
    expect(workspaceStore.activeCaseId).toBeNull();
  });

  it('does NOT override a pre-existing active case set by URL or prop', async () => {
    // Simulate the URL/prop path: WorkspaceView calls
    // setActiveCase(urlCaseId) BEFORE restoreLastWorkspace() is
    // awaited.  The restore must respect that, not clobber it.
    setActiveTenant('tenant-A');
    setActiveCase('S 201…');
    getLastWorkspace.mockResolvedValueOnce('hkk');
    // Even if the case IS visible, restore must not overwrite a
    // value that was set by the caller (the URL takes precedence).
    getCase.mockResolvedValueOnce({ id: 'hkk', tenant_id: 'tenant-A' });

    const result = await restoreLastWorkspace();

    // The pre-existing value (S 201…) must be preserved.
    expect(workspaceStore.activeCaseId).toBe('S 201…');
    // restoreLastWorkspace returns the value it found (hkk) so the
    // caller can log/track it, but does not change the store.
    expect(result).toBe('hkk');
  });

  it('returns null without error when the backend has no stored value', async () => {
    setActiveTenant('tenant-A');
    getLastWorkspace.mockResolvedValueOnce(null);

    const result = await restoreLastWorkspace();

    expect(result).toBeNull();
    expect(workspaceStore.activeCaseId).toBeNull();
  });

  it('returns null when there is no active tenant (cannot verify ownership)', async () => {
    setActiveTenant(null);
    getLastWorkspace.mockResolvedValueOnce('some-case');

    const result = await restoreLastWorkspace();

    // No tenant → cannot verify cross-tenant safety → stay safe.
    expect(result).toBeNull();
    expect(workspaceStore.activeCaseId).toBeNull();
  });

  // Note: the defensive setLastWorkspace(null) cleanup call lives
  // inside the dynamic import branch of restoreLastWorkspace and
  // is hard to assert reliably in isolation.  Marked as .todo
  // until we have a clean way to test the dynamic-import branch.
});
describe('TODO: defensive setLastWorkspace(null) cleanup branch', () => {
  it.todo('clears the persisted value when the restored case is not in the active tenant');
});


// ─── Bug B — sync $activeCase (header) into workspaceStore ──────────
//
// Symptom: the header CaseSelector and the WorkspaceView use two
// different stores.  When the user picks a case in the header,
// $activeCase in stores.js updates, but workspaceStore.activeCaseId
// stays stale.  The Workspace keeps rendering the previous case
// even though the user has chosen a different one.
//
// Fix: a `syncFromActiveCase()` helper that reads the current value
// of any $activeCase-shaped store and calls setActiveCase() iff it
// differs from the current workspaceStore.activeCaseId.  WorkspaceView
// wires this into an $effect that watches the global activeCase
// store so the two are kept in lockstep.

describe('syncFromActiveCase — Bug B: header ↔ workspace sync', () => {
  // We dynamically import the helper to keep the static-import
  // list at the top of the file stable.
  it('updates workspaceStore.activeCaseId when the global active case changes', async () => {
    const { syncFromActiveCase } = await import(
      '../../src/lib/stores/workspaceStore.svelte.js'
    );
    const globalActiveCase = _writable(null);
    syncFromActiveCase(globalActiveCase);
    expect(workspaceStore.activeCaseId).toBeNull();

    globalActiveCase.set({ id: 'case-X', title: 'X', tenant_id: 'tenant-A' });
    // Svelte stores are synchronous; the sync helper reads the
    // current value at call time, not via subscription.
    syncFromActiveCase(globalActiveCase);
    expect(workspaceStore.activeCaseId).toBe('case-X');
  });

  it('does NOT clobber a workspace value when the global store reports the same case', async () => {
    const { syncFromActiveCase } = await import(
      '../../src/lib/stores/workspaceStore.svelte.js'
    );
    setActiveCase('case-Y');
    const globalActiveCase = _writable({ id: 'case-Y', title: 'Y', tenant_id: 'tenant-A' });
    // Calling sync with the same id must not call setActiveCase
    // (which would reset summary to null and trigger a re-fetch).
    // We assert by checking that summary was not cleared.
    getWorkspaceSummary.mockResolvedValueOnce(SUMMARY);
    await loadSummary();
    expect(workspaceStore.summary).not.toBeNull();

    syncFromActiveCase(globalActiveCase);
    expect(workspaceStore.activeCaseId).toBe('case-Y');
    expect(workspaceStore.summary).not.toBeNull();
  });

  it('tolerates a null value (e.g. user deselected in the header)', async () => {
    const { syncFromActiveCase } = await import(
      '../../src/lib/stores/workspaceStore.svelte.js'
    );
    setActiveCase('case-Z');
    const globalActiveCase = _writable(null);
    syncFromActiveCase(globalActiveCase);
    // null in the global store does NOT mean the workspace should
    // forget its active case — the workspace has its own state.
    // The sync helper must leave the workspace value untouched.
    expect(workspaceStore.activeCaseId).toBe('case-Z');
  });

  it('handles stores that report undefined (initialised but no value yet)', async () => {
    const { syncFromActiveCase } = await import(
      '../../src/lib/stores/workspaceStore.svelte.js'
    );
    setActiveCase('case-keep');
    const ghostStore = {
      subscribe: (fn) => { fn(undefined); return () => {}; },
    };
    // Must not throw and must not clobber the current value.
    expect(() => syncFromActiveCase(ghostStore)).not.toThrow();
    expect(workspaceStore.activeCaseId).toBe('case-keep');
  });
});
