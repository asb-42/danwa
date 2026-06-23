/**
 * Auth API client — login, register, logout, user/tenant management.
 *
 * Token refresh lives in `api/core.js::attemptTokenRefresh()` which is
 * called automatically on 401 responses by the `request()` wrapper.
 */

import { get } from 'svelte/store';
import { accessToken, setAuth, clearAuth } from './stores/auth.svelte.js';
import { i18n } from './i18n/index.js';
import { request, isBackendReachable } from './api/core.js';

const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Login with email + password.
 * @returns {Promise<object>} The user object
 */
export async function login(email, password) {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: i18n.t('auth.errors.loginFailed') }));
    throw new Error(error.detail || i18n.t('auth.errors.loginFailed'));
  }

  const data = await response.json();
  setAuth(data.access_token, data.refresh_token, data.user);
  return data.user;
}

/**
 * Register a new user.
 * @returns {Promise<object>} The created user object
 */
export async function register(email, displayName, password, role = 'viewer') {
  // Pre-flight: if the backend is unreachable, fail fast with a
  // specific diagnostic instead of masking it as
  // 'Registration failed'. This addresses the user-reported
  // bug where the only feedback was a generic error and no hint
  // that the backend wasn't running.
  const reach = await isBackendReachable({ timeoutMs: 2500 });
  if (!reach.ok) {
    // Reuse the same i18n key as request()'s network-failure
    // branch so the UI can render a single, well-tested error
    // path.
    throw new Error(i18n.t('error.backendDisconnected'));
  }

  // Use request() so 4xx/5xx responses are translated and any
  // remaining network failure is caught and re-thrown as the
  // localized 'Backend connection lost' error.
  return request('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      email,
      display_name: displayName,
      password,
      role,
    }),
  });
}

/**
 * Logout — clear all auth state.
 */
export function logout() {
  clearAuth();
}

/**
 * List all users (admin only).
 * @returns {Promise<Array>}
 */
export async function listUsers() {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/auth/users`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: i18n.t('auth.errors.loadUsersFailed') }));
    throw new Error(error.detail || i18n.t('auth.errors.loadUsersFailed'));
  }
  return response.json();
}

/**
 * Invite a new user (admin only).
 * @returns {Promise<object>}
 */
export async function inviteUser(email, displayName, password, role) {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/auth/users/invite`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ email, display_name: displayName, password, role }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: i18n.t('auth.errors.inviteUserFailed') }));
    throw new Error(error.detail || i18n.t('auth.errors.inviteUserFailed'));
  }
  return response.json();
}

/**
 * Delete a user (admin only).
 */
export async function deleteUser(userId) {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/auth/users/${userId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: i18n.t('auth.errors.deleteUserFailed') }));
    throw new Error(error.detail || i18n.t('auth.errors.deleteUserFailed'));
  }
}

/**
 * List tenants the current user is a member of.
 * @returns {Promise<Array>}
 */
export async function getMyTenants() {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/auth/my-tenants`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: i18n.t('auth.errors.loadTenantsFailed') }));
    throw new Error(error.detail || i18n.t('auth.errors.loadTenantsFailed'));
  }
  return response.json();
}

/**
 * Select a tenant — switches active tenant and returns new JWT pair.
 * @param {string} tenantId
 * @returns {Promise<object>} { access_token, refresh_token, user }
 */
export async function selectTenant(tenantId) {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/auth/select-tenant/${tenantId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: i18n.t('auth.errors.selectTenantFailed') }));
    throw new Error(error.detail || i18n.t('auth.errors.selectTenantFailed'));
  }
  return response.json();
}

/**
 * List all tenants (admin only).
 * @returns {Promise<Array>}
 */
export async function listAllTenants() {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/tenants/`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load tenants' }));
    throw new Error(error.detail || 'Failed to load tenants');
  }
  return response.json();
}

/**
 * Create a new tenant (admin only).
 * @param {{ name: string, plan?: string }} body
 * @returns {Promise<object>}
 */
export async function createTenant(body) {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/tenants/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create tenant' }));
    throw new Error(error.detail || 'Failed to create tenant');
  }
  return response.json();
}

/**
 * Change the current user's password.
 */
export async function changePassword(currentPassword, newPassword) {
  const token = get(accessToken);
  const response = await fetch(`${API_BASE}/api/v1/auth/password`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: i18n.t('auth.errors.passwordChangeFailed') }));
    throw new Error(error.detail || i18n.t('auth.errors.passwordChangeFailed'));
  }

  return response.json();
}
