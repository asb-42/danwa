/**
 * Case-Space Onboarding API — frontend wrapper.
 *
 * One endpoint introduced in
 * ``plans/2026-06-14_case-space-workspace.md`` (Phase 3):
 *
 *   - ``GET /api/v1/onboarding/state?tenant_id=…`` → OnboardingState
 *
 * @see plans/2026-06-14_case-space-workspace.md
 */

import { request } from './core.js';

/**
 * @typedef {Object} OnboardingState
 * @property {string}  tenant_id
 * @property {boolean} has_cases
 * @property {boolean} has_documents
 * @property {boolean} has_debates
 */

/**
 * Fetch the onboarding state for a tenant.  Never throws; returns
 * a "blank" state on failure so the Welcome-Card renders with
 * all three cards hidden rather than crashing the dashboard.
 *
 * @param {string} tenantId
 * @returns {Promise<OnboardingState>}
 */
export async function getOnboardingState(tenantId) {
  if (!tenantId || typeof tenantId !== 'string') {
    return { tenant_id: '', has_cases: false, has_documents: false, has_debates: false };
  }
  try {
    return await request(`/api/v1/onboarding/state?tenant_id=${encodeURIComponent(tenantId)}`);
  } catch {
    return { tenant_id: tenantId, has_cases: false, has_documents: false, has_debates: false };
  }
}
