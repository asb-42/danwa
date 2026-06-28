/**
 * Workflow Execution — API client functions.
 *
 * Provides functions to start, control, and monitor workflow executions.
 * All endpoints are under /api/v1/workflow-exec.
 */

import { request } from './api.js';

/**
 * Start executing a workflow definition.
 * @param {string} workflowId - The workflow definition ID.
 * @param {string} context - The debate topic / context.
 * @param {{ language?: string, projectId?: string, maxRounds?: number, threshold?: number, documentIds?: string[], ragAutoRetrieve?: boolean, includeDebateResults?: boolean, includeDocumentAnalysis?: boolean }} [options]
 * @returns {Promise<{ session_id: string, status: string }>}
 */
export function startWorkflow(workflowId, context, options = {}) {
  return request(`/api/v1/workflow-exec/${workflowId}/start`, {
    method: 'POST',
    body: JSON.stringify({
      context,
      language: options.language || 'de',
      project_id: options.projectId || '_default',
      max_rounds: options.maxRounds || 10,
      threshold: options.threshold || 0.7,
      document_ids: options.documentIds || [],
      rag_auto_retrieve: options.ragAutoRetrieve || false,
      include_document_analysis: options.includeDocumentAnalysis ?? false,
    }),
  });
}

/**
 * Get the current execution state for a workflow session.
 * @param {string} sessionId
 * @returns {Promise<{ session_id: string, status: string, workflow_id?: string, current_node_id?: string, current_round: number, node_outputs: Array, output?: string, final_consensus?: number }>}
 */
export function getWorkflowState(sessionId) {
  return request(`/api/v1/workflow-exec/${sessionId}/state`);
}

/**
 * Pause a running workflow.
 * @param {string} sessionId
 * @returns {Promise<{ session_id: string, status: string }>}
 */
export function pauseWorkflow(sessionId) {
  return request(`/api/v1/workflow-exec/${sessionId}/pause`, {
    method: 'POST',
  });
}

/**
 * Resume a paused workflow.
 * @param {string} sessionId
 * @returns {Promise<{ session_id: string, status: string }>}
 */
export function resumeWorkflow(sessionId) {
  return request(`/api/v1/workflow-exec/${sessionId}/resume`, {
    method: 'POST',
  });
}

/**
 * Cancel a running or paused workflow.
 * @param {string} sessionId
 * @returns {Promise<{ session_id: string, status: string }>}
 */
export function cancelWorkflow(sessionId) {
  return request(`/api/v1/workflow-exec/${sessionId}/cancel`, {
    method: 'POST',
  });
}

/**
 * Start an MVP debate with per-agent LLM profiles.
 * @param {object} params
 * @param {string} params.context - The debate topic
 * @param {string} [params.language] - Language code
 * @param {string} [params.projectId] - Project ID
 * @param {number} [params.maxRounds] - Maximum rounds
 * @param {number} [params.threshold] - Consensus threshold
 * @param {Record<string, string>} [params.llmProfileIds] - role → llm_profile_id mapping
 * @returns {Promise<{ session_id: string, workflow_id: string, status: string, llm_assignments: Record<string, string> }>}
 */
export function startMvpDebate({
  context,
  language = 'de',
  projectId = '_default',
  maxRounds = 5,
  threshold = 0.9,
  llmProfileIds = {},
  agentCoreIds = {},
  argumentationPatternIds = {},
  toneProfileIds = {},
  promptModifierIds = {},
  searchMode = 'off',
  documentIds = [],
  ragAutoRetrieve = false,
  includeDebateResults = false,
  includeDocumentAnalysis = false,
  debateResultIds = [],
  enableExtraRounds = false,
}) {
  return request('/api/v1/workflow-exec/mvp/start', {
    method: 'POST',
    body: JSON.stringify({
      context,
      language,
      project_id: projectId,
      max_rounds: maxRounds,
      threshold,
      llm_profile_ids: llmProfileIds,
      agent_core_ids: agentCoreIds,
      argumentation_pattern_ids: argumentationPatternIds,
      tone_profile_ids: toneProfileIds,
      prompt_modifier_ids: promptModifierIds,
      search_mode: searchMode,
      document_ids: documentIds,
      rag_auto_retrieve: ragAutoRetrieve,
      include_debate_results: includeDebateResults,
      include_document_analysis: includeDocumentAnalysis,
      debate_result_ids: debateResultIds,
      enable_extra_rounds: enableExtraRounds,
    }),
  });
}

/**
 * Fetch all available agent personas (agent cores).
 * @param {string} [role] - Optional role filter
 * @returns {Promise<Array<{ id: string, name: string, role: string, system_prompt: string, llm_profile_id: string, tags: string[] }>>}
 */
export function getAgentCores(role) {
  const params = role ? `?role=${encodeURIComponent(role)}` : '';
  return request(`/api/v1/profiles/agents${params}`);
}

