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
  const key = ERROR_MAP[backendMessage];
  if (key) return i18n.t(key);
  // Return the actual backend message if no translation mapping exists
  return backendMessage || i18n.t('common.error');
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

// ---------------------------------------------------------------------------
// Profiles (Sprint 3)
// ---------------------------------------------------------------------------

export function getLLMProfiles() {
  return request('/api/v1/profiles/llm');
}

export function getLLMProfile(profileId) {
  return request(`/api/v1/profiles/llm/${profileId}`);
}

export function createLLMProfile(profile) {
  return request('/api/v1/profiles/llm', {
    method: 'POST',
    body: JSON.stringify(profile),
  });
}

export function updateLLMProfile(profileId, profile) {
  return request(`/api/v1/profiles/llm/${profileId}`, {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
}

export function deleteLLMProfile(profileId) {
  return request(`/api/v1/profiles/llm/${profileId}`, {
    method: 'DELETE',
  });
}

export function getAgentPersonas(role = null) {
  const params = role ? `?role=${encodeURIComponent(role)}` : '';
  return request(`/api/v1/profiles/agents${params}`);
}

export function getAgentPersona(personaId) {
  return request(`/api/v1/profiles/agents/${personaId}`);
}

export function createAgentPersona(persona) {
  return request('/api/v1/profiles/agents', {
    method: 'POST',
    body: JSON.stringify(persona),
  });
}

export function updateAgentPersona(personaId, persona) {
  return request(`/api/v1/profiles/agents/${personaId}`, {
    method: 'PUT',
    body: JSON.stringify(persona),
  });
}

export function deleteAgentPersona(personaId) {
  return request(`/api/v1/profiles/agents/${personaId}`, {
    method: 'DELETE',
  });
}

export function getPromptVariants() {
  return request('/api/v1/profiles/prompts');
}

export function previewPromptVariant(variantId, agentRole) {
  return request(`/api/v1/profiles/prompts/${variantId}/preview?agent_role=${encodeURIComponent(agentRole)}`);
}

export function deletePromptVariant(variantId) {
  return request(`/api/v1/profiles/prompts/${variantId}`, {
    method: 'DELETE',
  });
}

export function estimateCost(llmProfileId, numAgents = 4, numRounds = 3) {
  return request(`/api/v1/profiles/cost-estimate?llm_profile_id=${encodeURIComponent(llmProfileId)}&num_agents=${numAgents}&num_rounds=${numRounds}`);
}

// ---------------------------------------------------------------------------
// System (Sprint 3)
// ---------------------------------------------------------------------------

export function reloadProfiles() {
  return request('/api/v1/system/reload-profiles', { method: 'POST' });
}

export function getBackendLogs(lines = 100, search = null) {
  let url = `/api/v1/system/logs?lines=${lines}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  return request(url);
}
