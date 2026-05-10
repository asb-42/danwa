/**
 * Output Composer API client functions.
 *
 * Provides typed wrappers for the Output Composer and
 * Optimization Proposal REST endpoints.
 */

const BASE = '/api/v1';

/**
 * List all registered output plugins with their config schemas.
 */
export async function listOutputPlugins() {
  const res = await fetch(`${BASE}/output-plugins`);
  if (!res.ok) throw new Error(`Failed to list plugins: ${res.status}`);
  return res.json();
}

/**
 * Start a render job for a completed session.
 *
 * @param {string} sessionId - The workflow session ID.
 * @param {string} pluginKey - Plugin key (e.g. "print", "tts").
 * @param {object} config - Plugin-specific configuration.
 * @returns {Promise<{job_id: string, session_id: string, plugin_key: string, status: string}>}
 */
export async function startRenderJob(sessionId, pluginKey, config = {}) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plugin_key: pluginKey, config }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to start render job: ${res.status} ${detail}`);
  }
  return res.json();
}

/**
 * Get the status of a render job.
 *
 * @param {string} jobId
 * @returns {Promise<object>}
 */
export async function getRenderJobStatus(jobId) {
  const res = await fetch(`${BASE}/render-jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get job status: ${res.status}`);
  return res.json();
}

/**
 * Download a generated output file.
 *
 * @param {string} jobId
 * @param {number} fileIndex - Index in output_files (default 0).
 * @returns {Promise<Blob>}
 */
export async function downloadRenderFile(jobId, fileIndex = 0) {
  const res = await fetch(
    `${BASE}/render-jobs/${jobId}/download?file_index=${fileIndex}`
  );
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  return res.blob();
}

/**
 * Delete a render job and its output files.
 *
 * @param {string} jobId
 */
export async function deleteRenderJob(jobId) {
  const res = await fetch(`${BASE}/render-jobs/${jobId}`, {
    method: 'DELETE',
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Delete failed: ${res.status}`);
  }
}

// ---------------------------------------------------------------------------
// Optimization Proposals
// ---------------------------------------------------------------------------

/**
 * Generate a reflection proposal for a workflow.
 *
 * @param {string} workflowId
 * @returns {Promise<{proposal_id: string, target_workflow_id: string, status: string}>}
 */
export async function reflectOnWorkflow(workflowId) {
  const res = await fetch(`${BASE}/workflows/${workflowId}/reflect`, {
    method: 'POST',
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Reflect failed: ${res.status} ${detail}`);
  }
  return res.json();
}

/**
 * List optimization proposals.
 *
 * @param {object} params - { status?, workflow_id?, limit?, offset? }
 */
export async function listProposals(params = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set('status', params.status);
  if (params.workflow_id) qs.set('workflow_id', params.workflow_id);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.offset) qs.set('offset', String(params.offset));
  const res = await fetch(`${BASE}/optimization-proposals?${qs}`);
  if (!res.ok) throw new Error(`List proposals failed: ${res.status}`);
  return res.json();
}

/**
 * Get a single optimization proposal.
 *
 * @param {string} proposalId
 */
export async function getProposal(proposalId) {
  const res = await fetch(`${BASE}/optimization-proposals/${proposalId}`);
  if (!res.ok) throw new Error(`Get proposal failed: ${res.status}`);
  return res.json();
}

/**
 * Approve an optimization proposal (creates new workflow version).
 *
 * @param {string} proposalId
 */
export async function approveProposal(proposalId) {
  const res = await fetch(
    `${BASE}/optimization-proposals/${proposalId}/approve`,
    { method: 'POST' }
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Approve failed: ${res.status} ${detail}`);
  }
  return res.json();
}

/**
 * Reject an optimization proposal.
 *
 * @param {string} proposalId
 */
export async function rejectProposal(proposalId) {
  const res = await fetch(
    `${BASE}/optimization-proposals/${proposalId}/reject`,
    { method: 'POST' }
  );
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Reject failed: ${res.status} ${detail}`);
  }
  return res.json();
}

/**
 * List TTS voices with optional filters.
 *
 * @param {object} params - { language?, gender? }
 */
export async function listTTSVoices(params = {}) {
  const qs = new URLSearchParams();
  if (params.language) qs.set('language', params.language);
  if (params.gender) qs.set('gender', params.gender);
  const res = await fetch(`${BASE}/tts-voices?${qs}`);
  if (!res.ok) throw new Error(`List voices failed: ${res.status}`);
  return res.json();
}

/**
 * Search completed sessions by ID or title for autocomplete.
 *
 * @param {string} query - Search term (ID or title fragment)
 * @param {number} limit - Max results
 * @returns {Promise<Array<{session_id: string, title: string, status: string}>>}
 */
export async function searchSessions(query = '', limit = 20) {
  const qs = new URLSearchParams({ q: query, limit: String(limit) });
  const res = await fetch(`${BASE}/render-sessions?${qs}`);
  if (!res.ok) throw new Error(`Search sessions failed: ${res.status}`);
  return res.json();
}
