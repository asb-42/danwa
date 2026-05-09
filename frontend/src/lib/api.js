/**
 * API client for Debate Engine v2.0 backend.
 * All communication in English (Accept-Language: en).
 */

import { get } from 'svelte/store';
import { i18n } from './i18n/index.js';
import { activeProject } from './stores.js';

const API_BASE = import.meta.env.VITE_API_URL || '';

const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept-Language': 'en',
};

/**
 * Map of backend error messages to i18n keys.
 */
const ERROR_MAP = {
  'Debate not found': 'error.debateNotFound',
  'Invalid input': 'error.invalidInput',
  'Backend connection lost': 'error.backendDisconnected',
};

/**
 * Translate a backend error message to the current UI locale.
 */
export function translateBackendError(backendMessage) {
  const key = ERROR_MAP[backendMessage];
  if (key) return i18n.t(key);
  // Return the actual backend message if no translation mapping exists
  return backendMessage || i18n.t('common.error');
}

/**
 * Generic fetch wrapper with error handling.
 *
 * Automatically injects the ``X-Project-Id`` header from the
 * ``activeProject`` store for all project-scoped requests.
 */
export async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const projectId = get(activeProject)?.id;
  const headers = {
    ...DEFAULT_HEADERS,
    ...(projectId ? { 'X-Project-Id': projectId } : {}),
    ...options.headers,
  };
  const response = await fetch(url, {
    headers,
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    let detail = error.detail || `HTTP ${response.status}`;
    // FastAPI validation errors return detail as an array of objects
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
    }
    throw new Error(translateBackendError(detail));
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function getHealth() {
  return request('/health');
}

// ---------------------------------------------------------------------------
// Debate
// ---------------------------------------------------------------------------

export function getDebates(limit = 50, { status = null, search = null, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) params.set('status', status);
  if (search) params.set('search', search);
  return request(`/api/v1/debate?${params.toString()}`);
}

export function createDebate(caseText, options = {}) {
  return request('/api/v1/debate', {
    method: 'POST',
    body: JSON.stringify({
      case: { text: caseText },
      ...options,
    }),
  });
}

export function getDebate(debateId) {
  return request(`/api/v1/debate/${debateId}`);
}

export function deleteDebate(debateId) {
  return request(`/api/v1/debate/${debateId}`, {
    method: 'DELETE',
  });
}

export function startDebate(debateId) {
  return request(`/api/v1/debate/${debateId}/start`, {
    method: 'POST',
  });
}

export function cancelDebate(debateId) {
  return request(`/api/v1/debate/${debateId}/cancel`, {
    method: 'POST',
  });
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export function getAuditEvents(debateId) {
  return request(`/api/v1/audit/${debateId}`);
}

// ---------------------------------------------------------------------------
// Profiles (Sprint 3)
// ---------------------------------------------------------------------------

export function getLLMProfiles() {
  return request('/api/v1/profiles/llm');
}

export function getLLMProfile(profileId) {
  return request(`/api/v1/profiles/llm/${profileId}`);
}

export function createLLMProfile(profile) {
  return request('/api/v1/profiles/llm', {
    method: 'POST',
    body: JSON.stringify(profile),
  });
}

export function updateLLMProfile(profileId, profile) {
  return request(`/api/v1/profiles/llm/${profileId}`, {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
}

export function deleteLLMProfile(profileId) {
  return request(`/api/v1/profiles/llm/${profileId}`, {
    method: 'DELETE',
  });
}

export function getAgentPersonas(role = null) {
  const params = role ? `?role=${encodeURIComponent(role)}` : '';
  return request(`/api/v1/profiles/agents${params}`);
}

export function getAgentPersona(personaId) {
  return request(`/api/v1/profiles/agents/${personaId}`);
}

export function createAgentPersona(persona) {
  return request('/api/v1/profiles/agents', {
    method: 'POST',
    body: JSON.stringify(persona),
  });
}

export function updateAgentPersona(personaId, persona) {
  return request(`/api/v1/profiles/agents/${personaId}`, {
    method: 'PUT',
    body: JSON.stringify(persona),
  });
}

export function deleteAgentPersona(personaId) {
  return request(`/api/v1/profiles/agents/${personaId}`, {
    method: 'DELETE',
  });
}

export function getPromptVariants() {
  return request('/api/v1/profiles/prompts');
}

export function previewPromptVariant(variantId, agentRole) {
  return request(`/api/v1/profiles/prompts/${variantId}/preview?agent_role=${encodeURIComponent(agentRole)}`);
}

export function deletePromptVariant(variantId) {
  return request(`/api/v1/profiles/prompts/${variantId}`, {
    method: 'DELETE',
  });
}

export function estimateCost(llmProfileId, numAgents = 4, numRounds = 3) {
  return request(`/api/v1/profiles/cost-estimate?llm_profile_id=${encodeURIComponent(llmProfileId)}&num_agents=${numAgents}&num_rounds=${numRounds}`);
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export function getSettings() {
  return request('/api/v1/config/settings');
}

export function updateSettings(settings) {
  return request('/api/v1/config/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

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
  const projectId = get(activeProject)?.id;
  const formData = new FormData();
  formData.append('file', file);
  return fetch(`${API_BASE}/api/v1/dms/documents`, {
    method: 'POST',
    headers: {
      'Accept-Language': 'en',
      ...(projectId ? { 'X-Project-Id': projectId } : {}),
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

export function addDocumentToRAG(documentId) {
  return request(`/api/v1/dms/documents/${documentId}/rag`, {
    method: 'POST',
  });
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
  return request(`/api/v1/dms/rag/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export function assignDocumentsToDebate(debateId, documentIds, ragAutoRetrieve = false) {
  return request(`/api/v1/debate/${debateId}/documents`, {
    method: 'PUT',
    body: JSON.stringify({ document_ids: documentIds, rag_auto_retrieve: ragAutoRetrieve }),
  });
}

// ---------------------------------------------------------------------------
// System (Sprint 3)
// ---------------------------------------------------------------------------

export function reloadProfiles() {
  return request('/api/v1/system/reload-profiles', { method: 'POST' });
}

export function getBackendLogs(lines = 100, search = null) {
  let url = `/api/v1/system/logs?lines=${lines}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  return request(url);
}

/**
 * Submit an Out-of-Band (OOB) input to a running debate.
 * @param {string} debateId
 * @param {{ content: string, target: { type: string, agent_role?: string, round?: number, current_agent_role?: string, from_round?: number }, urgency?: string }} body
 * @returns {Promise<{ oob_id: string, status: string, target_resolved: string }>}
 */
export function submitOOBInput(debateId, body) {
  return request(`/api/v1/debate/${debateId}/oob`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
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
// Language (Phase 8)
// ---------------------------------------------------------------------------

export function getLanguage() {
  return request('/api/v1/config/language');
}

export function setLanguage(language) {
  return request('/api/v1/config/language', {
    method: 'PUT',
    body: JSON.stringify({ language }),
  });
}

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
