/**
 * Debate-related API functions.
 *
 * All functions auto-resolve tenant and case from stores and use
 * tenant-scoped endpoints where available.  Operations without
 * tenant-scoped equivalents fall back to legacy endpoints (which
 * rely on the X-Case-Id header injected by core.js).
 */

import { get } from 'svelte/store';
import { activeCase } from '../stores.js';
import { currentTenant } from '../stores/auth.svelte.js';
import { request } from './core.js';

function _ctx() {
  const tenant = get(currentTenant);
  const caseObj = get(activeCase);
  return { tenantId: tenant?.id, caseId: caseObj?.id };
}

// ---------------------------------------------------------------------------
// Debate
// ---------------------------------------------------------------------------

export function getDebates(limit = 50, { status = null, search = null, offset = 0 } = {}) {
  const { tenantId } = _ctx();
  if (tenantId) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (status) params.set('status', status);
    if (search) params.set('search', search);
    return request(`/api/v1/tenants/${tenantId}/debates?${params.toString()}`);
  }
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) params.set('status', status);
  if (search) params.set('search', search);
  return request(`/api/v1/debate?${params.toString()}`);
}

export function findRunningDebateAcrossProjects() {
  return request('/api/v1/debate/cross-project/running');
}

export function createDebate(caseText, options = {}) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates`, {
      method: 'POST',
      body: JSON.stringify({ case_text: caseText, ...options }),
    });
  }
  return request('/api/v1/debate', {
    method: 'POST',
    body: JSON.stringify({
      case: { text: caseText },
      ...options,
    }),
  });
}

export function getDebate(debateId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}`);
  }
  return request(`/api/v1/debate/${debateId}`);
}

export function deleteDebate(debateId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}`, {
      method: 'DELETE',
    });
  }
  return request(`/api/v1/debate/${debateId}`, {
    method: 'DELETE',
  });
}

export function moveDebate(debateId, targetProjectId) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/debate/${debateId}`, {
    method: 'PATCH',
    body: JSON.stringify({ project_id: targetProjectId }),
  });
}

export function startDebate(debateId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}/start`, {
      method: 'POST',
    });
  }
  return request(`/api/v1/debate/${debateId}/start`, {
    method: 'POST',
  });
}

export function cancelDebate(debateId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}/cancel`, {
      method: 'POST',
    });
  }
  return request(`/api/v1/debate/${debateId}/cancel`, {
    method: 'POST',
  });
}

// ---------------------------------------------------------------------------
// Extension / Extra Rounds
// ---------------------------------------------------------------------------

export function requestExtension(debateId, body) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/debate/${debateId}/extension-request`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function decideExtension(debateId, decision) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/debate/${debateId}/extension-decision`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  });
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export function getAuditEvents(debateId) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/audit/${debateId}`);
  }
  return request(`/api/v1/audit/${debateId}`);
}

// ---------------------------------------------------------------------------
// Document assignment
// ---------------------------------------------------------------------------

export function assignDocumentsToDebate(debateId, documentIds, ragAutoRetrieve = false) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/debate/${debateId}/documents`, {
    method: 'PUT',
    body: JSON.stringify({ document_ids: documentIds, rag_auto_retrieve: ragAutoRetrieve }),
  });
}

// ---------------------------------------------------------------------------
// OOB Input
// ---------------------------------------------------------------------------

/**
 * Submit an Out-of-Band (OOB) input to a running debate.
 * @param {string} debateId
 * @param {{ content: string, target: { type: string, agent_role?: string, round?: number, current_agent_role?: string, from_round?: number }, urgency?: string }} body
 * @returns {Promise<{ oob_id: string, status: string, target_resolved: string }>}
 */
export function submitOOBInput(debateId, body) {
  const { tenantId, caseId } = _ctx();
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}/oob`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }
  return request(`/api/v1/debate/${debateId}/oob`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Follow-up / Fork (Plan 19)
// ---------------------------------------------------------------------------

/** Continue a completed debate with optional focus topic. */
export function continueDebate(debateId, body) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/debate/${debateId}/continue`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** Fork a debate from consensus with new topic. */
export function forkFromConsensus(debateId, body) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/debate/${debateId}/fork-from-consensus`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** Fork a debate with optional modifications. */
export function forkDebate(debateId, body) {
  // No tenant-scoped equivalent yet — legacy endpoint
  return request(`/api/v1/debate/${debateId}/fork`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** List all forks of a given debate. */
export function listDebateForks(debateId, limit = 50, offset = 0) {
  const { tenantId, caseId } = _ctx();
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (tenantId && caseId) {
    return request(`/api/v1/tenants/${tenantId}/cases/${caseId}/debates/${debateId}/forks?${params.toString()}`);
  }
  return request(`/api/v1/debate/${debateId}/forks?${params.toString()}`);
}
