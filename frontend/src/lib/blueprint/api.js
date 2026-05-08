/**
 * Blueprint Canvas — API client functions.
 *
 * Follows the same request() pattern as the main api.js module.
 * All endpoints are under /api/v1/blueprints and /api/v1/canvas.
 */

import { request } from '../api.js';

// ─── LLM Profiles ──────────────────────────────────────────────────

/**
 * List all blueprint LLM profiles.
 * @param {{ limit?: number, offset?: number }} [opts]
 * @returns {Promise<Array>}
 */
export function listBlueprintLLMProfiles({ limit = 100, offset = 0 } = {}) {
  return request(
    `/api/v1/blueprints/llm-profiles?limit=${limit}&offset=${offset}`,
  );
}

/**
 * Get a single blueprint LLM profile by ID.
 * @param {string} profileId
 * @returns {Promise<Object>}
 */
export function getBlueprintLLMProfile(profileId) {
  return request(`/api/v1/blueprints/llm-profiles/${profileId}`);
}

/**
 * Create a new blueprint LLM profile.
 * @param {Object} profile
 * @returns {Promise<Object>}
 */
export function createBlueprintLLMProfile(profile) {
  return request('/api/v1/blueprints/llm-profiles', {
    method: 'POST',
    body: JSON.stringify(profile),
  });
}

/**
 * Update an existing blueprint LLM profile.
 * @param {string} profileId
 * @param {Object} profile
 * @returns {Promise<Object>}
 */
