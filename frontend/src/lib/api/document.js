/**
 * Document / DMS related API functions.
 */

import { get } from 'svelte/store';
import { activeCase } from '../stores.js';
import { request, API_BASE } from './core.js';

// ---------------------------------------------------------------------------
// DMS / Documents
// ---------------------------------------------------------------------------

export function getDocuments() {
  return request('/api/v1/dms/documents');
}

export function getDocument(documentId) {
  return request(`/api/v1/dms/documents/${documentId}`);
}

export function uploadDocument(file) {
  const caseId = get(activeCase)?.id;
  const formData = new FormData();
  formData.append('file', file);
  return fetch(`${API_BASE}/api/v1/dms/documents`, {
    method: 'POST',
    headers: {
      'Accept-Language': 'en',
      ...(caseId ? { 'X-Case-Id': caseId } : {}),
    },
    body: formData,
  }).then(async (response) => {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  });
}

export function deleteDocument(documentId) {
  return request(`/api/v1/dms/documents/${documentId}`, {
    method: 'DELETE',
  });
}

export function updateDocumentText(documentId, text) {
  return request(`/api/v1/dms/documents/${documentId}/text`, {
    method: 'PUT',
    body: JSON.stringify({ text }),
  });
}

export function moveDocument(documentId, targetProjectId) {
  return request(`/api/v1/dms/documents/${documentId}/move`, {
    method: 'POST',
    body: JSON.stringify({ target_project_id: targetProjectId }),
  });
}

export function addDocumentToRAG(documentId) {
  return request(`/api/v1/dms/documents/${documentId}/rag`, {
    method: 'POST',
  });
}

export function analyzeDocuments({ language = 'de', mode = 'full' } = {}) {
  return request(`/api/v1/dms/analyze?language=${language}&mode=${mode}`, { method: 'POST' });
}

export function getAnalysis() {
  return request('/api/v1/dms/analyze');
}

export function removeDocumentFromRAG(documentId) {
  return request(`/api/v1/dms/documents/${documentId}/rag`, {
    method: 'DELETE',
  });
}

export function getManualRAGDocuments() {
  return request('/api/v1/dms/rag/manual');
}

export function searchRAG(query, limit = 5) {
  return request(`/api/v1/dms/rag/search?query=${encodeURIComponent(query)}&k=${limit}`);
}

export function exportAnalysis(format = 'pdf') {
  const caseId = get(activeCase)?.id;
  return fetch(`${API_BASE}/api/v1/dms/analyze/export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(caseId ? { 'X-Case-Id': caseId } : {}),
    },
    body: JSON.stringify({ format }),
  }).then(async (response) => {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Export failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    // Trigger download
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analysis.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });
}

export function getOcrStatus() {
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
