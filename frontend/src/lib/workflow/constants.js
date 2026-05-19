/**
 * Workflow Constants — Shared between mapper, graphReducer, and layout.
 *
 * Defines the canonical agent pipeline order. This is the single source
 * of truth for which roles exist and in what order they execute.
 *
 * The pipeline order is derived from the backend's default debate
 * configuration. A2A agents (custom roles not in this list) run after
 * all standard agents and receive the moderator's output as input.
 */

/**
 * Standard pipeline roles in execution order.
 * Used for:
 * - Edge creation in graphReducer (connects each agent to its predecessor)
 * - Artifact input resolution in mapper.js
 * - Initial node positioning in getInitialPosition()
 */
export const PIPELINE_ROLES = [
  'strategist',
  'critic',
  'fact-checker',
  'optimizer',
  'moderator',
  'analyst',
  'creative',
];

/**
 * Map artifact types back to their producing pipeline role.
 * Inverse of mapRoleToArtifactType().
 */
export const ARTIFACT_ROLE_MAP = {
  strategy: 'strategist',
  critique: 'critic',
  'fact-check': 'fact-checker',
  analysis: 'analyst',
  creative: 'creative',
  synthesis: 'optimizer',
  consensus: 'moderator',
};

/**
 * Map agent roles to their artifact type names.
 */
export const ROLE_ARTIFACT_MAP = {
  strategist: 'strategy',
  critic: 'critique',
  'fact-checker': 'fact-check',
  analyst: 'analysis',
  creative: 'creative',
  optimizer: 'synthesis',
  moderator: 'consensus',
};

/**
 * Check if a role is part of the standard pipeline.
 * @param {string} role
 * @returns {boolean}
 */
export function isPipelineRole(role) {
  return PIPELINE_ROLES.includes(role);
}

/**
 * Get the index of a role in the pipeline order.
 * Returns -1 for unknown/A2A roles.
 * @param {string} role
 * @returns {number}
 */
export function getPipelineIndex(role) {
  return PIPELINE_ROLES.indexOf(role);
}

/**
 * Get the previous role in the pipeline (or null if this is the first).
 * @param {string} role
 * @returns {string|null}
 */
export function getPreviousPipelineRole(role) {
  const idx = getPipelineIndex(role);
  return idx > 0 ? PIPELINE_ROLES[idx - 1] : null;
}
