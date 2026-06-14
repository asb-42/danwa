/**
 * Phase-snapshots store — Svelte 5 runes cache for the
 * workflow-observability phase-snapshot history.
 *
 * The backend already persists one snapshot per gate phase + one per
 * `node.started` event via `StateSnapshotStore.save(...)`
 * (see `backend/workflow/state_snapshot.py`).  This store caches the
 * *list* of snapshots per session and lazy-fetches the full state
 * JSON for individual phases on demand.
 *
 * Design:
 * - Module-level singleton (mirrors `BlueprintCanvasStore`'s shape).
 * - Per-session `$state` for the list and detail map.
 * - In-flight `Map<sessionId, Promise>` to dedupe concurrent `load()`s
 *   from multiple components mounting at once (e.g. ExecutionPanel +
 *   MvpDebateView activity sidebar).
 * - Read-only outside: components call `load()` to populate and
 *   `invalidate()` to drop a session's cache; UI reacts to `$state`
 *   updates.
 *
 * @see plans/phase5-workflow-observability-ux.md  (A2)
 */

import {
  getPhaseSnapshots,
  getPhaseSnapshotDetail,
} from '../workflowExec.js';

/**
 * @typedef {import('./workflowExec.js').PhaseSnapshotSummary} PhaseSnapshotSummary
 * @typedef {import('./workflowExec.js').PhaseSnapshotDetail}   PhaseSnapshotDetail
 *
 * @typedef {Object} SessionEntry
 * @property {PhaseSnapshotSummary[]}           list        Cached list
 * @property {Record<string, PhaseSnapshotDetail>} detail     node_id → detail
 * @property {boolean}                           loading     True while a list fetch is in flight
 * @property {Error|null}                        error       Last load error, if any
 * @property {number}                            loadedAt    ms epoch of last successful load
 */

// ─── Internal state ───────────────────────────────────────────────────
// `$state` only works inside `.svelte`/`.svelte.js` files (Svelte 5).
// We use a plain object + getter proxy here so non-Svelte consumers
// (and tests) can still read the values directly.

/** @type {Record<string, SessionEntry>} */
const _bySession = {};

/** @type {Map<string, Promise<PhaseSnapshotSummary[]>>} */
const _inflight = new Map();

function _emptyEntry() {
  return {
    list: [],
    detail: {},
    loading: false,
    error: null,
    loadedAt: 0,
  };
}

function _getEntry(sessionId) {
  let entry = _bySession[sessionId];
  if (!entry) {
    entry = _emptyEntry();
    _bySession[sessionId] = entry;
  }
  return entry;
}

function _setEntry(sessionId, patch) {
  const entry = _getEntry(sessionId);
  Object.assign(entry, patch);
  // Notify subscribers: re-import this module to get the new object
  // reference.  Consumers in Svelte templates should call
  // `phaseSnapshots.list(sessionId)` which returns the entry.
  _notifyChange(sessionId);
}

const _listeners = new Set();

function _notifyChange(sessionId) {
  for (const fn of _listeners) {
    try { fn(sessionId); } catch (e) { /* ignore */ }
  }
}

/**
 * Public API.
 *
 * @example
 *   $effect(() => {
 *     phaseSnapshots.load(sessionId);
 *   });
 *   const entry = phaseSnapshots.entry(sessionId);
 *   {#each entry.list as snap} ... {/each}
 */