export function updateBlueprintLLMProfile(profileId, profile) {
  return request(`/api/v1/blueprints/llm-profiles/${profileId}`, {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
}

/**
 * Delete a blueprint LLM profile.
 * @param {string} profileId
 * @returns {Promise<void>}
 */
export function deleteBlueprintLLMProfile(profileId) {
  return request(`/api/v1/blueprints/llm-profiles/${profileId}`, {
    method: 'DELETE',
  });
}

// ─── Prompt Templates ───────────────────────────────────────────────

/**
 * List prompt templates with optional filtering.
 * @param {{ limit?: number, offset?: number, role?: string, variant?: string }} [opts]
 * @returns {Promise<Array>}
 */
export function listPromptTemplates(
  { limit = 100, offset = 0, role = null, variant = null } = {},
) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (role) params.set('role', role);
  if (variant) params.set('variant', variant);
  return request(`/api/v1/blueprints/prompt-templates?${params.toString()}`);
}

/**
 * Get a single prompt template by ID.
 * @param {string} templateId
 * @returns {Promise<Object>}
 */
export function getPromptTemplate(templateId) {
  return request(`/api/v1/blueprints/prompt-templates/${templateId}`);
}

/**
 * Create a new prompt template.
 * @param {Object} template
 * @returns {Promise<Object>}
 */
export function createPromptTemplate(template) {
  return request('/api/v1/blueprints/prompt-templates', {
    method: 'POST',
    body: JSON.stringify(template),
  });
}

/**
 * Update an existing prompt template.
 * @param {string} templateId
 * @param {Object} template
 * @returns {Promise<Object>}
 */
export function updatePromptTemplate(templateId, template) {
  return request(`/api/v1/blueprints/prompt-templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(template),
  });
}

/**
 * Delete a prompt template.
 * @param {string} templateId
 * @returns {Promise<void>}
 */
export function deletePromptTemplate(templateId) {
  return request(`/api/v1/blueprints/prompt-templates/${templateId}`, {
    method: 'DELETE',
  });
}

// ─── Role Definitions ───────────────────────────────────────────────

/**
 * List role definitions with optional filtering.
 * @param {{ limit?: number, offset?: number, role?: string }} [opts]
 * @returns {Promise<Array>}
 */
export function listRoleDefinitions(
  { limit = 100, offset = 0, role = null } = {},
) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (role) params.set('role', role);
  return request(
    `/api/v1/blueprints/role-definitions?${params.toString()}`,
  );
}

/**
 * Get a single role definition by ID.
 * @param {string} roleId
 * @returns {Promise<Object>}
 */
export function getRoleDefinition(roleId) {
  return request(`/api/v1/blueprints/role-definitions/${roleId}`);
}

/**
 * Create a new role definition.
 * @param {Object} roleDef
 * @returns {Promise<Object>}
 */
export function createRoleDefinition(roleDef) {
  return request('/api/v1/blueprints/role-definitions', {
    method: 'POST',
    body: JSON.stringify(roleDef),
  });
}

/**
 * Update an existing role definition.
 * @param {string} roleId
 * @param {Object} roleDef
 * @returns {Promise<Object>}
 */
export function updateRoleDefinition(roleId, roleDef) {
  return request(`/api/v1/blueprints/role-definitions/${roleId}`, {
    method: 'PUT',
    body: JSON.stringify(roleDef),
  });
}

/**
 * Delete a role definition.
 * @param {string} roleId
 * @returns {Promise<void>}
 */
export function deleteRoleDefinition(roleId) {
  return request(`/api/v1/blueprints/role-definitions/${roleId}`, {
    method: 'DELETE',
  });
}

// ─── Agent Blueprints ───────────────────────────────────────────────

/**
 * List agent blueprints with optional active-only filter.
 * @param {{ limit?: number, offset?: number, active_only?: boolean }} [opts]
 * @returns {Promise<Array>}
 */
export function listAgentBlueprints(
  { limit = 100, offset = 0, active_only = false } = {},
) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (active_only) params.set('active_only', 'true');
  return request(
    `/api/v1/blueprints/agent-blueprints?${params.toString()}`,
  );
}

/**
 * Get a single agent blueprint by ID.
 * @param {string} blueprintId
 * @returns {Promise<Object>}
 */
export function getAgentBlueprint(blueprintId) {
  return request(`/api/v1/blueprints/agent-blueprints/${blueprintId}`);
}

/**
 * Create a new agent blueprint.
 * @param {Object} blueprint
 * @returns {Promise<Object>}
 */
export function createAgentBlueprint(blueprint) {
  return request('/api/v1/blueprints/agent-blueprints', {
    method: 'POST',
    body: JSON.stringify(blueprint),
  });
}

/**
 * Update an existing agent blueprint.
 * @param {string} blueprintId
 * @param {Object} blueprint
 * @returns {Promise<Object>}
 */
export function updateAgentBlueprint(blueprintId, blueprint) {
  return request(`/api/v1/blueprints/agent-blueprints/${blueprintId}`, {
    method: 'PUT',
    body: JSON.stringify(blueprint),
  });
}

/**
 * Delete an agent blueprint.
 * @param {string} blueprintId
 * @returns {Promise<void>}
 */
export function deleteAgentBlueprint(blueprintId) {
  return request(`/api/v1/blueprints/agent-blueprints/${blueprintId}`, {
    method: 'DELETE',
  });
}

// ─── Canvas Layouts ─────────────────────────────────────────────────

/**
 * List canvas layouts with optional project filter.
 * @param {{ limit?: number, offset?: number, project_id?: string }} [opts]
 * @returns {Promise<Array>}
 */
export function listCanvasLayouts(
  { limit = 50, offset = 0, project_id = null } = {},
) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (project_id) params.set('project_id', project_id);
  return request(`/api/v1/canvas/layouts?${params.toString()}`);
}

/**
 * Get a single canvas layout by ID.
 * @param {string} layoutId
 * @returns {Promise<Object>}
 */
export function getCanvasLayout(layoutId) {
  return request(`/api/v1/canvas/layouts/${layoutId}`);
}

/**
 * Create a new canvas layout.
 * @param {Object} layout
 * @returns {Promise<Object>}
 */
export function createCanvasLayout(layout) {
  return request('/api/v1/canvas/layouts', {
    method: 'POST',
    body: JSON.stringify(layout),
  });
}

/**
 * Update an existing canvas layout.
 * @param {string} layoutId
 * @param {Object} layout
 * @returns {Promise<Object>}
 */
export function updateCanvasLayout(layoutId, layout) {
  return request(`/api/v1/canvas/layouts/${layoutId}`, {
    method: 'PUT',
    body: JSON.stringify(layout),
  });
}

/**
 * Delete a canvas layout.
 * @param {string} layoutId
 * @returns {Promise<void>}
 */
export function deleteCanvasLayout(layoutId) {
  return request(`/api/v1/canvas/layouts/${layoutId}`, {
    method: 'DELETE',
  });
}

// ─── Import ─────────────────────────────────────────────────────────

/**
 * Run the blueprint importer.
 * @param {{ dry_run?: boolean }} [opts]
 * @returns {Promise<{ created: number, updated: number, skipped: number, errors: string[] }>}
 */
export function runBlueprintImport({ dry_run = false } = {}) {
  return request('/api/v1/blueprints/import', {
    method: 'POST',
    body: JSON.stringify({ dry_run }),
  });
}

// ─── Role Types ────────────────────────────────────────────────────

/**
 * List all role types.
 * @param {{ limit?: number, offset?: number, active_only?: boolean }} [opts]
 * @returns {Promise<Array>}
 */
export function listRoleTypes({ limit = 100, offset = 0, active_only = false } = {}) {
  return request(
    `/api/v1/blueprints/role-types?limit=${limit}&offset=${offset}&active_only=${active_only}`,
  );
}

/**
 * Get a single role type by ID.
 * @param {string} roleTypeId
 * @returns {Promise<Object>}
 */
export function getRoleType(roleTypeId) {
  return request(`/api/v1/blueprints/role-types/${roleTypeId}`);
}

/**
 * Create a new role type.
 * @param {Object} roleType
 * @returns {Promise<Object>}
 */
export function createRoleType(roleType) {
  return request('/api/v1/blueprints/role-types', {
    method: 'POST',
    body: JSON.stringify(roleType),
  });
}

/**
 * Update an existing role type.
 * @param {string} roleTypeId
 * @param {Object} roleType
 * @returns {Promise<Object>}
 */
export function updateRoleType(roleTypeId, roleType) {
  return request(`/api/v1/blueprints/role-types/${roleTypeId}`, {
    method: 'PUT',
    body: JSON.stringify(roleType),
  });
}

/**
 * Delete a role type.
 * @param {string} roleTypeId
 * @returns {Promise<Object>}
 */
export function deleteRoleType(roleTypeId) {
  return request(`/api/v1/blueprints/role-types/${roleTypeId}`, {
    method: 'DELETE',
  });
}

// ─── Workflow Definitions ──────────────────────────────────────────

/**
 * List all workflow definitions.
 * @param {{ limit?: number, offset?: number }} [opts]
 * @returns {Promise<Array>}
 */
export function listWorkflowDefinitions({ limit = 50, offset = 0 } = {}) {
  return request(
    `/api/v1/blueprints/workflows?limit=${limit}&offset=${offset}`,
  );
}

/**
 * Get a single workflow definition by ID.
 * @param {string} wfId
 * @returns {Promise<Object>}
 */
export function getWorkflowDefinition(wfId) {
  return request(`/api/v1/blueprints/workflows/${wfId}`);
}

/**
 * Create a new workflow definition.
 * @param {Object} workflow
 * @returns {Promise<Object>}
 */
export function createWorkflowDefinition(workflow) {
  return request('/api/v1/blueprints/workflows', {
    method: 'POST',
    body: JSON.stringify(workflow),
  });
}

/**
 * Update an existing workflow definition.
 * @param {string} wfId
 * @param {Object} workflow
 * @returns {Promise<Object>}
 */
export function updateWorkflowDefinition(wfId, workflow) {
  return request(`/api/v1/blueprints/workflows/${wfId}`, {
    method: 'PUT',
    body: JSON.stringify(workflow),
  });
}

/**
 * Delete a workflow definition.
 * @param {string} wfId
 * @returns {Promise<Object>}
 */
export function deleteWorkflowDefinition(wfId) {
  return request(`/api/v1/blueprints/workflows/${wfId}`, {
    method: 'DELETE',
  });
}

/**
 * Compile a workflow definition — validate blueprint references.
 * @param {string} wfId
 * @returns {Promise<{ is_valid: boolean, resolved_agents: Array, errors: string[], warnings: string[] }>}
 */
export function compileWorkflow(wfId) {
  return request(`/api/v1/blueprints/workflows/${wfId}/compile`, {
    method: 'POST',
  });
}
