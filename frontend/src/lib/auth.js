/**
 * Auth API client — login, register, refresh, logout.
 */

import { get } from 'svelte/store';
import { accessToken, refreshToken, currentUser, setAuth, clearAuth } from './stores/auth.svelte.js';

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
    const error = await response.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(error.detail || 'Login failed');
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
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      display_name: displayName,
      password,
      role,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Registration failed' }));
    throw new Error(error.detail || 'Registration failed');
  }

  return response.json();
}

/**
 * Refresh the access token using the refresh token.
 * Delegates to the api.js request wrapper for consistent 401 handling.
 * @returns {Promise<boolean>} True if refresh succeeded
 */
export async function refreshAccessToken() {
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

// NOTE: api.js has its own attemptTokenRefresh() that handles 401 retry.
// This function is used for standalone token refresh (e.g., on page load).

/**
 * Logout — clear all auth state.
 */
export function logout() {
  clearAuth();
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
    const error = await response.json().catch(() => ({ detail: 'Password change failed' }));
    throw new Error(error.detail || 'Password change failed');
  }

  return response.json();
}
