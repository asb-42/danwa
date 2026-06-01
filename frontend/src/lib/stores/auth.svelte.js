/**
 * Auth stores for JWT-based authentication.
 *
 * Persisted to localStorage so the user stays logged in across page reloads.
 */

import { writable, derived, get } from 'svelte/store';

/** JWT access token (null when logged out) */
export const accessToken = writable(null);

/** JWT refresh token (null when logged out) */
export const refreshToken = writable(null);

/** Current user object (null when logged out) */
export const currentUser = writable(null);

/** Currently active tenant (null when logged out or no tenant selected) */
export const currentTenant = writable(null);

/** Whether the user is authenticated */
export const isAuthenticated = derived(
  [accessToken, currentUser],
  ([$token, $user]) => !!$token && !!$user
);

// ---------------------------------------------------------------------------
// Persistence — restore from localStorage on module load
// ---------------------------------------------------------------------------

if (typeof localStorage !== 'undefined') {
  const storedAccess = localStorage.getItem('danwa.accessToken');
  const storedRefresh = localStorage.getItem('danwa.refreshToken');
  const storedUser = localStorage.getItem('danwa.currentUser');
  const storedTenant = localStorage.getItem('danwa.currentTenant');

  if (storedAccess) accessToken.set(storedAccess);
  if (storedRefresh) refreshToken.set(storedRefresh);
  if (storedUser) {
    try {
      currentUser.set(JSON.parse(storedUser));
    } catch { /* ignore */ }
  }
  if (storedTenant) {
    try {
      currentTenant.set(JSON.parse(storedTenant));
    } catch { /* ignore */ }
  }

  // Persist on change
  accessToken.subscribe((v) => {
    if (v) localStorage.setItem('danwa.accessToken', v);
    else localStorage.removeItem('danwa.accessToken');
  });
  refreshToken.subscribe((v) => {
    if (v) localStorage.setItem('danwa.refreshToken', v);
    else localStorage.removeItem('danwa.refreshToken');
  });
  currentUser.subscribe((v) => {
    if (v) localStorage.setItem('danwa.currentUser', JSON.stringify(v));
    else localStorage.removeItem('danwa.currentUser');
  });
  currentTenant.subscribe((v) => {
    if (v) localStorage.setItem('danwa.currentTenant', JSON.stringify(v));
    else localStorage.removeItem('danwa.currentTenant');
  });
}

// ---------------------------------------------------------------------------
// Auth actions
// ---------------------------------------------------------------------------

/**
 * Store tokens and user after successful login/refresh.
 */
export function setAuth(accessTokenVal, refreshTokenVal, userVal) {
  accessToken.set(accessTokenVal);
  refreshToken.set(refreshTokenVal);
  currentUser.set(userVal);
}

/**
 * Clear all auth state (logout).
 */
export function clearAuth() {
  accessToken.set(null);
  refreshToken.set(null);
  currentUser.set(null);
  currentTenant.set(null);
}
