/**
 * Settings, config, health, and system API functions.
 */

import { request } from './core.js';

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function getHealth() {
  return request('/health');
}

// ---------------------------------------------------------------------------
// Version (Sprint 17)
// ---------------------------------------------------------------------------

/** Get the application version from the single source of truth. */
export function getVersion() {
  return request('/api/v1/config/version');
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export function getSettings() {
  return request('/api/v1/config/settings');
}

export function updateSettings(settings) {
  return request('/api/v1/config/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

// ---------------------------------------------------------------------------
// Language (Phase 8)
// ---------------------------------------------------------------------------

export function getLanguage() {
  return request('/api/v1/config/language');
}

export function setLanguage(language) {
  return request('/api/v1/config/language', {
    method: 'PUT',
    body: JSON.stringify({ language }),
  });
}

// ---------------------------------------------------------------------------
// Service LLM Config (Sprint 16)
// ---------------------------------------------------------------------------

/** Get current service LLM configuration. */
export function getServiceLLMConfig() {
  return request('/api/v1/config/service-llm');
}

// ---------------------------------------------------------------------------
// System Logs
// ---------------------------------------------------------------------------

export function getBackendLogs(lines = 100, search = null) {
  let url = `/api/v1/system/logs?lines=${lines}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  return request(url);
}