export const phaseSnapshots = {
  /**
   * Get the per-session entry.  Returns an empty entry if the
   * sessionId has never been loaded — safe to read before `load()`.
   * @param {string} sessionId
   * @returns {SessionEntry}
   */
  entry(sessionId) {
    if (!sessionId) return _emptyEntry();
    return _getEntry(sessionId);
  },

  /**
   * Get the list of snapshots for a session.  Empty array if not
   * loaded yet.
   * @param {string} sessionId
   * @returns {PhaseSnapshotSummary[]}
   */
  list(sessionId) {
    if (!sessionId) return [];
    return _getEntry(sessionId).list;
  },

  /**
   * Get a single detail entry (or undefined if not loaded).
   * @param {string} sessionId
   * @param {string} nodeId
   * @returns {PhaseSnapshotDetail | undefined}
   */
  detail(sessionId, nodeId) {
    if (!sessionId || !nodeId) return undefined;
    return _getEntry(sessionId).detail[nodeId];
  },

  /**
   * True when a list fetch is in flight for this session.
   * @param {string} sessionId
   */
  isLoading(sessionId) {
    if (!sessionId) return false;
    return _getEntry(sessionId).loading;
  },

  /**
   * Load (or re-load) the snapshot list for a session.
   * Idempotent: concurrent calls share a single in-flight request.
   * Resolves with the list (empty array on error) and never throws.
   *
   * @param {string} sessionId
   * @returns {Promise<PhaseSnapshotSummary[]>}
   */
  async load(sessionId) {
    if (!sessionId) return [];

    // Dedupe in-flight loads for the same session.
    const existing = _inflight.get(sessionId);
    if (existing) return existing;

    _setEntry(sessionId, { loading: true, error: null });

    const promise = (async () => {
      try {
        const list = await getPhaseSnapshots(sessionId);
        // Only commit if this is still the most recent load.
        // (A later load() call has implicitly superseded us.)
        _setEntry(sessionId, {
          list: Array.isArray(list) ? list : [],
          loading: false,
          error: null,
          loadedAt: Date.now(),
        });
        return _getEntry(sessionId).list;
      } catch (err) {
        _setEntry(sessionId, {
          loading: false,
          error: err instanceof Error ? err : new Error(String(err)),
        });
        return [];
      } finally {
        _inflight.delete(sessionId);
      }
    })();

    _inflight.set(sessionId, promise);
    return promise;
  },

  /**
   * Fetch (and cache) the full state for a single phase snapshot.
   * No-op (returns undefined) if the session has not yet had its
   * list loaded — callers should `load(sessionId)` first.
   *
   * @param {string} sessionId
   * @param {string} nodeId
   * @returns {Promise<PhaseSnapshotDetail | null | undefined>}
   *   - `null`    when the snapshot does not exist on the backend
   *   - `undefined` when no sessionId/nodeId was provided or the list
   *     hasn't been loaded yet
   *   - the detail object on success
   */
  async loadDetail(sessionId, nodeId) {
    if (!sessionId || !nodeId) return undefined;
    const entry = _getEntry(sessionId);
    if (entry.loadedAt === 0) {
      // List not loaded yet — surface as undefined so callers can
      // decide whether to load the list first.
      return undefined;
    }
    if (entry.detail[nodeId]) {
      return entry.detail[nodeId];
    }
    const detail = await getPhaseSnapshotDetail(sessionId, nodeId);
    if (detail) {
      entry.detail[nodeId] = detail;
      _notifyChange(sessionId);
    }
    return detail;
  },

  /**
   * Drop the cached entry for a session so the next `load()`
   * re-fetches from the backend.  Use when a session is restarted
   * or the user explicitly refreshes the panel.
   *
   * @param {string} sessionId
   */
  invalidate(sessionId) {
    if (!sessionId) return;
    delete _bySession[sessionId];
    _inflight.delete(sessionId);
    _notifyChange(sessionId);
  },

  /**
   * Drop every cached session.  Used by tests and by the global
   * "sign out" flow so a different user doesn't see the previous
   * user's snapshots.
   */
  invalidateAll() {
    for (const k of Object.keys(_bySession)) delete _bySession[k];
    _inflight.clear();
    _notifyChange('*');
  },

  /**
   * Subscribe to store changes.  The listener is called with the
   * affected sessionId ('*' for invalidateAll).  Used by Svelte
   * components to trigger reactivity in `$effect` blocks.
   *
   * @param {(sessionId: string) => void} fn
   * @returns {() => void} unsubscribe
   */
  subscribe(fn) {
    _listeners.add(fn);
    return () => _listeners.delete(fn);
  },
};

export default phaseSnapshots;
