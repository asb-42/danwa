/**
 * Case-Space Graph store — Svelte 5 runes cache (Phase 4.6).
 *
 * Holds the last-fetched global graph payload for the active
 * tenant plus a per-filter LRU cache (max 10 entries) so
 * flipping filters in the BrowseView does not refetch when
 * the user toggles back.  Mirrors the design pattern of
 * ``workspaceStore.svelte.js`` and ``inboxStore.svelte.js``:
 * module-level singleton, plain object + getter proxy, single
 * in-flight promise per cache key to dedupe concurrent callers.
 *
 * Local subgraphs (Inspector tab) are intentionally NOT cached
 * here: they are per-entity, typically only consumed once
 * during the inspector lifetime, and a per-entity cache would
 * grow without bound.  The CytoscapeGraphView component keeps
 * its own in-memory store.
 *
 * @see plans/2026-06-14_case-space-impl-todos.md (Phase 4.6)
 */

import {
  getGlobalGraph,
  isGraphDisabled,
} from '../api/graph.js';

/**
 * @typedef {import('../api/graph.js').GraphPayload} GraphPayload
 * @typedef {import('../api/graph.js').GraphNode}    GraphNode
 * @typedef {import('../api/graph.js').GraphEdge}    GraphEdge
 */

/**
 * @typedef {Object} GraphFilters
 * @property {string[]}   entityTypes
 * @property {string[]}   tagIds
 * @property {string|null} status
 * @property {string|null} dateFrom
 * @property {string|null} dateTo
 * @property {number}     limit
 */

/**
 * @typedef {Object} GraphState
 * @property {string|null}         activeTenantId
 * @property {GraphPayload|null}    globalPayload
 * @property {GraphFilters}         filters
 * @property {boolean}              loading
 * @property {Error|null}           error
 * @property {boolean}              graphDisabled
 * @property {boolean}              truncated     Mirror of payload.truncated
 * @property {number}               totalCount    Mirror of payload.total_count
 * @property {number}               sampledCount  Mirror of payload.sampled_count
 */

/** @type {GraphState} */
const _state = $state({
  activeTenantId: null,
  globalPayload: null,
  filters: {
    entityTypes: [],
    tagIds: [],
    status: null,
    dateFrom: null,
    dateTo: null,
    limit: 200,
  },
  loading: false,
  error: null,
  graphDisabled: false,
  truncated: false,
  totalCount: 0,
  sampledCount: 0,
});

/** LRU cache: key -> { payload, promise, ts }.  Max 10 entries. */
const CACHE_MAX = 10;
/** @type {Map<string, { payload: GraphPayload, ts: number }>} */
const _cache = new Map();

/** In-flight promises, dedupe concurrent calls. */
/** @type {Map<string, Promise<GraphPayload|null>>} */
const _inflight = new Map();

// ─── Read access ──────────────────────────────────────────────────────

/**
 * Reactive read proxy.  Components do ``$graphStore.globalPayload`` etc.
 * @type {GraphState}
 */
export const graphStore = {
  get activeTenantId() { return _state.activeTenantId; },
  get globalPayload()  { return _state.globalPayload; },
  get filters()        { return _state.filters; },
  get loading()        { return _state.loading; },
  get error()          { return _state.error; },
  get graphDisabled()  { return _state.graphDisabled; },
  get truncated()      { return _state.truncated; },
  get totalCount()     { return _state.totalCount; },
  get sampledCount()   { return _state.sampledCount; },

  /** Convenience derived: nodes from the active payload. */
  get nodes() { return _state.globalPayload?.nodes ?? []; },
  /** Convenience derived: edges from the active payload. */
  get edges() { return _state.globalPayload?.edges ?? []; },
};

// ─── Helpers ──────────────────────────────────────────────────────────

/**
 * Build a stable cache key from tenantId + filter hash.
 * Filters are JSON-canonicalised so {a:1,b:2} and {b:2,a:1}
 * produce the same key.
 *
 * @param {string} tenantId
 * @param {GraphFilters} f
 * @returns {string}
 */
function _cacheKey(tenantId, f) {
  const canonical = {
    entityTypes: [...(f.entityTypes ?? [])].sort(),
    tagIds: [...(f.tagIds ?? [])].sort(),
    status: f.status ?? null,
    dateFrom: f.dateFrom ?? null,
    dateTo: f.dateTo ?? null,
    limit: f.limit ?? 200,
  };
  return `${tenantId}::${JSON.stringify(canonical)}`;
}

