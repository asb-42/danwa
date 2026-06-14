/**
 * Case-Space Workspace API — frontend wrapper.
 *
 * Two endpoints introduced in
 * ``plans/2026-06-14_case-space-workspace.md`` (Phase 1):
 *
 *   - ``GET /api/v1/workspace/summary?case_id=…``  → WorkspaceSummary
 *   - ``GET /api/v1/cases/search?q=…&limit=…``     → CaseSearchHit[]
 *
 * Both are feature-gated by ``settings.enable_case_space`` on the
 * backend; while the flag is False the endpoints return 404.  The
 * wrapper functions surface the 404 as a typed exception so the
 * frontend can fall back to the legacy Case list view.
 *
 * @see plans/2026-06-14_case-space-workspace.md
 */

import { request } from './core.js';

/**
 * @typedef {Object} WorkspaceRecentEvent
 * @property {string} id
 * @property {string} event_type
 * @property {string|null} actor
 * @property {string|null} subject
 * @property {string|null} case_id
 * @property {string} created_at   ISO-8601
 */

/**
 * @typedef {Object} WorkspaceSuggestedNextStep
 * @property {string} kind         e.g. "no_documents" | "no_debates" | "unlinked_documents"
 * @property {string} severity     "info" | "warning"
 * @property {string} message
 * @property {string} action_label
 * @property {string} action_target
 */

/**
 * @typedef {Object} WorkspaceSummary
 * @property {string} case_id
 * @property {string} tenant_id
 * @property {string} title
 * @property {string|null} description
 * @property {string} status
 * @property {string[]} tags
 * @property {string[]} members
 * @property {number} debate_count
 * @property {number} document_count
 * @property {WorkspaceRecentEvent[]} recent_events
 * @property {WorkspaceSuggestedNextStep[]} suggested_next_steps
 * @property {string} generated_at   ISO-8601
 */

/**
 * @typedef {Object} CaseSearchHit
 * @property {string} case_id
 * @property {string} tenant_id
 * @property {string} title
 * @property {string} status
 * @property {string[]} tags
 */

/**
 * Fetch the workspace summary for a case.
 *
 * @param {string} caseId
 * @returns {Promise<WorkspaceSummary>}
 * @throws {Error} 404 if the feature flag is off or the case is not visible
 */
export async function getWorkspaceSummary(caseId) {
  if (!caseId || typeof caseId !== 'string') {
    throw new TypeError('getWorkspaceSummary: caseId must be a non-empty string');
  }
  return request(`/api/v1/workspace/summary?case_id=${encodeURIComponent(caseId)}`);
}

/**
 * Typeahead search for the Case selector.
 *
 * Returns an empty list (not an error) for empty/whitespace queries,
 * and for backend failures (e.g. feature flag off → 404).  Callers
 * should treat a 404 specifically via {@link isCaseSpaceDisabled}.
 *
 * @param {string} q
 * @param {number} [limit=10]
 * @returns {Promise<CaseSearchHit[]>}
 */
export async function searchCases(q, limit = 10) {
  const needle = (q || '').trim();
  if (!needle) {
    return [];
  }
  const safeLimit = Math.max(1, Math.min(50, Number(limit) || 10));
  try {
    const res = await request(
      `/api/v1/cases/search?q=${encodeURIComponent(needle)}&limit=${safeLimit}`,
    );
    return Array.isArray(res) ? res : [];
  } catch (err) {
    // Feature-gate 404 or transient failure → empty result, not an error
    console.debug('[workspace] searchCases returned no results:', err?.message ?? err);
    return [];
  }
}

/**
 * Detect whether a thrown error corresponds to a 404 from the
 * feature-gated Case-Space endpoints.
 *
 * @param {unknown} err
 * @returns {boolean}
 */
export function isCaseSpaceDisabled(err) {
  if (!err) return false;
  const msg = String(err?.message ?? err);
  return /DANWA_ENABLE_CASE_SPACE/.test(msg) || /\b404\b/.test(msg);
}
