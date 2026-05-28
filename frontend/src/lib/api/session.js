/**
 * Session management, audit log, reports, and trace API functions.
 */

import { get } from 'svelte/store';
import { activeProject } from '../stores.js';
import { request, API_BASE, DEFAULT_HEADERS } from './core.js';

// ---------------------------------------------------------------------------
// Session soft-delete / restore (Phase 7)
// ---------------------------------------------------------------------------

export function softDeleteSession(sessionId) {
  return request(`/api/v1/workflow-exec/${sessionId}`, { method: 'DELETE' });
}

export function restoreSession(sessionId) {
  return request(`/api/v1/workflow-exec/${sessionId}/restore`, { method: 'POST' });
}

export function getSessionsForReplay(workflowId) {
  const qs = workflowId ? `?workflow_id=${workflowId}&status=completed` : '?status=completed';
  return request(`/api/v1/workflow-exec/sessions${qs}`);
}

export function getSessionsForDiff(workflowId) {
  return request(`/api/v1/workflow-exec/sessions?workflow_id=${workflowId}&status=completed`);
}

// ---------------------------------------------------------------------------
// Audit Log (Phase 7)
// ---------------------------------------------------------------------------

export function getAuditLog(sessionId, filters = {}) {
  const params = new URLSearchParams();
  if (filters.event_type) params.set('event_type', filters.event_type);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.limit) params.set('limit', String(filters.limit));
  if (filters.offset) params.set('offset', String(filters.offset));
  const qs = params.toString();
  return request(`/api/v1/workflow-exec/${sessionId}/audit-log${qs ? '?' + qs : ''}`);
}

// ---------------------------------------------------------------------------
// Reports (Phase 7)
// ---------------------------------------------------------------------------

export function generateReport(sessionId, format) {
  return request(`/api/v1/sessions/${sessionId}/report`, {
    method: 'POST',
    body: JSON.stringify({ format }),
  });
}

export function getReportStatus(jobId) {
  return request(`/api/v1/reports/${jobId}/status`);
}

export async function downloadReport(jobId) {
  const url = `${API_BASE}/api/v1/reports/${jobId}/download`;
  const projectId = get(activeProject)?.id;
  const headers = {
    ...DEFAULT_HEADERS,
    ...(projectId ? { 'X-Project-Id': projectId } : {}),
  };
  const response = await fetch(url, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Download failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.blob();
}

// ---------------------------------------------------------------------------
// Report SSE Progress Stream
// ---------------------------------------------------------------------------

/**
 * Create an SSE connection for report generation progress.
 * @param {string} sessionId
 * @returns {EventSource}
 */
export function createReportSSE(sessionId) {
  const base = import.meta.env.VITE_API_URL || '';
  return new EventSource(`${base}/api/v1/sessions/${sessionId}/report/stream`);
}

// ---------------------------------------------------------------------------
// Legacy Session Trace
// ---------------------------------------------------------------------------

/**
 * Get the execution trace for a session.
 * @param {string} sessionId
 * @returns {Promise<Object>}
 */
export function getTrace(sessionId) {
  return request(`/api/v1/sessions/${sessionId}/trace`);
}