/**
 * Touch a cache entry to mark it as recently used (LRU).
 * @param {string} key
 */
function _touch(key) {
  if (!_cache.has(key)) return;
  const entry = _cache.get(key);
  _cache.delete(key);
  _cache.set(key, entry);
}

/** Evict the oldest entry if the cache grew past CACHE_MAX. */
function _evictIfNeeded() {
  while (_cache.size > CACHE_MAX) {
    const oldest = _cache.keys().next().value;
    if (!oldest) break;
    _cache.delete(oldest);
  }
}

// ─── Actions ──────────────────────────────────────────────────────────

/**
 * Set the active tenant id.  The next load() call will use
 * this tenant.  Does not clear the cache — cached payloads
 * from the previous tenant are still reusable if the user
 * switches back.
 *
 * @param {string|null} tenantId
 */
export function setActiveTenant(tenantId) {
  _state.activeTenantId = tenantId;
  _state.error = null;
}

/**
 * Update a single filter field.  The change is *not* applied
 * to the active payload until the next load() call; this
 * allows the UI to stage several filter changes in one batch.
 *
 * @param {Partial<GraphFilters>} patch
 */
export function setFilter(patch) {
  if (!patch || typeof patch !== 'object') return;
  Object.assign(_state.filters, patch);
}

/**
 * Reset filters to their default values.
 */
export function resetFilters() {
  _state.filters = {
    entityTypes: [],
    tagIds: [],
    status: null,
    dateFrom: null,
    dateTo: null,
    limit: 200,
  };
}

/**
 * Load the global graph for the active tenant + filters.
 * Caches the result and dedupes concurrent calls.
 *
 * @returns {Promise<GraphPayload|null>} the loaded payload, or null on error
 */
export async function loadGlobal() {
  const tid = _state.activeTenantId;
  if (!tid) {
    _state.error = new Error('loadGlobal: no active tenant');
    return null;
  }
  const key = _cacheKey(tid, _state.filters);

  // Cache hit?
  if (_cache.has(key)) {
    _touch(key);
    const entry = _cache.get(key);
    if (!entry) return null;
    _state.globalPayload = entry.payload;
    _state.truncated = Boolean(entry.payload.truncated);
    _state.totalCount = entry.payload.total_count ?? entry.payload.nodes?.length ?? 0;
    _state.sampledCount = entry.payload.sampled_count ?? entry.payload.nodes?.length ?? 0;
    _state.error = null;
    return entry.payload;
  }

  // In-flight dedup
  if (_inflight.has(key)) {
    return _inflight.get(key) ?? null;
  }

  // Fetch
  _state.loading = true;
  _state.error = null;
  _state.graphDisabled = false;
  const promise = (async () => {
    try {
      const payload = await getGlobalGraph(tid, _state.filters.limit);
      _state.globalPayload = payload;
      _state.truncated = Boolean(payload?.truncated);
      _state.totalCount = payload?.total_count ?? payload?.nodes?.length ?? 0;
      _state.sampledCount = payload?.sampled_count ?? payload?.nodes?.length ?? 0;
      _cache.set(key, { payload, ts: Date.now() });
      _evictIfNeeded();
      return payload;
    } catch (err) {
      if (isGraphDisabled(err)) {
        _state.graphDisabled = true;
      } else {
        _state.error = err;
      }
      return null;
    } finally {
      _state.loading = false;
      _inflight.delete(key);
    }
  })();
  _inflight.set(key, promise);
  return promise;
}

/**
 * Invalidate the cache for a tenant (or all tenants if omitted).
 * Use after a write that may have changed edges (e.g. debate
 * created, tag added).
 *
 * @param {string} [tenantId]  when omitted, all cache entries are dropped
 */
export function invalidate(tenantId) {
  if (!tenantId) {
    _cache.clear();
    return;
  }
  const prefix = `${tenantId}::`;
  for (const key of _cache.keys()) {
    if (key.startsWith(prefix)) _cache.delete(key);
  }
}

/**
 * Reset the entire store.  Used by logout or tenant-switch
 * flows where stale data must not leak between users.
 */
export function reset() {
  _state.activeTenantId = null;
  _state.globalPayload = null;
  _state.error = null;
  _state.loading = false;
  _state.graphDisabled = false;
  _state.truncated = false;
  _state.totalCount = 0;
  _state.sampledCount = 0;
  resetFilters();
  _cache.clear();
  _inflight.clear();
}
