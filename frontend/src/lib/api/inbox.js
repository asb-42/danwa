/**
 * Case-Space Inbox API — frontend wrapper.
 *
 * Four endpoints introduced in
 * ``plans/2026-06-14_case-space-workspace.md`` (Phase 2):
 *
 *   - ``GET  /api/v1/inbox?tenant_id=…``         → InboxSummary
 *   - ``POST /api/v1/inbox/bulk-move``            → InboxBulkResult
 *   - ``POST /api/v1/inbox/bulk-tag``             → InboxBulkResult
 *   - ``POST /api/v1/inbox/bulk-delete``          → InboxBulkResult
 *
 * All endpoints are feature-gated by ``settings.enable_case_space_inbox``;
 * while the flag is False they return 404.  The bulk endpoints always
 * return 200 (even on partial failure) — failures are reported in
 * the ``failed`` array so the UI can show a partial-success message.
 *
 * @see plans/2026-06-14_case-space-workspace.md
 */

import { request } from './core.js';

/**
 * @typedef {Object} InboxDebateItem
 * @property {string} id
 * @property {string} kind              "recently_completed" | "untagged" | "stale_running"
 * @property {string} tenant_id
 * @property {string} case_id
 * @property {string} title
 * @property {string} status
 * @property {string[]} tags
 * @property {string|null} updated_at    ISO-8601
 * @property {string|null} completed_at  ISO-8601
 * @property {number|null} age_hours
 * @property {string} message
 */

/**
 * @typedef {Object} InboxSummary
 * @property {string} tenant_id
 * @property {InboxDebateItem[]} items
 * @property {Record<string, number>} counts   kind → count
 * @property {boolean} is_all_clear
 * @property {string} generated_at     ISO-8601
 */

/**
 * @typedef {Object} InboxBulkResult
 * @property {string[]} succeeded
 * @property {{id: string, reason: string}[]} failed
 */

/**
 * Fetch the Inbox for a tenant.
 *
 * @param {string} tenantId
 * @returns {Promise<InboxSummary>}
 * @throws {Error} 404 if the inbox feature flag is off
 */
export async function getInbox(tenantId) {
  if (!tenantId || typeof tenantId !== 'string') {
    throw new TypeError('getInbox: tenantId must be a non-empty string');
  }
  return request(`/api/v1/inbox?tenant_id=${encodeURIComponent(tenantId)}`);
}

/**
 * Move one or more debates to a different case.  Always returns 200;
 * check the ``failed`` array for partial failures (cross-tenant,
 * not found, store rejected).
 *
 * @param {string[]} debateIds
 * @param {string} targetCaseId
 * @returns {Promise<InboxBulkResult>}
 */
export async function bulkMove(debateIds, targetCaseId) {
  if (!Array.isArray(debateIds) || debateIds.length === 0) {
    throw new TypeError('bulkMove: debateIds must be a non-empty array');
  }
  if (!targetCaseId || typeof targetCaseId !== 'string') {
    throw new TypeError('bulkMove: targetCaseId must be a non-empty string');
  }
  return request('/api/v1/inbox/bulk-move', {
    method: 'POST',
    body: JSON.stringify({ debate_ids: debateIds, target_case_id: targetCaseId }),
  });
}

/**
 * Add tags to one or more debates.  Empty ``tagIds`` is a 200 no-op.
 *
 * @param {string[]} debateIds
 * @param {string[]} tagIds
 * @returns {Promise<InboxBulkResult>}
 */
export async function bulkTag(debateIds, tagIds = []) {
  if (!Array.isArray(debateIds) || debateIds.length === 0) {
    throw new TypeError('bulkTag: debateIds must be a non-empty array');
  }
  if (!Array.isArray(tagIds)) {
    throw new TypeError('bulkTag: tagIds must be an array');
  }
  return request('/api/v1/inbox/bulk-tag', {
    method: 'POST',
    body: JSON.stringify({ debate_ids: debateIds, tag_ids: tagIds }),
  });
}

/**
 * Archive one or more debates (soft delete: status=archived).
 *
 * @param {string[]} debateIds
 * @returns {Promise<InboxBulkResult>}
 */
export async function bulkDelete(debateIds) {
  if (!Array.isArray(debateIds) || debateIds.length === 0) {
    throw new TypeError('bulkDelete: debateIds must be a non-empty array');
  }
  return request('/api/v1/inbox/bulk-delete', {
    method: 'POST',
    body: JSON.stringify({ debate_ids: debateIds }),
  });
}

/**
 * Detect whether a thrown error corresponds to a 404 from the
 * feature-gated Inbox endpoints.
 *
 * @param {unknown} err
 * @returns {boolean}
 */
export function isInboxDisabled(err) {
  if (!err) return false;
  const msg = String(err?.message ?? err);
  return /DANWA_ENABLE_CASE_SPACE_INBOX/.test(msg) || /\b404\b/.test(msg);
}
