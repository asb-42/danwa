/**
 * Document / DMS related API functions.
 *
 * All functions auto-resolve tenant and case from stores and use
 * tenant-scoped endpoints where available.  Operations without
 * tenant-scoped equivalents fall back to legacy endpoints (which
 * rely on the X-Case-Id header injected by core.js).
 */

import { get } from 'svelte/store';
import { activeCase } from '../stores.js';
import { currentTenant } from '../stores/auth.svelte.js';
import { request, API_BASE } from './core.js';

function _ctx() {
  const tenant = get(currentTenant);
  const caseObj = get(activeCase);
  return { tenantId: tenant?.id, caseId: caseObj?.id };
}

// ---------------------------------------------------------------------------
// DMS / Documents
// ---------------------------------------------------------------------------

export function getDocuments() {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents`);
  }
  return request('/api/v1/dms/documents');
}

export function getDocument(documentId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents/${documentId}`);
  }
  return request(`/api/v1/dms/documents/${documentId}`);
}

export function uploadDocument(file) {
  const { tenantId, caseId } = _ctx();
  const formData = new FormData();
  formData.append('file', file);

  // Flatten FastAPI error payloads (which put a list of validation
  // errors in `detail`) into a single human-readable string.  Without
  // this the user sees `[object Object]` when the backend rejects
  // an upload for a missing/invalid field.
  const flattenError = (err, fallback) => {
    let detail = err?.detail ?? fallback;
    if (Array.isArray(detail)) {
      detail = detail
        .map((e) => {
          if (typeof e === 'string') return e;
          if (e && typeof e === 'object') {
            const loc = Array.isArray(e.loc) ? e.loc.join('.') : '';
            const msg = e.msg || JSON.stringify(e);
            return loc ? `${loc}: ${msg}` : msg;
          }
          return String(e);
        })
        .join('; ');
    } else if (detail && typeof detail === 'object') {
      const msg = detail.message || detail.msg || '';
      const errors = Array.isArray(detail.errors) ? detail.errors.join('; ') : '';
      detail = msg && errors ? `${msg}: ${errors}` : msg || errors || JSON.stringify(detail);
    }
    return typeof detail === 'string' ? detail : fallback;
  };

  const handleResponse = async (response) => {
    if (response.ok) return response.json();
    const error = await response.json().catch(() => ({}));
    throw new Error(flattenError(error, `HTTP ${response.status}`));
  };

  if (tenantId && caseId) {
    return fetch(`${API_BASE}/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents`, {
      method: 'POST',
      headers: { 'Accept-Language': 'en' },
      body: formData,
    }).then(handleResponse);
  }

  const caseIdHeader = caseId || get(activeCase)?.id;
  return fetch(`${API_BASE}/api/v1/dms/documents`, {
    method: 'POST',
    headers: {
      'Accept-Language': 'en',
      ...(caseIdHeader ? { 'X-Case-Id': caseIdHeader } : {}),
    },
    body: formData,
  }).then(handleResponse);
}

export function deleteDocument(documentId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents/${documentId}`, {
      method: 'DELETE',
    });
  }
  return request(`/api/v1/dms/documents/${documentId}`, {
    method: 'DELETE',
  });
}

export function updateDocumentText(documentId, text) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/dms/documents/${documentId}/text`, {
    method: 'PUT',
    body: JSON.stringify({ text }),
  });
}

export function moveDocument(documentId, targetProjectId) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/dms/documents/${documentId}/move`, {
    method: 'POST',
    body: JSON.stringify({ target_project_id: targetProjectId }),
  });
}

export function addDocumentToRAG(documentId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents/${documentId}/rag`, {
      method: 'POST',
    });
  }
  return request(`/api/v1/dms/documents/${documentId}/rag`, {
    method: 'POST',
  });
}

export function analyzeDocuments({ language = 'de', mode = 'full' } = {}) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/analyze?language=${language}&mode=${mode}`, { method: 'POST' });
  }
  return request(`/api/v1/dms/analyze?language=${language}&mode=${mode}`, { method: 'POST' });
}

export function getAnalysis() {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/analyze`);
  }
  return request('/api/v1/dms/analyze');
}

export function removeDocumentFromRAG(documentId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/documents/${documentId}/rag`, {
      method: 'DELETE',
    });
  }
  return request(`/api/v1/dms/documents/${documentId}/rag`, {
    method: 'DELETE',
  });
}

export function getManualRAGDocuments() {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request('/api/v1/dms/rag/manual');
}

export function searchRAG(query, limit = 5) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/dms/rag/search?query=${encodeURIComponent(query)}&limit=${limit}`);
  }
  return request(`/api/v1/dms/rag/search?query=${encodeURIComponent(query)}&k=${limit}`);
}

export function exportAnalysis(format = 'pdf') {
  const { tenantId, caseId } = _ctx();
  const url = (tenantId && caseId)
    ? `${API_BASE}/api/v1/tenants/${tenantId}/cases/${caseId}/dms/analyze/export`
    : `${API_BASE}/api/v1/dms/analyze/export`;
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format }),
  }).then(async (response) => {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Export failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `analysis.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
  });
}

export function getOcrStatus() {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request('/api/v1/dms/ocr-status');
}


export function getOcrSettings() {
  return request('/api/v1/config/ocr-settings');
}


export function updateOcrSettings(settings) {
  return request('/api/v1/config/ocr-settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}