/**
 * Fetch all composition components for Phase 2 dropdowns.
 * @returns {Promise<{ agent_cores: Array, argumentation_patterns: Array, tone_profiles: Array, prompt_modifiers: Array }>}
 */
export function getCompositionComponents() {
  return request('/api/v1/profiles/composition/components');
}

/**
 * Submit a user interjection for a running workflow session.
 * @param {string} sessionId
 * @param {string} content - The interjection text.
 * @param {string} [source='user'] - Origin of the interjection.
 * @returns {Promise<{ interjection_id: string, status: string }>}
 */
export function submitInterjection(sessionId, content, source = 'user') {
  return request(`/api/v1/workflow-exec/${sessionId}/interject`, {
    method: 'POST',
    body: JSON.stringify({ content, source }),
  });
}

// ---------------------------------------------------------------------------
// Phase-snapshot history (workflow-observability feature, see
// `plans/workflow-observability.md` and the new phase-snapshot API in
// `backend/api/routers/workflow_exec.py:905-941`).
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} PhaseSnapshotSummary
 * @property {string} node_id
 * @property {string} node_type
 * @property {number} phase
 * @property {number|null} round
 * @property {number} state_size
 * @property {string} created_at  ISO 8601 timestamp
 */

/**
 * @typedef {Object} PhaseSnapshotDetail
 * @property {string} node_id
 * @property {string} node_type
 * @property {number} phase
 * @property {number|null} round
 * @property {object} state       Full state JSON captured at this phase
 * @property {string} created_at
 */

/**
 * List all phase snapshots captured for a workflow session.
 * Backend persists one snapshot per gate phase + one per `node.started` event
 * via `StateSnapshotStore.save(...)` (see `backend/workflow/state_snapshot.py`).
 *
 * @param {string} sessionId
 * @returns {Promise<PhaseSnapshotSummary[]>}
 */
export function getPhaseSnapshots(sessionId) {
  return request(
    `/api/v1/workflow-exec/${encodeURIComponent(sessionId)}/phase-snapshots`,
  );
}

/**
 * Fetch the full state for a single phase snapshot.
 * Returns `null` when the snapshot does not exist (HTTP 404).
 *
 * @param {string} sessionId
 * @param {string} nodeId
 * @returns {Promise<PhaseSnapshotDetail | null>}
 */
export async function getPhaseSnapshotDetail(sessionId, nodeId) {
  try {
    return await request(
      `/api/v1/workflow-exec/${encodeURIComponent(sessionId)}/phase-snapshots/${encodeURIComponent(nodeId)}`,
    );
  } catch (err) {
    // `request()` in api/core.js throws on !ok with a translated message
    // (e.g. "HTTP 404").  We treat 404 as a legitimate empty-result and
    // re-throw everything else so callers can distinguish transient
    // failures from "no such snapshot".
    const msg = (err && err.message) || '';
    if (/404|HTTP 404|not\s*found/i.test(msg)) return null;
    throw err;
  }
}

// ─── Export / Render (Output Composer) ──────────────────────────────

/**
 * Start a render job for a completed session.
 * @param {string} sessionId
 * @param {{ template_name?: string, primary_format?: string, include_audit_trail?: boolean, include_minority_votes?: boolean, include_toc?: boolean, page_size?: string, language?: string }} [config]
 * @returns {Promise<{ job_id: string, session_id: string, plugin_key: string, status: string }>}
 */
export function startRenderJob(sessionId, config = {}) {
  return request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/render`, {
    method: 'POST',
    body: JSON.stringify({
      plugin_key: 'print',
      config: {
        template_name: config.template_name || 'academic_debate',
        primary_format: config.primary_format || 'pdf',
        include_audit_trail: config.include_audit_trail ?? true,
        include_minority_votes: config.include_minority_votes ?? true,
        include_toc: config.include_toc ?? true,
        page_size: config.page_size || 'a4',
        language: config.language || 'en',
      },
    }),
  });
}

/**
 * Poll render job status.
 * @param {string} jobId
 * @returns {Promise<{ job_id: string, status: string, output_files: string[], error_message?: string }>}
 */
export function getRenderJobStatus(jobId) {
  return request(`/api/v1/render-jobs/${encodeURIComponent(jobId)}`);
}

/**
 * Get the download URL for a render job.
 * @param {string} jobId
 * @param {number} [fileIndex=0]
 * @returns {string} Download URL (use with <a> tag or fetch)
 */
export function getRenderDownloadUrl(jobId, fileIndex = 0) {
  return `/api/v1/render-jobs/${encodeURIComponent(jobId)}/download?file_index=${fileIndex}`;
}

/**
 * Delete a render job and its output files.
 * @param {string} jobId
 * @returns {Promise<void>}
 */
export function deleteRenderJob(jobId) {
  return request(`/api/v1/render-jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
}
