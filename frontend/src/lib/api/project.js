/**
 * Project-related API functions.
 */

import { request } from './core.js';

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function getProjects() {
  return request('/api/v1/projects');
}

export function getProject(projectId) {
  return request(`/api/v1/projects/${projectId}`);
}

export function createProject(name, description = '') {
  return request('/api/v1/projects', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  });
}

export function updateProject(projectId, data) {
  return request(`/api/v1/projects/${projectId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteProject(projectId) {
  return request(`/api/v1/projects/${projectId}`, {
    method: 'DELETE',
  });
}

export function getProjectConfig(projectId) {
  return request(`/api/v1/projects/${projectId}/config`);
}

export function updateProjectConfig(projectId, config) {
  return request(`/api/v1/projects/${projectId}/config`, {
    method: 'PUT',
    body: JSON.stringify({ config }),
  });
}
