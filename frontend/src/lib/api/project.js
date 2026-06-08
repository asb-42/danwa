/**
 * Project-related API functions (legacy — used only for move-to-project dialogs).
 *
 * @deprecated Projects are being replaced by tenants/cases.
 */

import { request } from './core.js';

/**
 * List all projects in the current tenant.
 * @deprecated Use tenant/case-scoped endpoints instead.
 */
export function getProjects() {
  return request('/api/v1/projects');
}
