/**
 * Core API utilities for Danwa backend.
 * Shared request function, auth handling, and error translation.
 */

import { get } from 'svelte/store';
import { i18n } from '../i18n/index.js';
import { activeCase } from '../stores.js';
import { currentTenant } from '../stores/auth.svelte.js';
import { accessToken, refreshToken, setAuth, clearAuth } from '../stores/auth.svelte.js';

export const API_BASE = import.meta.env.VITE_API_URL || '';

export const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept-Language': 'en',
};

/**
 * Reachability reasons for isBackendReachable().
 * Kept as a small set so the UI can render a specific action hint
 * ("start the backend", "check the proxy config", "wait & retry").
 */
export const REACHABILITY = Object.freeze({
  REACHABLE: 'reachable',
  CONNECTION_REFUSED: 'connection_refused',
  TIMEOUT: 'timeout',
  NETWORK_ERROR: 'network_error',
  UNHEALTHY: 'unhealthy',
});

/**
 * Probe the backend's /health endpoint with a short timeout.
 * Use this BEFORE expensive calls (registration, login) so the
 * user sees a specific "backend not running" error instead of the
 * generic "Login/Registration failed" mask.
 *
 * @param {{ timeoutMs?: number }} [opts]
 * @returns {Promise<{ok: true} | {ok: false, reason: string, status?: number}>}
 */
export async function isBackendReachable(opts = {}) {
  const timeoutMs = opts.timeoutMs ?? 2500;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    if (response.ok) {
      return { ok: true };
    }
    // Backend responded but reported itself unhealthy (e.g. 503
    // because a downstream dep is down).
    return { ok: false, reason: REACHABILITY.UNHEALTHY, status: response.status };
  } catch (err) {
    if (err && err.name === 'AbortError') {
      return { ok: false, reason: REACHABILITY.TIMEOUT };
    }
    // fetch() throws TypeError on network failure (DNS, refused,
    // offline, CORS preflight abort, etc.). We can't reliably
    // distinguish them in the browser, so collapse to
    // 'connection_refused' (the most common case during dev).
    return { ok: false, reason: REACHABILITY.CONNECTION_REFUSED };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Map of backend error messages to i18n keys.
 */
export const ERROR_MAP = {
  'Debate not found': 'error.debateNotFound',
  'Invalid input': 'error.invalidInput',
  'Backend connection lost': 'error.backendDisconnected',
};

/**
 * Translate a backend error message to the current UI locale.
 */
export function translateBackendError(backendMessage) {
  const key = ERROR_MAP[backendMessage];
  if (key) return i18n.t(key);
  // Return the actual backend message if no translation mapping exists
  return backendMessage || i18n.t('common.error');
}

/**
 * In-flight token-refresh promise. Concurrent 401s share the same refresh
 * so we don't issue a second `/auth/refresh` with the just-issued token
 * (which would fail and incorrectly log the user out).
 * @type {Promise<boolean> | null}
 */
let refreshInFlight = null;

/**
 * Attempt to refresh the access token using the stored refresh token.
 * @returns {Promise<boolean>} True if refresh succeeded
 */
function attemptTokenRefresh() {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = doRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

async function doRefresh() {
  const currentRefreshToken = get(refreshToken);
  if (!currentRefreshToken) return false;

  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: currentRefreshToken }),
    });
    if (!response.ok) {
      clearAuth();
      return false;
    }
    const data = await response.json();
    setAuth(data.access_token, data.refresh_token, data.user);
    return true;
  } catch {
    clearAuth();
    return false;
  }
}

/**
 * Generic fetch wrapper with error handling.
 *
 * Automatically injects:
 * - ``Authorization: Bearer <token>`` from the auth store
 * - ``X-Case-Id`` header from the ``activeCase`` store
 *
 * On 401 responses, attempts a token refresh and retries once.
 */
export async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const caseId = get(activeCase)?.id;
  const token = get(accessToken);

  const headers = {
    ...DEFAULT_HEADERS,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(caseId ? { 'X-Case-Id': caseId } : {}),
    ...(get(currentTenant)?.id ? { 'X-Tenant-Id': get(currentTenant).id } : {}),
    ...options.headers,
  };

  let response;
  try {
    response = await fetch(url, {
      headers,
      ...options,
    });
  } catch (networkErr) {
    // fetch() throws TypeError on connection failure (no response at
    // all). Surface this as the localized 'Backend connection lost'
    // error so the UI can render a specific action hint instead of
    // a generic 'Login failed' / 'Registration failed'.
    if (networkErr && (networkErr.name === 'AbortError' || /aborted/i.test(String(networkErr.message)))) {
      throw new Error(translateBackendError('Backend connection lost'));
    }
    throw new Error(translateBackendError('Backend connection lost'));
  }

  // On 401: attempt token refresh and retry once
  if (response.status === 401 && token) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      const newToken = get(accessToken);
      try {
        response = await fetch(url, {
          headers: {
            ...headers,
            Authorization: `Bearer ${newToken}`,
          },
        ...options,
      });
      } catch (networkErr) {
        throw new Error(translateBackendError('Backend connection lost'));
      }
    } else {
      // Refresh failed — redirect to login
      if (typeof window !== 'undefined') {
        window.location.hash = '#/login';
      }
      throw new Error(i18n.t('auth.sessionExpired') || 'Session expired. Please log in again.');
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    let detail = error.detail || `HTTP ${response.status}`;
    // FastAPI validation errors return detail as an array of objects
    if (Array.isArray(detail)) {
      detail = detail
        .map((e) => {
          if (typeof e === 'string') return e;
          if (e && typeof e === 'object') {
            const loc = Array.isArray(e.loc) ? e.loc.join('.') : '';
            const msg = e.msg || JSON.stringify(e);
            return loc ? `${loc}: ${msg}` : msg;
          }
          return String(e);
        })
        .join('; ');
    } else if (detail && typeof detail === 'object') {
      // Backend may return detail as a dict (e.g. compilation errors)
      const msg = detail.message || detail.msg || '';
      const errors = Array.isArray(detail.errors) ? detail.errors.join('; ') : '';
      detail = msg && errors ? `${msg}: ${errors}` : msg || errors || JSON.stringify(detail);
    }
    throw new Error(translateBackendError(detail));
  }

  return response.json();
}
