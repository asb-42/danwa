/**
 * Audit API client — fetches audit log entries and session data
 * for Replay View, Diff View, and Audit Tab.
 */

import { request } from '../api.js';

/**
 * Fetch audit log entries for a session.
 * @param {string} sessionId
 * @param {{ event_type?: string, date_from?: string, date_to?: string, limit?: number, offset?: number }} [filters]
 * @returns {Promise<Array>}
 */
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

/**
 * Fetch workflow sessions for replay selection.
 * @param {string} [workflowId]
 * @param {{ status?: string, limit?: number, offset?: number }} [options]
 * @returns {Promise<Array>}
 */
export function getWorkflowSessions(workflowId, options = {}) {
  const params = new URLSearchParams();
  if (options.status) params.set('status', options.status);
  if (options.limit) params.set('limit', String(options.limit));
  if (options.offset) params.set('offset', String(options.offset));
  const qs = params.toString();
  const base = workflowId
    ? `/api/v1/blueprints/workflows/${workflowId}/sessions`
    : '/api/v1/workflow-exec/sessions';
  return request(`${base}${qs ? '?' + qs : ''}`);
}

/**
 * Fetch a session for replay (session + workflow graph + audit log).
 * @param {string} sessionId
 * @returns {Promise<{ session: Object, workflow: Object, auditLog: Array }>}
 */
export function getSessionForReplay(sessionId) {
  return request(`/api/v1/workflow-exec/${sessionId}/replay-data`);
}

/**
 * Fetch two sessions for diff comparison.
 * @param {string} sessionA
 * @param {string} sessionB
 * @returns {Promise<{ sessionA: Object, sessionB: Object, auditLogA: Array, auditLogB: Array }>}
 */
export function getSessionsForDiff(sessionA, sessionB) {
  return request(`/api/v1/workflow-exec/diff?session_a=${sessionA}&session_b=${sessionB}`);
}
