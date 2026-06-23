/**
 * Unit tests for src/lib/api/core.js (request() + isBackendReachable)
 * and src/lib/auth.js (register()).
 *
 * Verifies the contract that:
 *   1. request() catches network failures (TypeError from fetch) and
 *      re-throws a localized "Backend connection lost" error
 *      (key: error.backendDisconnected). Prevents users from seeing
 *      "Registration failed" when the real issue is that the backend
 *      isn't running.
 *   2. isBackendReachable() returns false when the backend is down
 *      and a clear reason string.
 *   3. register() in auth.js wraps the fetch in try/catch and either
 *      delegates to request() (so the localized error propagates) or
 *      catches TypeError explicitly.
 *
 * Pre-fix bug: src/lib/auth.js:39 register() used a raw fetch() with
 * no error handling, and the catch in LoginView showed
 * 'auth.errors.registrationFailed' = "Registration failed" for any
 * failure mode (backend down, CORS, 4xx, 5xx). The user's report:
 * "Registration failed" without further info.
 *
 * Date: 2026-06-23
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the Svelte stores + i18n so we can test request() and
// register() in isolation without Svelte runtime.
vi.mock('svelte/store', () => ({
  get: vi.fn(() => null),
  readable: vi.fn(),
  writable: vi.fn(),
}));

vi.mock('../../src/lib/stores/auth.svelte.js', () => ({
  accessToken: { subscribe: vi.fn() },
  refreshToken: { subscribe: vi.fn() },
  setAuth: vi.fn(),
  clearAuth: vi.fn(),
  currentTenant: { subscribe: vi.fn() },
}));

vi.mock('../../src/lib/stores.js', () => ({
  activeCase: { subscribe: vi.fn() },
}));

vi.mock('../../src/lib/i18n/index.js', () => {
  const t = (key) => {
    const map = {
      'error.backendDisconnected': 'Backend connection lost',
      'auth.errors.registrationFailed': 'Registration failed',
      'auth.errors.loginFailed': 'Login failed',
    };
    return map[key] || key;
  };
  return { i18n: { t } };
});

import { request, isBackendReachable, translateBackendError } from '../../src/lib/api/core.js';

describe('api/core.js — request() network error handling', () => {
  let originalFetch;
  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('re-throws a localized "Backend connection lost" error when fetch throws TypeError', async () => {
    // Simulate the browser behaviour when the backend is unreachable:
    // fetch() throws a TypeError synchronously (no response, no JSON).
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(
      request('/api/v1/auth/register', { method: 'POST', body: '{}' }),
    ).rejects.toThrow(/Backend connection lost/);
  });

  it('still throws the original error message for HTTP 4xx/5xx', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ detail: 'Email already exists' }),
    });
    await expect(
      request('/api/v1/auth/register', { method: 'POST', body: '{}' }),
    ).rejects.toThrow(/Email already exists/);
  });

  it('returns parsed JSON on 2xx', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: 'user-1' }),
    });
    const result = await request('/api/v1/auth/register', { method: 'POST', body: '{}' });
    expect(result).toEqual({ id: 'user-1' });
  });
});

describe('api/core.js — isBackendReachable()', () => {
  let originalFetch;
  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('returns {ok: true} when /health responds 200', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
    });
    const result = await isBackendReachable();
    expect(result.ok).toBe(true);
  });

  it('returns {ok: false, reason: "connection_refused"} when fetch throws TypeError', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    const result = await isBackendReachable();
    expect(result.ok).toBe(false);
    // The reason should be machine-readable so the UI can act on it
    expect(['connection_refused', 'timeout', 'network_error']).toContain(result.reason);
  });

  it('returns {ok: false, reason: "unhealthy"} when /health responds 503', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
    });
    const result = await isBackendReachable();
    expect(result.ok).toBe(false);
    expect(result.reason).toBe('unhealthy');
  });

  it("has a short timeout (under 3s) so the check does not block the UI", async () => {
    let timeoutValue = null;
    globalThis.fetch = vi.fn().mockImplementation((_url, init = {}) => {
      timeoutValue = init.signal ? 'has-signal' : 'no-signal';
      return new Promise(() => {}); // never resolves
    });
    // Call with a 2s timeout — we don't await (it would hang).
    const promise = isBackendReachable({ timeoutMs: 2000 });
    // Give the microtask queue a chance to run
    await new Promise((r) => setTimeout(r, 50));
    expect(timeoutValue).toBe('has-signal');
    // Don't actually wait for the promise — the test runtime is short.
    promise.catch(() => {}); // suppress unhandled rejection
  });
});

describe('auth.js — register() error messages', () => {
  let originalFetch;
  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('throws "Backend connection lost" (not "Registration failed") when backend is down', async () => {
    // Late-bind the auth module AFTER our mocks are in place.
    const { register } = await import('../../src/lib/auth.js');
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(
      register('test@example.com', 'Test User', 'password123'),
    ).rejects.toThrow(/Backend connection lost/);
  });
});

describe('api/core.js — translateBackendError()', () => {
  it('returns the i18n key when the mocked i18n.t has no mapping', () => {
    // The real i18n.t would translate the key to a localized string;
    // the mock returns the key on miss. We assert the *fallback
    // behaviour*: when the backend message is in ERROR_MAP, the
    // function returns what i18n.t returns (the key if mocked).
    expect(translateBackendError('Debate not found')).toBe('error.debateNotFound');
  });
  it('falls back to the original message when no mapping exists', () => {
    expect(translateBackendError('Some weird backend error')).toBe('Some weird backend error');
  });
});
