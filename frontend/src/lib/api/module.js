/**
 * Module registry API functions (Sprint 4).
 */

import { request } from './core.js';

/** Get all registered modules. */
export function getModules() {
  return request('/api/v1/modules/');
}

/** Get details for a specific module. */
export function getModule(moduleId) {
  return request(`/api/v1/modules/${moduleId}`);
}

/** Install a module. */
export function installModule(moduleId) {
  return request('/api/v1/modules/install', {
    method: 'POST',
    body: JSON.stringify({ module_id: moduleId, source: 'local' }),
  });
}

/** Uninstall a module. */
export function uninstallModule(moduleId) {
  return request(`/api/v1/modules/${moduleId}/uninstall`, { method: 'POST' });
}

/** Update a module. */
export function updateModule(moduleId) {
  return request(`/api/v1/modules/${moduleId}/update`, { method: 'POST' });
}

/** Rollback a module to previous version. */
export function rollbackModule(moduleId) {
  return request(`/api/v1/modules/${moduleId}/rollback`, { method: 'POST' });
}

/** Get module validation results. */
export function validateModule(moduleId) {
  return request(`/api/v1/modules/${moduleId}/validate`);
}

/** Enable (activate) a module. */
export function enableModule(moduleId) {
  return request(`/api/v1/modules/${moduleId}/enable`, { method: 'POST' });
}

/** Disable (deactivate) a module. */
export function disableModule(moduleId) {
  return request(`/api/v1/modules/${moduleId}/disable`, { method: 'POST' });
}

/** Export a module as ZIP. Returns blob URL for download. */
export async function exportModule(moduleId) {
  const resp = await fetch(`/api/v1/modules/${moduleId}/export`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(err.detail || 'Export failed');
  }
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

/** Get available modules from registry. */
export function getAvailableModules() {
  return request('/api/v1/modules/available');
}

/** Fetch the module index from the danwa-modules GitHub repository. */
export function getRepoIndex(forceRefresh = false) {
  return request(`/api/v1/modules/repo-index?force_refresh=${forceRefresh}`);
}

/** Install a module directly from the danwa-modules GitHub release. */
export function installFromRepo(moduleId, version = null) {
  return request('/api/v1/modules/install-from-repo', {
    method: 'POST',
    body: JSON.stringify({ module_id: moduleId, version }),
  });
}

/** Check for available updates from the danwa-modules repo. */
export function getRepoUpdates() {
  return request('/api/v1/modules/check-repo-updates');
}

/** Get the parsed profile data for a module. */
export function getModuleProfile(moduleId) {
  return request(`/api/v1/modules/${moduleId}/profile`);
}

/** Update a module's profile data. */
export function updateModuleProfile(moduleId, data) {
  return request(`/api/v1/modules/${moduleId}/profile`, {
    method: 'PUT',
    body: JSON.stringify({ data }),
  });
}

/** Duplicate a module with a new ID. */
export function duplicateModule(moduleId, newId, newName = null) {
  return request(`/api/v1/modules/${moduleId}/duplicate`, {
    method: 'POST',
    body: JSON.stringify({ new_id: newId, new_name: newName }),
  });
}
