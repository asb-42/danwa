/**
 * Case API functions for tenant-scoped case operations.
 */

import { get } from 'svelte/store';
import { activeCase } from '../stores.js';
import { request } from './core.js';

export function getCases(tenantId) {
  return request(`/api/v1/tenants/${tenantId}/cases`);
}

export function createCase(tenantId, { title, description, tags }) {
  return request(`/api/v1/tenants/${tenantId}/cases`, {
    method: 'POST',
    body: JSON.stringify({ title, description, tags: tags || [] }),
  });
}

export function getCase(tenantId, caseId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}`);
}

export function updateCase(tenantId, caseId, updates) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export function deleteCase(tenantId, caseId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}`, {
    method: 'DELETE',
  });
}

// --- Case-scoped debates ---

export function getCaseDebates(tenantId, caseId, { limit = 50, offset = 0, status, search } = {}) {
  let q = `?limit=${limit}&offset=${offset}`;
  if (status) q += `&status=${status}`;
  if (search) q += `&search=${encodeURIComponent(search)}`;
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates${q}`);
}

export function createCaseDebate(tenantId, caseId, body) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function getCaseDebate(tenantId, caseId, debateId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}`);
}

export function deleteCaseDebate(tenantId, caseId, debateId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}`, {
    method: 'DELETE',
  });
}

export function startCaseDebate(tenantId, caseId, debateId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}/start`, {
    method: 'POST',
  });
}

export function cancelCaseDebate(tenantId, caseId, debateId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}/cancel`, {
    method: 'POST',
  });
}

// --- Case-scoped DMS ---

export function getCaseDocuments(tenantId, caseId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents`);
}

export function getCaseDocument(tenantId, caseId, documentId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents/${documentId}`);
}

export function deleteCaseDocument(tenantId, caseId, documentId) {
  return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents/${documentId}`, {
    method: 'DELETE',
  });
}
