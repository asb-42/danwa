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
  /**
   * Items filtered by the current activeTab.  Returns all items
   * if tab is '', and always dedupes by id because a single
   * debate can match multiple inbox kinds (e.g. a debate that is
   * both 'untagged' and 'recently_completed' returns twice from
   * the backend, and the {#each (item.id)} block in InboxView
   * would otherwise throw each_key_duplicate).
   *
   * For the merged 'all' view, the kind field is a comma-joined
   * string of the matched kinds (e.g. "untagged, recently_completed")
   * so the row can show multiple badges if needed.
   */
  get filteredItems() {
    const items = _state.summary?.items ?? [];
    const byId = new Map();
    for (const it of items) {
      if (!it || !it.id) continue;
      if (_state.activeTab && it.kind !== _state.activeTab) continue;
      const existing = byId.get(it.id);
      if (existing) {
        // Same id, different kind (only happens for the 'all' view).
        // Merge the kinds into the existing entry.
        if (existing.kind && existing.kind !== it.kind) {
          const set = new Set(existing.kind.split(',').map((s) => s.trim()).filter(Boolean));
          set.add(it.kind);
          existing.kind = Array.from(set).join(', ');
        }
      } else {
        byId.set(it.id, { ...it });
      }
    }
    return Array.from(byId.values());
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
  // Svelte 5 runes do not track mutations on Set/Map reliably;
  // we replace the set so the $derived getters re-run.
  const next = new Set(_state.selectedIds);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  _state.selectedIds = next;
}

/**
 * Select all currently filtered items (or clear if all are already selected).
 */
export function toggleSelectAll() {
  // Use the (deduplicated) filteredItems getter so we never add the
  // same id twice when a debate matches multiple inbox kinds.
  const visibleIds = inboxStore.filteredItems.map((it) => it.id);
  const allSelected =
    visibleIds.length > 0 &&
    visibleIds.every((id) => _state.selectedIds.has(id));
  // Reassign the set so Svelte 5 runes pick up the change.  A
  // .add() / .clear() in-place would mutate without triggering the
  // $derived getters that read inboxStore.selectedIds.
  const next = new Set(_state.selectedIds);
  if (allSelected) {
    for (const id of visibleIds) next.delete(id);
  } else {
    for (const id of visibleIds) next.add(id);
  }
  _state.selectedIds = next;
}

export function clearSelection() {
  _state.selectedIds = new Set();
}

/**
 * Set the active tab (kind filter).  '' means "all kinds".
 * Resets the selection so cross-tab operations don't carry stale ids.
 *
 * @param {string} kind  "recently_completed" | "untagged" | "stale_running" | ''
 */
export function setActiveTab(kind) {
  _state.activeTab = kind;
  _state.selectedIds = new Set();
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

// ─── Single-item actions (Phase 2.8 visual revision) ─────────────
//
// The Inbox rows now expose inline action buttons ("Open", "Tag",
// "Move", "Archive") so the user can act on one item at a time
// without first having to discover and tick the checkbox.
// These wrappers delegate to the same bulk-* endpoints that the
// multi-select path uses; the backend accepts a single-element
// array identically.  The contract is symmetric so future
// "Select all matching" actions can reuse the same primitives.

/**
 * Move a single inbox item to a different case.
 * @param {string} itemId
 * @param {string} targetCaseId
 * @returns {Promise<InboxBulkResult|null>}
 */
export async function moveItem(itemId, targetCaseId) {
  if (!itemId || !targetCaseId) return null;
  return _runBulk(() => bulkMove([itemId], targetCaseId), [itemId]);
}

/**
 * Add tag ids to a single inbox item.
 * @param {string} itemId
 * @param {string[]} tagIds
 * @returns {Promise<InboxBulkResult|null>}
 */
export async function tagItem(itemId, tagIds) {
  if (!itemId) return null;
  return _runBulk(() => bulkTag([itemId], tagIds || []), [itemId]);
}

/**
 * Archive a single inbox item (sets status=archived + archived_at).
 * @param {string} itemId
 * @returns {Promise<InboxBulkResult|null>}
 */
export async function archiveItem(itemId) {
  if (!itemId) return null;
  return _runBulk(() => bulkArchive([itemId]), [itemId]);
}

async function _runBulk(caller, ids) {
  _state.bulkInFlight = true;
  _state.error = null;
  try {
    const result = await caller();
    _state.lastBulkResult = result;
    // Prune succeeded ids from the selection so the UI hides them
    if (result && Array.isArray(result.succeeded)) {
      const next = new Set(_state.selectedIds);
      for (const id of result.succeeded) next.delete(id);
      _state.selectedIds = next;
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
  _state.selectedIds = new Set();
  _state.activeTab = '';
  _state.bulkInFlight = false;
  _state.lastBulkResult = null;
  _state.inboxDisabled = false;
}
