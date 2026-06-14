/**
 * Case-Space Workspace store — Svelte 5 runes cache.
 *
 * Holds the currently active case (or null) and the last-fetched
 * workspace summary, plus a debounced typeahead result list for the
 * Case selector.  Mirrors the design pattern of
 * ``phaseSnapshotsStore.svelte.js``: module-level singleton, plain
 * object + getter proxy, single in-flight promise per case to dedupe
 * concurrent callers.
 *
 * Read-only outside: components call ``setActiveCase(id)``,
 * ``loadSummary()``, ``search(q)`` to populate; UI reacts to the
 * ``$state`` updates.
 *
 * @see plans/2026-06-14_case-space-workspace.md (Phase 1)
 */

import {
  getWorkspaceSummary,
  searchCases,
  isCaseSpaceDisabled,
} from '../api/workspace.js';

/**
 * @typedef {import('../api/workspace.js').WorkspaceSummary} WorkspaceSummary
 * @typedef {import('../api/workspace.js').CaseSearchHit}    CaseSearchHit
 */

/**
 * @typedef {Object} WorkspaceState
 * @property {string|null}              activeCaseId
 * @property {WorkspaceSummary|null}    summary
 * @property {boolean}                  loading
 * @property {Error|null}               error
 * @property {CaseSearchHit[]}          searchResults
 * @property {string}                   searchQuery
 * @property {boolean}                  searchLoading
 * @property {boolean}                  caseSpaceDisabled
 */

/** @type {WorkspaceState} */
const _state = $state({
  activeCaseId: null,
  summary: null,
  loading: false,
  error: null,
  searchResults: [],
  searchQuery: '',
  searchLoading: false,
  caseSpaceDisabled: false,
});

/** @type {Map<string, Promise<WorkspaceSummary|null>>} */
const _inflight = new Map();

/** Debounce handle for typeahead. */
let _searchTimer = null;
const SEARCH_DEBOUNCE_MS = 200;

// ─── Read access ──────────────────────────────────────────────────────

/**
 * Reactive read proxy.  Components do ``$workspaceStore.summary`` etc.
 * @type {WorkspaceState}
 */
export const workspaceStore = {
  get activeCaseId() {
    return _state.activeCaseId;
  },
  get summary() {
    return _state.summary;
  },
  get loading() {
    return _state.loading;
  },
  get error() {
    return _state.error;
  },
  get searchResults() {
    return _state.searchResults;
  },
  get searchQuery() {
    return _state.searchQuery;
  },
  get searchLoading() {
    return _state.searchLoading;
  },
  get caseSpaceDisabled() {
    return _state.caseSpaceDisabled;
  },
};

// ─── Actions ─────────────────────────────────────────────────────────

/**
 * Set the active case id.  Does NOT auto-fetch — call ``loadSummary()``
 * explicitly.  This separation lets the URL-state handler set the id
 * before the router confirms the view should mount.
 *
 * @param {string|null} id
 */
export function setActiveCase(id) {
  _state.activeCaseId = id || null;
  _state.summary = null;
  _state.error = null;
}

/**
 * Load the workspace summary for the active case.  Dedupe: if a
 * request for the same case id is already in flight, return the
 * existing promise.
 *
 * @returns {Promise<WorkspaceSummary|null>}
 */
export async function loadSummary() {
  const caseId = _state.activeCaseId;
  if (!caseId) {
    _state.summary = null;
    return null;
  }
  if (_inflight.has(caseId)) {
    return _inflight.get(caseId);
  }

  _state.loading = true;
  _state.error = null;
  const p = (async () => {
    try {
      const summary = await getWorkspaceSummary(caseId);
      // Only commit if the active case hasn't changed while we waited
      if (_state.activeCaseId === caseId) {
        _state.summary = summary;
        _state.caseSpaceDisabled = false;
      }
      return summary;
    } catch (err) {
      if (_state.activeCaseId === caseId) {
        _state.error = err;
        _state.caseSpaceDisabled = isCaseSpaceDisabled(err);
      }
      return null;
    } finally {
      if (_state.activeCaseId === caseId) {
        _state.loading = false;
      }
      _inflight.delete(caseId);
    }
  })();
  _inflight.set(caseId, p);
  return p;
}

/**
 * Typeahead search.  Debounced by {@link SEARCH_DEBOUNCE_MS}.
 *
 * @param {string} q
 */
export function search(q) {
  _state.searchQuery = q || '';
  if (_searchTimer) {
    clearTimeout(_searchTimer);
    _searchTimer = null;
  }
  if (!_state.searchQuery.trim()) {
    _state.searchResults = [];
    _state.searchLoading = false;
    return;
  }
  _state.searchLoading = true;
  _searchTimer = setTimeout(() => {
    _searchTimer = null;
    void _doSearch(_state.searchQuery);
  }, SEARCH_DEBOUNCE_MS);
}

async function _doSearch(q) {
  try {
    const hits = await searchCases(q, 10);
    // Only commit if the query hasn't moved on while we waited
    if (_state.searchQuery === q) {
      _state.searchResults = hits;
    }
  } finally {
    if (_state.searchQuery === q) {
      _state.searchLoading = false;
    }
  }
}

/**
 * Invalidate the cached summary for a case (or all).  Next
 * ``loadSummary()`` will re-fetch.
 *
 * @param {string} [caseId]
 */
export function invalidate(caseId) {
  if (caseId) {
    _inflight.delete(caseId);
  } else {
    _inflight.clear();
  }
}

/**
 * Persist the current active case to the backend so the user
 * finds it on next login.  Best-effort: errors are logged but do
 * not surface in the UI (the user already sees the case loaded
 * in the workspace).
 */
export async function persistActiveCase() {
  const caseId = _state.activeCaseId;
  try {
    const { setLastWorkspace } = await import('../api/workspace.js');
    await setLastWorkspace(caseId);
  } catch (err) {
    if (import.meta.env?.DEV) {
      console.debug('[workspace] persistActiveCase failed:', err?.message ?? err);
    }
  }
}

/**
 * Restore the last_workspace from the backend and set it as
 * active.  Called by WorkspaceView on mount.
 */
export async function restoreLastWorkspace() {
  try {
    const { getLastWorkspace } = await import('../api/workspace.js');
    const caseId = await getLastWorkspace();
    if (caseId && caseId !== _state.activeCaseId) {
      setActiveCase(caseId);
    }
    return caseId;
  } catch (err) {
    if (import.meta.env?.DEV) {
      console.debug('[workspace] restoreLastWorkspace failed:', err?.message ?? err);
    }
    return null;
  }
}

/**
 * Reset the entire store.  Used by logout or tenant-switch flows.
 */
export function reset() {
  if (_searchTimer) {
    clearTimeout(_searchTimer);
    _searchTimer = null;
  }
  _inflight.clear();
  _state.activeCaseId = null;
  _state.summary = null;
  _state.error = null;
  _state.loading = false;
  _state.searchResults = [];
  _state.searchQuery = '';
  _state.searchLoading = false;
  _state.caseSpaceDisabled = false;
}
