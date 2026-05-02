/**
 * API client for Debate Engine v2.0 backend.
 * All communication in English (Accept-Language: en).
 */

import { i18n } from './i18n/index.js';

const API_BASE = import.meta.env.VITE_API_URL || '';

const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept-Language': 'en',
};

/**
 * Map of backend error messages to i18n keys.
 */
const ERROR_MAP = {
  'Debate not found': 'error.debateNotFound',
  'Invalid input': 'error.invalidInput',
  'Backend connection lost': 'error.backendDisconnected',
};

/**
 * Translate a backend error message to the current UI locale.
 */
export function translateBackendError(backendMessage) {
  const key = ERROR_MAP[backendMessage] || 'common.error';
  return i18n.t(key);
}

/**
 * Generic fetch wrapper with error handling.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: { ...DEFAULT_HEADERS, ...options.headers },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    const detail = error.detail || `HTTP ${response.status}`;
    throw new Error(translateBackendError(detail));
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function getHealth() {
  return request('/health');
}

// ---------------------------------------------------------------------------
// Debate
// ---------------------------------------------------------------------------

export function createDebate(caseText, options = {}) {
  return request('/api/v1/debate', {
    method: 'POST',
    body: JSON.stringify({
      case: { text: caseText },
      ...options,
    }),
  });
}

export function getDebate(debateId) {
  return request(`/api/v1/debate/${debateId}`);
}

export function startDebate(debateId) {
  return request(`/api/v1/debate/${debateId}/start`, {
    method: 'POST',
  });
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export function getAuditEvents(debateId) {
  return request(`/api/v1/audit/${debateId}`);
}
