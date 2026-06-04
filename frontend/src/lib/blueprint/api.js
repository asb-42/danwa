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

/**
 * Convert a canvas layout to a WorkflowDefinition.
 * If the layout was previously converted, the existing workflow is updated.
 * @param {string} layoutId
 * @param {{ name?: string, description?: string, max_rounds?: number, consensus_threshold?: number }} [body]
 * @returns {Promise<import('./workflow_models.js').WorkflowDefinition>}
 */
export function convertLayoutToWorkflow(layoutId, body = {}) {
  return request(`/api/v1/canvas/layouts/${layoutId}/to-workflow`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ─── Argumentation Patterns ────────────────────────────────────

/**
 * List all available argumentation pattern names.
 * @returns {Promise<Array<string>>}
 */
export function listArgumentationPatterns() {
  return request('/api/v1/blueprints/argumentation-patterns');
}

// ─── Import ─────────────────────────────────────────────────────────

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

/**
 * Clone a workflow definition — creates a deep copy with a new ID.
 * @param {string} wfId
 * @returns {Promise<Object>}
 */
export function cloneWorkflow(wfId) {
  return request(`/api/v1/blueprints/workflows/${wfId}/clone`, {
    method: 'POST',
  });
}

// ─── Workflow Templates ────────────────────────────────────────────

/**
 * List all workflow templates with optional filtering.
 * @param {{ category?: string, limit?: number, offset?: number }} [opts]
 * @returns {Promise<Array>}
 */
export function listWorkflowTemplates({ category, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (category) params.set('category', category);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return request(`/api/v1/workflow-templates?${params.toString()}`);
}

/**
 * Get a single workflow template by ID.
 * @param {string} templateId
 * @returns {Promise<Object>}
 */
export function getWorkflowTemplate(templateId) {
  return request(`/api/v1/workflow-templates/${templateId}`);
}

/**
 * Create a new custom workflow template.
 * @param {Object} template
 * @returns {Promise<Object>}
 */
export function createWorkflowTemplate(template) {
  return request('/api/v1/workflow-templates', {
    method: 'POST',
    body: JSON.stringify(template),
  });
}

/**
 * Update an existing workflow template.
 * @param {string} templateId
 * @param {Object} template
 * @returns {Promise<Object>}
 */
export function updateWorkflowTemplate(templateId, template) {
  return request(`/api/v1/workflow-templates/${templateId}`, {
    method: 'PUT',
    body: JSON.stringify(template),
  });
}

/**
 * Delete a workflow template.
 * @param {string} templateId
 * @returns {Promise<void>}
 */
export function deleteWorkflowTemplate(templateId) {
  return request(`/api/v1/workflow-templates/${templateId}`, {
    method: 'DELETE',
  });
}

/**
 * Instantiate a workflow template into a concrete WorkflowDefinition.
 * @param {string} templateId
 * @param {{ name?: string, placeholder_values: Object }} body
 * @returns {Promise<Object>}
 */
export function instantiateWorkflowTemplate(templateId, body) {
  return request(`/api/v1/workflow-templates/${templateId}/instantiate`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Save an existing workflow as a custom template.
 * @param {string} wfId
 * @param {{ name: string, description?: string, extracted_placeholders?: string[] }} body
 * @returns {Promise<Object>}
 */
export function saveWorkflowAsTemplate(wfId, body) {
  return request(`/api/v1/blueprints/workflows/${wfId}/save-as-template`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ─── Agent Bundles ──────────────────────────────────────────────────

/**
 * List all agent bundles.
 * @param {{ limit?: number, offset?: number, active_only?: boolean }} [opts]
 * @returns {Promise<Array>}
 */
export function listAgentBundles({ limit = 100, offset = 0, active_only = false } = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (active_only) params.set('active_only', 'true');
  return request(`/api/v1/blueprints/bundles?${params.toString()}`);
}

/**
 * Get a single agent bundle by ID.
 * @param {string} bundleId
 * @returns {Promise<Object>}
 */
export function getAgentBundle(bundleId) {
  return request(`/api/v1/blueprints/bundles/${bundleId}`);
}

/**
 * Create a new agent bundle.
 * @param {Object} bundle
 * @returns {Promise<Object>}
 */
export function createAgentBundle(bundle) {
  return request('/api/v1/blueprints/bundles', {
    method: 'POST',
    body: JSON.stringify(bundle),
  });
}

/**
 * Update an existing agent bundle.
 * @param {string} bundleId
 * @param {Object} bundle
 * @returns {Promise<Object>}
 */
export function updateAgentBundle(bundleId, bundle) {
  return request(`/api/v1/blueprints/bundles/${bundleId}`, {
    method: 'PUT',
    body: JSON.stringify(bundle),
  });
}

/**
 * Delete an agent bundle.
 * @param {string} bundleId
 * @returns {Promise<void>}
 */
export function deleteAgentBundle(bundleId) {
  return request(`/api/v1/blueprints/bundles/${bundleId}`, {
    method: 'DELETE',
  });
}

/**
 * Resolve an agent bundle — returns full config with all references.
 * @param {string} bundleId
 * @returns {Promise<Object>}
 */
export function resolveAgentBundle(bundleId) {
  return request(`/api/v1/blueprints/bundles/${bundleId}/resolve`);
}

// ─── Tone Profiles ───────────────────────────────────────────────

/**
 * List all tone profiles.
 * @param {{ include_system?: boolean, limit?: number, offset?: number }} [opts]
 * @returns {Promise<Array>}
 */
export function listToneProfiles({ includeSystem = true, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({
    include_system: String(includeSystem),
    limit: String(limit),
    offset: String(offset),
  });
  return request(`/api/v1/tone-profiles?${params.toString()}`);
}

/**
 * Get a single tone profile by ID.
 * @param {string} profileId
 * @returns {Promise<Object>}
 */
export function getToneProfile(profileId) {
  return request(`/api/v1/tone-profiles/${profileId}`);
}

/**
 * Create a new tone profile.
 * @param {Object} profile
 * @returns {Promise<Object>}
 */
export function createToneProfile(profile) {
  return request('/api/v1/tone-profiles', {
    method: 'POST',
    body: JSON.stringify(profile),
  });
}

/**
 * Update an existing tone profile.
 * @param {string} profileId
 * @param {Object} profile
 * @returns {Promise<Object>}
 */
export function updateToneProfile(profileId, profile) {
  return request(`/api/v1/tone-profiles/${profileId}`, {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
}

/**
 * Delete a tone profile.
 * @param {string} profileId
 * @returns {Promise<void>}
 */
export function deleteToneProfile(profileId) {
  return request(`/api/v1/tone-profiles/${profileId}`, {
    method: 'DELETE',
  });
}

// ─── Bundle Composer ───────────────────────────────────────────────

/**
 * List all available composer components (agent cores, arg patterns,
 * tone profiles, prompt modifiers, LLM profiles).
 * @returns {Promise<Object>}
 */
export function listComposerComponents() {
  return request('/api/v1/bundle-composer/components');
}

/**
 * Preview the assembled system prompt from component selection.
 * @param {{ agent_core_id?: string, argumentation_pattern_id?: string, tone_profile_id?: string, prompt_modifier_id?: string }} composition
 * @returns {Promise<{prompt: string}>}
 */
export function previewComposition(composition) {
  return request('/api/v1/bundle-composer/preview', {
    method: 'POST',
    body: JSON.stringify(composition),
  });
}

/**
 * Create a new composer-based agent bundle.
 * @param {{ name: string, composition: Object, description?: string, llm_profile_id?: string }} bundle
 * @returns {Promise<Object>}
 */
export function createComposerBundle(bundle) {
  return request('/api/v1/bundle-composer/bundles', {
    method: 'POST',
    body: JSON.stringify(bundle),
  });
}

/**
 * Update an existing composer bundle.
 * @param {string} bundleId
 * @param {{ name?: string, composition?: Object, description?: string, llm_profile_id?: string }} bundle
 * @returns {Promise<Object>}
 */
export function updateComposerBundle(bundleId, bundle) {
  return request(`/api/v1/bundle-composer/bundles/${bundleId}`, {
    method: 'PUT',
    body: JSON.stringify(bundle),
  });
}

/**
 * Get a single composer bundle by ID.
 * @param {string} bundleId
 * @returns {Promise<Object>}
 */
export function getComposerBundle(bundleId) {
  return request(`/api/v1/bundle-composer/bundles/${bundleId}`);
}

/**
 * List all composer bundles.
 * @param {{ limit?: number, offset?: number, active_only?: boolean }} [opts]
 * @returns {Promise<Array>}
 */
export function listComposerBundles({ limit = 100, offset = 0, active_only = false } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (active_only) params.set('active_only', 'true');
  return request(`/api/v1/bundle-composer/bundles?${params.toString()}`);
}

/**
 * Export a composer bundle as manifest + profile.
 * @param {string} bundleId
 * @param {boolean} [to_directory=false] Write to modules/agent-bundles/ on disk
 * @returns {Promise<Object>}
 */
export function exportComposerBundle(bundleId, to_directory = false) {
  return request(`/api/v1/bundle-composer/bundles/${bundleId}/export?to_directory=${to_directory}`, {
    method: 'POST',
  });
}

/**
 * Import a composer bundle from modules/agent-bundles/<module_id>/.
 * @param {string} moduleId
 * @returns {Promise<Object>}
 */
export function importComposerBundle(moduleId) {
  return request('/api/v1/bundle-composer/import', {
    method: 'POST',
    body: JSON.stringify({ module_id: moduleId }),
  });
}
