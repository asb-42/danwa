/**
 * i18n management API functions (Plan 20: Multi-Language Support).
 */

import { request } from './core.js';

/** Get list of supported locales with metadata. */
export function getSupportedLocales() {
  return request('/api/v1/i18n/locales');
}

/** Get translations for a locale (optionally filtered by keys). */
export function getTranslations(locale, keys = null) {
  const params = new URLSearchParams();
  if (keys) params.set('keys', keys.join(','));
  return request(`/api/v1/i18n/${locale}?${params.toString()}`);
}

/** Get a single translation by key. */
export function getTranslation(locale, key) {
  return request(`/api/v1/i18n/${locale}/${encodeURIComponent(key)}`);
}

/** Set a single translation. */
export function setTranslation(locale, key, value, namespace = 'global') {
  return request(`/api/v1/i18n/${locale}/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ key, value, namespace }),
  });
}

/** Bulk-set translations for a locale. */
export function bulkSetTranslations(locale, translations, namespace = 'global') {
  return request(`/api/v1/i18n/${locale}`, {
    method: 'POST',
    body: JSON.stringify({ locale, translations, namespace }),
  });
}

/** Delete a translation. */
export function deleteTranslation(locale, key, namespace = 'global') {
  return request(`/api/v1/i18n/${locale}/${encodeURIComponent(key)}?namespace=${namespace}`, {
    method: 'DELETE',
  });
}

/** Get translation coverage statistics. */
export function getTranslationStats(namespace = 'global') {
  return request(`/api/v1/i18n/stats?namespace=${namespace}`);
}

/** Get translation coverage report. */
export function getTranslationCoverage(namespace = 'global') {
  return request(`/api/v1/i18n/coverage?namespace=${namespace}`);
}

/** Start an async bulk translation job. Returns job_id for polling. */
export function bulkTranslate(targetLocales = null, namespace = 'global', force = false, wipeFirst = false) {
  return request('/api/v1/i18n/bulk-translate', {
    method: 'POST',
    body: JSON.stringify({ target_locales: targetLocales, namespace, force, wipe_first: wipeFirst }),
  });
}

/** Wipe all translations for a locale. */
export function wipeLocale(locale, namespace = 'global') {
  return request(`/api/v1/i18n/${encodeURIComponent(locale)}/wipe`, {
    method: 'POST',
    body: JSON.stringify({ namespace }),
  });
}

/** Get the status and progress of a translation job. */
export function getTranslationJobStatus(jobId) {
  return request(`/api/v1/i18n/bulk-translate/${jobId}/status`);
}

/** List all translation jobs. */
export function listTranslationJobs() {
  return request('/api/v1/i18n/bulk-translate');
}

/** Get per-locale string details with translation status, source, dates. */
export function getLocaleDetails(locale, namespace = 'global') {
  return request(`/api/v1/i18n/strings/${encodeURIComponent(locale)}?namespace=${namespace}`);
}

/** Register a new custom locale. */
export function registerLocale(locale, name = null, isRtl = false) {
  return request('/api/v1/i18n/locales', {
    method: 'POST',
    body: JSON.stringify({ locale, name, is_rtl: isRtl }),
  });
}

/** List custom-registered locales. */
export function getCustomLocales() {
  return request('/api/v1/i18n/custom-locales');
}
