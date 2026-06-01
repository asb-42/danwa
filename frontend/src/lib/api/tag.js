/**
 * Tag API functions — tenant-global tag CRUD.
 */

import { request } from './core.js';

export function getTags(tenantId) {
  return request(`/api/v1/tenants/${tenantId}/tags`);
}

export function createTag(tenantId, { name, color, parent_id }) {
  return request(`/api/v1/tenants/${tenantId}/tags`, {
    method: 'POST',
    body: JSON.stringify({ name, color: color || null, parent_id: parent_id || null }),
  });
}

export function getTag(tenantId, tagId) {
  return request(`/api/v1/tenants/${tenantId}/tags/${tagId}`);
}

export function updateTag(tenantId, tagId, updates) {
  return request(`/api/v1/tenants/${tenantId}/tags/${tagId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export function deleteTag(tenantId, tagId) {
  return request(`/api/v1/tenants/${tenantId}/tags/${tagId}`, {
    method: 'DELETE',
  });
}
