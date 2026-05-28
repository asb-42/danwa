/**
 * Translation API functions (Sprint 4).
 */

import { request } from './core.js';

/** Get supported target languages for translation. */
export function getSupportedLanguages() {
  return request('/api/v1/translation/supported-languages');
}

/**
 * Translate a module to the target language.
 * @param {string} moduleId
 * @param {object} options - { target_language, force, llm_profile_id, skip_back_translation, auto_approve, quality_threshold }
 * @returns {Promise<Object>}
 */
export function translateModule(moduleId, options = {}) {
  return request(`/api/v1/translation/${moduleId}/translate`, {
    method: 'POST',
    body: JSON.stringify(options),
  });
}

/**
 * Get translation status for a module.
 * @param {string} moduleId
 * @param {object} params - { target_language, approved_only }
 * @returns {Promise<Object>}
 */
export function getTranslationStatus(moduleId, params = {}) {
  const qs = new URLSearchParams();
  if (params.target_language) qs.set('target_language', params.target_language);
  if (params.approved_only) qs.set('approved_only', 'true');
  return request(`/api/v1/translation/${moduleId}/status?${qs.toString()}`);
}

/**
 * Get translation statistics for a module.
 * @param {string} moduleId
 * @returns {Promise<Object>}
 */
export function getTranslationStatistics(moduleId) {
  return request(`/api/v1/translation/${moduleId}/statistics`);
}

/**
 * Approve or reject a specific translation.
 * @param {string} moduleId
 * @param {object} body - { file_path, approved }
 * @returns {Promise<Object>}
 */
export function approveTranslation(moduleId, body) {
  return request(`/api/v1/translation/${moduleId}/approve`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Invalidate cached translations.
 * @param {string} moduleId
 * @param {object} body - { file_path, target_language }
 * @returns {Promise<Object>}
 */
export function invalidateTranslation(moduleId, body = {}) {
  return request(`/api/v1/translation/${moduleId}/invalidate`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Batch translate multiple modules.
 * @param {object} body - { module_ids, target_language, force, parallel }
 * @returns {Promise<Object>}
 */
export function batchTranslate(body) {
  return request('/api/v1/translation/batch-translate', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
