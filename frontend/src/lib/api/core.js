/**
 * Core API utilities for Danwa backend.
 * Shared request function, auth handling, and error translation.
 */

import { get } from 'svelte/store';
import { i18n } from '../i18n/index.js';
import { activeCase } from '../stores.js';
import { accessToken, refreshToken, setAuth, clearAuth } from '../stores/auth.svelte.js';

export const API_BASE = import.meta.env.VITE_API_URL || '';

export const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept-Language': 'en',
};

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
 * - ``X-Project-Id`` header (same value, for backward compatibility)
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
    ...(caseId ? { 'X-Case-Id': caseId, 'X-Project-Id': caseId } : {}),
    ...options.headers,
  };

  let response = await fetch(url, {
    headers,
    ...options,
  });

  // On 401: attempt token refresh and retry once
  if (response.status === 401 && token) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      const newToken = get(accessToken);
      response = await fetch(url, {
        headers: {
          ...headers,
          Authorization: `Bearer ${newToken}`,
        },
        ...options,
      });
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
