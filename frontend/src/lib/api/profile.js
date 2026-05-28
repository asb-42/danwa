/**
 * Profile-related API functions.
 * LLM profiles, agent personas, BYOK, prompt variants, cost estimation,
 * service LLM, and system reload.
 */

import { request } from './core.js';

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

// ---------------------------------------------------------------------------
// BYOK (Bring Your Own Key)
// ---------------------------------------------------------------------------

export function getUserKeys() {
  return request('/api/v1/user-keys');
}

export function setUserKey(profileId, apiKey, label = '') {
  return request('/api/v1/user-keys', {
    method: 'PUT',
    body: JSON.stringify({ profile_id: profileId, api_key: apiKey, label }),
  });
}

export function deleteUserKey(profileId) {
  return request(`/api/v1/user-keys/${profileId}`, {
    method: 'DELETE',
  });
}

export function deleteAllUserKeys() {
  return request('/api/v1/user-keys', {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Agent Personas
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Prompt Variants
// ---------------------------------------------------------------------------

export function getPromptVariants() {
  return request('/api/v1/profiles/prompts');
}

export function previewPromptVariant(variantId, agentRole) {
  return request(`/api/v1/profiles/prompts/${variantId}/preview?agent_role=${encodeURIComponent(agentRole)}`);
}

export function createPromptVariant(variant) {
  return request('/api/v1/profiles/prompts', {
    method: 'POST',
    body: JSON.stringify(variant),
  });
}

export function deletePromptVariant(variantId) {
  return request(`/api/v1/profiles/prompts/${variantId}`, {
    method: 'DELETE',
  });
}

export function translatePromptVariant(variantId, options = {}) {
  return request(`/api/v1/profiles/prompts/${variantId}/translate`, {
    method: 'POST',
    body: JSON.stringify({
      target_language: options.targetLanguage || 'de',
      force: options.force || false,
      auto_approve: options.autoApprove !== false,
    }),
  });
}

// ---------------------------------------------------------------------------
// Cost Estimation
// ---------------------------------------------------------------------------

export function estimateCost(llmProfileId, numAgents = 4, numRounds = 3) {
  return request(`/api/v1/profiles/cost-estimate?llm_profile_id=${encodeURIComponent(llmProfileId)}&num_agents=${numAgents}&num_rounds=${numRounds}`);
}

// ---------------------------------------------------------------------------
// Service LLM (Sprint 16)
// ---------------------------------------------------------------------------

/** Get list of service-eligible LLM profiles. */
export function getServiceEligibleProfiles() {
  return request('/api/v1/profiles/llm/service-eligible');
}

/** Validate a profile for service LLM eligibility. */
export function validateServiceLLM(profileId) {
  return request('/api/v1/config/validate-service-llm', {
    method: 'POST',
    body: JSON.stringify({ profile_id: profileId }),
  });
}

/** Set the active service LLM profile. */
export function setServiceLLM(profileId) {
  return request('/api/v1/config/service-llm', {
    method: 'POST',
    body: JSON.stringify({ profile_id: profileId }),
  });
}

// ---------------------------------------------------------------------------
// System (Sprint 3)
// ---------------------------------------------------------------------------

export function reloadProfiles() {
  return request('/api/v1/system/reload-profiles', { method: 'POST' });
}
