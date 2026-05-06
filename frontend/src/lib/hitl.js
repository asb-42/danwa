/**
 * HITL (Human-in-the-Loop) API functions.
 *
 * Provides functions for bidirectional interactions during debates:
 * - injectContext: user → agent context injection
 * - respondToQuery: user → agent query response
 * - pauseDebate: pause/resume debate
 * - getHITLStatus: current HITL state
 * - getInteractions: interaction history
 */

import { request } from './api.js';

/**
 * Inject user context into a running debate.
 *
 * @param {string} debateId
 * @param {{ content: string, target_agent?: string|null, target_round?: number|null, priority?: string }} params
 * @returns {Promise<{ interaction_id: string, status: string, target_resolved: string, message: string }>}
 */
export function injectContext(debateId, { content, target_agent = null, target_round = null, priority = 'normal' }) {
  return request(`/api/v1/debate/${debateId}/inject`, {
    method: 'POST',
    body: JSON.stringify({ content, target_agent, target_round, priority }),
  });
}

/**
 * Respond to an agent's clarification query.
 *
 * @param {string} debateId
 * @param {{ interrupt_id: string, response: string }} params
 * @returns {Promise<{ interaction_id: string, interrupt_id: string, status: string, message: string }>}
 */
export function respondToQuery(debateId, { interrupt_id, response }) {
  return request(`/api/v1/debate/${debateId}/respond`, {
    method: 'POST',
    body: JSON.stringify({ interrupt_id, response }),
  });
}

/**
 * Pause or resume a running debate.
 *
 * @param {string} debateId
 * @param {{ action: 'pause'|'resume', reason?: string }} params
 * @returns {Promise<{ debate_id: string, paused: boolean, action: string, message: string }>}
 */
export function pauseDebate(debateId, { action, reason = '' }) {
  return request(`/api/v1/debate/${debateId}/pause`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
  });
}

/**
 * Get current HITL status for a debate.
 *
 * @param {string} debateId
 * @returns {Promise<{ debate_id: string, hitl_enabled: boolean, hitl_mode: string, is_paused: boolean, active_interrupt: Object|null, total_interactions: number, interactions_by_type: Object, round_interrupt_count: number, max_interrupts_per_round: number }>}
 */
export function getHITLStatus(debateId) {
  return request(`/api/v1/debate/${debateId}/hitl/status`);
}

/**
 * Get interaction history for a debate (paginated).
 *
 * @param {string} debateId
 * @param {{ offset?: number, limit?: number, interaction_type?: string|null }} params
 * @returns {Promise<{ interactions: Array, total: number, offset: number, limit: number }>}
 */
export function getInteractions(debateId, { offset = 0, limit = 50, interaction_type = null } = {}) {
  const params = new URLSearchParams();
  params.set('offset', offset);
  params.set('limit', limit);
  if (interaction_type) params.set('interaction_type', interaction_type);
  return request(`/api/v1/debate/${debateId}/interactions?${params.toString()}`);
}
