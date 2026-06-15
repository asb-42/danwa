/**
 * Vitest tests for graphStore.svelte.js (Phase 4.6).
 *
 * Mirrors the inboxStore.test.js pattern:
 * - mock the API module so we don't hit the network
 * - drive the store through its public actions
 * - assert state changes + cache behaviour + LRU eviction
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the API module so the store does not touch the network.
// The mock is hoisted by vi.mock; both the named exports
// (getGlobalGraph, isGraphDisabled) must be controllable from
// each test via vi.mocked().
vi.mock('../../src/lib/api/graph.js', () => ({
  getGlobalGraph: vi.fn(),
  isGraphDisabled: vi.fn(() => false),
}));

import { getGlobalGraph, isGraphDisabled } from '../../src/lib/api/graph.js';
import {
  graphStore,
  setActiveTenant,
  setFilter,
  resetFilters,
  loadGlobal,
  invalidate,
  reset,
} from '../../src/lib/stores/graphStore.svelte.js';

const samplePayload = (n = 3) => ({
  nodes: Array.from({ length: n }, (_, i) => ({
    id: `case:${i}`,
    type: 'Case',
    label: `Case ${i}`,
  })),
  edges: [],
  truncated: false,
  total_count: n,
  sampled_count: n,
});

describe('graphStore', () => {
  beforeEach(() => {
    vi.mocked(getGlobalGraph).mockReset();
    vi.mocked(isGraphDisabled).mockReset();
    vi.mocked(isGraphDisabled).mockReturnValue(false);
    reset(); // ensure no leftover state from earlier tests
  });

  afterEach(() => {
    reset();
  });

  it('starts in a clean state after reset()', () => {
    expect(graphStore.activeTenantId).toBeNull();
    expect(graphStore.globalPayload).toBeNull();
    expect(graphStore.loading).toBe(false);
    expect(graphStore.error).toBeNull();
    expect(graphStore.graphDisabled).toBe(false);
    expect(graphStore.nodes).toEqual([]);
    expect(graphStore.edges).toEqual([]);
  });

  it('setActiveTenant sets the tenant without fetching', () => {
    setActiveTenant('tenant-1');
    expect(graphStore.activeTenantId).toBe('tenant-1');
    expect(getGlobalGraph).not.toHaveBeenCalled();
  });

  it('loadGlobal without active tenant returns null and sets error', async () => {
    const result = await loadGlobal();
    expect(result).toBeNull();
    expect(graphStore.error).toBeInstanceOf(Error);
    expect(getGlobalGraph).not.toHaveBeenCalled();
  });

  it('loadGlobal fetches, stores payload, returns it', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue(samplePayload(5));
    const result = await loadGlobal();
    expect(result).not.toBeNull();
    expect(result?.nodes).toHaveLength(5);
    expect(graphStore.globalPayload).toBe(result);
    expect(graphStore.totalCount).toBe(5);
    expect(graphStore.sampledCount).toBe(5);
    expect(graphStore.truncated).toBe(false);
    expect(graphStore.loading).toBe(false);
    expect(getGlobalGraph).toHaveBeenCalledWith('tenant-1', 200);
  });

  it('second loadGlobal with same filters hits the cache', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue(samplePayload(4));
    await loadGlobal();
    await loadGlobal();
    // Only one API call, even though loadGlobal was called twice.
    expect(getGlobalGraph).toHaveBeenCalledTimes(1);
  });

  it('different filters bypass the cache', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue(samplePayload(3));
    await loadGlobal();
    setFilter({ limit: 50 });
    await loadGlobal();
    expect(getGlobalGraph).toHaveBeenCalledTimes(2);
    expect(getGlobalGraph).toHaveBeenNthCalledWith(1, 'tenant-1', 200);
    expect(getGlobalGraph).toHaveBeenNthCalledWith(2, 'tenant-1', 50);
  });

  it('LRU eviction drops the oldest entry after CACHE_MAX', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue(samplePayload(1));
    // 11 distinct filter combinations to overflow CACHE_MAX=10
    for (let i = 0; i < 11; i++) {
      setFilter({ limit: 100 + i });
      await loadGlobal();
    }
    expect(getGlobalGraph).toHaveBeenCalledTimes(11);
    // Re-issuing the first (oldest) combination now misses the
    // cache, so the API gets called a 12th time.
    setFilter({ limit: 100 });
    await loadGlobal();
    expect(getGlobalGraph).toHaveBeenCalledTimes(12);
  });

  it('invalidate(tenant) drops cache for that tenant only', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue(samplePayload(2));
    await loadGlobal();
    expect(getGlobalGraph).toHaveBeenCalledTimes(1);
    // Switch tenant but keep the same filters — different cache key
    setActiveTenant('tenant-2');
    await loadGlobal();
    expect(getGlobalGraph).toHaveBeenCalledTimes(2);
    // Invalidate tenant-1 only
    invalidate('tenant-1');
    setActiveTenant('tenant-1');
    await loadGlobal();
    expect(getGlobalGraph).toHaveBeenCalledTimes(3);
  });

  it('invalidate() with no argument clears the entire cache', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue(samplePayload(2));
    await loadGlobal();
    invalidate();
    await loadGlobal();
    expect(getGlobalGraph).toHaveBeenCalledTimes(2);
  });

  it('isGraphDisabled -> graphDisabled=true, no error set', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(isGraphDisabled).mockReturnValue(true);
    vi.mocked(getGlobalGraph).mockRejectedValue(
      new Error('DANWA_ENABLE_CASE_SPACE_GRAPH is off')
    );
    const result = await loadGlobal();
    expect(result).toBeNull();
    expect(graphStore.graphDisabled).toBe(true);
    expect(graphStore.error).toBeNull();
  });

  it('non-disabled error sets graphStore.error and returns null', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(isGraphDisabled).mockReturnValue(false);
    vi.mocked(getGlobalGraph).mockRejectedValue(new Error('network down'));
    const result = await loadGlobal();
    expect(result).toBeNull();
    expect(graphStore.error).toBeInstanceOf(Error);
    expect(graphStore.error && graphStore.error.message).toBe('network down');
    expect(graphStore.graphDisabled).toBe(false);
  });

  it('resetFilters restores default filter shape', () => {
    setFilter({ limit: 7, status: 'archived' });
    expect(graphStore.filters.limit).toBe(7);
    expect(graphStore.filters.status).toBe('archived');
    resetFilters();
    expect(graphStore.filters.limit).toBe(200);
    expect(graphStore.filters.status).toBeNull();
    expect(graphStore.filters.entityTypes).toEqual([]);
    expect(graphStore.filters.tagIds).toEqual([]);
  });

  it('reset() drops the cache and clears state', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue(samplePayload(2));
    await loadGlobal();
    expect(graphStore.globalPayload).not.toBeNull();
    reset();
    expect(graphStore.activeTenantId).toBeNull();
    expect(graphStore.globalPayload).toBeNull();
    // After reset, the same load should hit the API again.
    setActiveTenant('tenant-1');
    await loadGlobal();
    expect(getGlobalGraph).toHaveBeenCalledTimes(2);
  });

  it('mirrors payload.truncated and counts', async () => {
    setActiveTenant('tenant-1');
    vi.mocked(getGlobalGraph).mockResolvedValue({
      nodes: samplePayload(50).nodes,
      edges: [],
      truncated: true,
      total_count: 312,
      sampled_count: 50,
    });
    await loadGlobal();
    expect(graphStore.truncated).toBe(true);
    expect(graphStore.totalCount).toBe(312);
    expect(graphStore.sampledCount).toBe(50);
  });

  it('concurrent loadGlobal calls dedupe to a single API request', async () => {
    setActiveTenant('tenant-1');
    let resolveFn;
    vi.mocked(getGlobalGraph).mockReturnValue(
      new Promise((res) => { resolveFn = () => res(samplePayload(2)); })
    );
    // Two concurrent calls before the first resolves.
    const p1 = loadGlobal();
    const p2 = loadGlobal();
    resolveFn();
    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1).not.toBeNull();
    expect(r2).not.toBeNull();
    // Both promises resolve to the same payload (deduped).
    expect(r1).toBe(r2);
    expect(getGlobalGraph).toHaveBeenCalledTimes(1);
  });
});
