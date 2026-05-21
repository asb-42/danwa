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
 * @param {{ language?: string, projectId?: string, maxRounds?: number, threshold?: number }} [options]
 * @returns {Promise<{ session_id: string, status: string }>}
 */
export function startWorkflow(workflowId, context, options = {}) {
  return request(`/api/v1/workflow-exec/${workflowId}/start`, {
    method: 'POST',
    body: JSON.stringify({
      context,
      language: options.language || 'de',
      project_id: options.projectId || 'default',
      max_rounds: options.maxRounds || 10,
      threshold: options.threshold || 0.7,
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
    }),
  });
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
