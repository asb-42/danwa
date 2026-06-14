/**
 * Case-Space Inbox store — Svelte 5 runes cache.
 *
 * Holds the Inbox summary for the active tenant plus the current
 * selection state for bulk actions.  Mirrors the design pattern of
 * ``workspaceStore.svelte.js``: module-level singleton, plain
 * object + getter proxy, in-flight promise dedup.
 *
 * Read-only outside: components call ``load()`` to populate and
 * ``select()`` / ``clearSelection()`` to manage the bulk-action
 * selection; UI reacts to the ``$state`` updates.
 *
 * @see plans/2026-06-14_case-space-workspace.md (Phase 2)
 */

import {
  getInbox,
  bulkMove,
  bulkTag,
  bulkArchive,
  isInboxDisabled,
} from '../api/inbox.js';

/**
 * @typedef {import('../api/inbox.js').InboxSummary} InboxSummary
 * @typedef {import('../api/inbox.js').InboxDebateItem} InboxDebateItem
 * @typedef {import('../api/inbox.js').InboxBulkResult} InboxBulkResult
 */

/**
 * @typedef {Object} InboxState
 * @property {string|null}                 activeTenantId
 * @property {InboxSummary|null}           summary
 * @property {boolean}                     loading
 * @property {Error|null}                  error
 * @property {Set<string>}                 selectedIds
 * @property {string}                      activeTab            kind filter, '' = all
 * @property {boolean}                     bulkInFlight
 * @property {InboxBulkResult|null}        lastBulkResult
 * @property {boolean}                     inboxDisabled
 */

/** @type {InboxState} */
const _state = $state({
  activeTenantId: null,
  summary: null,
  loading: false,
  error: null,
  selectedIds: new Set(),
  activeTab: '',
  bulkInFlight: false,
  lastBulkResult: null,
  inboxDisabled: false,
});

/** @type {Map<string, Promise<InboxSummary|null>>} */
const _inflight = new Map();

// ─── Read access ──────────────────────────────────────────────────────

/**
 * Reactive read proxy.
 * @type {InboxState}
 */
export const inboxStore = {
  get activeTenantId() {
    return _state.activeTenantId;
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
  get selectedIds() {
    return _state.selectedIds;
  },
  get activeTab() {
    return _state.activeTab;
  },
  get bulkInFlight() {
    return _state.bulkInFlight;
  },
  get lastBulkResult() {
    return _state.lastBulkResult;
  },
  get inboxDisabled() {
    return _state.inboxDisabled;
  },
  /** Items filtered by the current activeTab; returns all items if tab is ''. */
  get filteredItems() {
    const items = _state.summary?.items ?? [];
    if (!_state.activeTab) return items;
    return items.filter((it) => it.kind === _state.activeTab);
  },
};

// ─── Actions ─────────────────────────────────────────────────────────

/**
 * Load the Inbox for a tenant.  Dedupe: if a request for the same
 * tenant id is already in flight, return the existing promise.
 *
 * @param {string} tenantId
 * @returns {Promise<InboxSummary|null>}
 */
export async function load(tenantId) {
  if (!tenantId) return null;
  if (_inflight.has(tenantId)) {
    return _inflight.get(tenantId);
  }

  _state.activeTenantId = tenantId;
  _state.loading = true;
  _state.error = null;
  const p = (async () => {
    try {
      const summary = await getInbox(tenantId);
      if (_state.activeTenantId === tenantId) {
        _state.summary = summary;
        _state.inboxDisabled = false;
      }
      return summary;
    } catch (err) {
      if (_state.activeTenantId === tenantId) {
        _state.error = err;
        _state.inboxDisabled = isInboxDisabled(err);
      }
      return null;
    } finally {
      if (_state.activeTenantId === tenantId) {
        _state.loading = false;
      }
      _inflight.delete(tenantId);
    }
  })();
  _inflight.set(tenantId, p);
  return p;
}

/**
 * Toggle a single item's selection.  Idempotent.
 *
 * @param {string} id
 */
export function toggleSelected(id) {
  if (_state.selectedIds.has(id)) {
    _state.selectedIds.delete(id);
  } else {
    _state.selectedIds.add(id);
  }
}

/**
 * Select all currently filtered items (or clear if all are already selected).
 */
export function toggleSelectAll() {
  const items = _state.summary?.items ?? [];
  const visibleIds = items
    .filter((it) => !_state.activeTab || it.kind === _state.activeTab)
    .map((it) => it.id);
  const allSelected = visibleIds.every((id) => _state.selectedIds.has(id));
  if (allSelected) {
    for (const id of visibleIds) _state.selectedIds.delete(id);
  } else {
    for (const id of visibleIds) _state.selectedIds.add(id);
  }
}

export function clearSelection() {
  _state.selectedIds.clear();
}

/**
 * Set the active tab (kind filter).  '' means "all kinds".
 * Resets the selection so cross-tab operations don't carry stale ids.
 *
 * @param {string} kind  "recently_completed" | "untagged" | "stale_running" | ''
 */
export function setActiveTab(kind) {
  _state.activeTab = kind;
  _state.selectedIds.clear();
}

// ─── Bulk actions ────────────────────────────────────────────────────

/**
 * Move the currently-selected items to a target case.
 *
 * @param {string} targetCaseId
 * @returns {Promise<InboxBulkResult|null>}
 */
export async function moveSelectedTo(targetCaseId) {
  const ids = [..._state.selectedIds];
  if (ids.length === 0 || !targetCaseId) return null;
  return _runBulk(() => bulkMove(ids, targetCaseId), ids);
}

/**
 * Add the given tag ids to the currently-selected items.
 *
 * @param {string[]} tagIds
 * @returns {Promise<InboxBulkResult|null>}
 */
export async function tagSelected(tagIds) {
  const ids = [..._state.selectedIds];
  if (ids.length === 0) return null;
  return _runBulk(() => bulkTag(ids, tagIds || []), ids);
}

/**
 * Archive the currently-selected items.
 *
 * @returns {Promise<InboxBulkResult|null>}
 */
export async function archiveSelected() {
  const ids = [..._state.selectedIds];
  if (ids.length === 0) return null;
  return _runBulk(() => bulkArchive(ids), ids);
}

async function _runBulk(caller, ids) {
  _state.bulkInFlight = true;
  _state.error = null;
  try {
    const result = await caller();
    _state.lastBulkResult = result;
    // Prune succeeded ids from the selection so the UI hides them
    for (const id of result?.succeeded ?? []) {
      _state.selectedIds.delete(id);
    }
    // Re-fetch the Inbox so the UI shows the post-bulk state
    if (_state.activeTenantId) {
      await load(_state.activeTenantId);
    }
    return result;
  } catch (err) {
    _state.error = err;
    _state.lastBulkResult = { succeeded: [], failed: ids.map((id) => ({ id, reason: String(err?.message ?? err) })) };
    return _state.lastBulkResult;
  } finally {
    _state.bulkInFlight = false;
  }
}

/**
 * Invalidate the cached summary for a tenant (or all).
 *
 * @param {string} [tenantId]
 */
export function invalidate(tenantId) {
  if (tenantId) {
    _inflight.delete(tenantId);
  } else {
    _inflight.clear();
  }
}

/**
 * Reset the entire store.  Used by logout or tenant-switch flows.
 */
export function reset() {
  _inflight.clear();
  _state.activeTenantId = null;
  _state.summary = null;
  _state.error = null;
  _state.loading = false;
  _state.selectedIds.clear();
  _state.activeTab = '';
  _state.bulkInFlight = false;
  _state.lastBulkResult = null;
  _state.inboxDisabled = false;
}
