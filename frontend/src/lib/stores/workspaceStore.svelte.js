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

import { get } from 'svelte/store';

import {
  getWorkspaceSummary,
  searchCases,
  isCaseSpaceDisabled,
} from '../api/workspace.js';
import { getCase } from '../api/case.js';
import { currentTenant } from '../stores/auth.svelte.js';

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
 *
 * 2026-06-16 — tenant-scoped persistence.  The backend now
 * records ``(user, tenant) → case_id`` so a case id never leaks
 * across tenants.  We read the active tenant from the auth store
 * and forward it through the body so the backend writes into the
 * correct mapping row.  If we cannot resolve a tenant we still
 * send the request (the backend falls back to its legacy single-
 * column write so we never lose the user's intent entirely).
 */
export async function persistActiveCase() {
  const caseId = _state.activeCaseId;
  // The active tenant is already part of the request via the
  // X-Tenant-Id header that the core request wrapper injects from
  // the auth store.  No body change needed: the backend route
  // resolves the tenant from the header and writes the per-tenant
  // mapping row.  We still read the tenant for diagnostics below
  // (and as a smoke test that the store has been initialised).
  const tenantId = _readActiveTenantId();
  try {
    const { setLastWorkspace } = await import('../api/workspace.js');
    await setLastWorkspace(caseId);
  } catch (err) {
    if (import.meta.env?.DEV) {
      console.debug(
        '[workspace] persistActiveCase failed (tenant=%s): %s',
        tenantId ?? 'unknown',
        err?.message ?? err,
      );
    }
  }
}

/**
 * Restore the last_workspace from the backend and set it as
 * active.  Called by WorkspaceView on mount.
 *
 * 2026-06-16 — cross-tenant guard.  The backend is now
 * tenant-scoped, so the value it returns already belongs to the
 * active tenant.  As a defence-in-depth measure we still verify
 * that the case is actually visible in the active tenant (via
 * ``GET /api/v1/tenants/{tid}/cases/{cid}``) before committing it
 * to the store; if the backend ever returns a stale cross-tenant
 * id during a transition, the Workspace renders the case picker
 * instead of a foreign case.  Failures of the verification call
 * fall through to "do not restore" — the case picker is the safe
 * default.
 */
export async function restoreLastWorkspace() {
  try {
    const { getLastWorkspace } = await import('../api/workspace.js');
    const caseId = await getLastWorkspace();
    if (!caseId || caseId === _state.activeCaseId) {
      return caseId ?? null;
    }
    const tenantId = _readActiveTenantId();
    if (!tenantId) {
      // No active tenant → cannot verify ownership.  Stay safe
      // and do not restore, so the case picker is shown.
      return null;
    }
    let visible = true;
    try {
      // Tenant-scoped lookup — throws 404 when the case is not
      // visible in this tenant.  getCase is imported statically
      // at the top of this module from api/case.js.
      await getCase(tenantId, caseId);
    } catch (err) {
      // 404 (or any other failure) means: not visible in this
      // tenant.  Refuse to restore.
      if (import.meta.env?.DEV) {
        console.debug(
          '[workspace] restoreLastWorkspace: case %s not visible in tenant %s — not restoring',
          caseId, tenantId,
        );
      }
      visible = false;
    }
    if (visible) {
      setActiveCase(caseId);
    } else {
      // Defensive: clear the persisted value so subsequent
      // mounts do not keep retrying a known-bad mapping.  This
      // also nudges the backend toward the per-tenant mapping.
      try {
        const { setLastWorkspace } = await import('../api/workspace.js');
        await setLastWorkspace(null);
      } catch {
        // best-effort
      }
    }
    return visible ? caseId : null;
  } catch (err) {
    if (import.meta.env?.DEV) {
      console.debug('[workspace] restoreLastWorkspace failed:', err?.message ?? err);
    }
    return null;
  }
}

/**
 * Read the active tenant id from the auth store.  Returns null
 * when the user is not logged in or the store has not been
 * populated yet.  Used to scope last-workspace persistence and
 * restoration to the active tenant (2026-06-16 cross-tenant fix).
 */
function _readActiveTenantId() {
  try {
    const v = get(currentTenant);
    return v?.id ?? null;
  } catch {
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
