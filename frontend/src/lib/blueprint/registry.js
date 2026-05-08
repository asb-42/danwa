/**
 * Blueprint Canvas — Central node type registry.
 *
 * Replaces hardcoded nodeTypes/edgeTypes maps with a central,
 * extensible registry. Each entry defines: type name, Svelte component,
 * category, backend schema reference, icon, i18n label key, and active state.
 *
 * @module registry
 */

/**
 * @typedef {Object} NodeRegistration
 * @property {string} type - Unique type identifier (e.g. 'agent-blueprint')
 * @property {import('svelte').Component} component - Svelte component for rendering
 * @property {'asset'|'workflow'} category - Palette category
 * @property {string} schemaRef - Pydantic model name in backend
 * @property {string} icon - Emoji icon for palette display
 * @property {string} labelKey - i18n translation key for label
 * @property {Function} defaultData - Factory function returning default node data
 * @property {boolean} active - Whether the node type is currently usable
 */

/**
 * @typedef {Object} EdgeRegistration
 * @property {string} type - Unique edge type identifier
 * @property {import('svelte').Component} component - Svelte component for rendering
 * @property {'semantic'|'control_flow'} category - Edge category
 */

/** @type {Map<string, NodeRegistration>} */
const nodes = new Map();

/** @type {Map<string, EdgeRegistration>} */
const edges = new Map();

/**
 * Register a node type configuration.
 * @param {NodeRegistration} config
 */
export function registerNode(config) {
  nodes.set(config.type, config);
}

/**
 * Register an edge type configuration.
 * @param {EdgeRegistration} config
 */
export function registerEdge(config) {
  edges.set(config.type, config);
}

/**
 * Get a single node registration by type.
 * @param {string} type
 * @returns {NodeRegistration|undefined}
 */
export function getNodeRegistration(type) {
  return nodes.get(type);
}

/**
 * Get a single edge registration by type.
 * @param {string} type
 * @returns {EdgeRegistration|undefined}
 */
export function getEdgeRegistration(type) {
  return edges.get(type);
}

/**
 * Get all node registrations filtered by category.
 * @param {'asset'|'workflow'} category
 * @returns {NodeRegistration[]}
 */
export function getNodesByCategory(category) {
  return [...nodes.values()].filter((n) => n.category === category);
}

/**
 * Get all edge registrations filtered by category.
 * @param {'semantic'|'control_flow'} category
 * @returns {EdgeRegistration[]}
 */
export function getEdgesByCategory(category) {
  return [...edges.values()].filter((e) => e.category === category);
}

/**
 * Build the nodeTypes map for SvelteFlow.
 * @returns {Record<string, import('svelte').Component>}
 */
export function getNodeTypes() {
  return Object.fromEntries(
    [...nodes.entries()].map(([k, v]) => [k, v.component]),
  );
}

/**
 * Build the edgeTypes map for SvelteFlow.
 * @returns {Record<string, import('svelte').Component>}
 */
export function getEdgeTypes() {
  return Object.fromEntries(
    [...edges.entries()].map(([k, v]) => [k, v.component]),
  );
}

/**
 * Get all registered node configurations.
 * @returns {NodeRegistration[]}
 */
export function getAllRegisteredNodes() {
  return [...nodes.values()];
}

/**
 * Get all registered edge configurations.
 * @returns {EdgeRegistration[]}
 */
export function getAllRegisteredEdges() {
  return [...edges.values()];
}
