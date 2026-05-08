/**
 * Blueprint Canvas — Edge connection validation.
 *
 * Defines which node types can connect to which, and maps
 * source→target pairs to semantic edge types.
 * Supports both Blueprint Mode (semantic edges only) and
 * Workflow Mode (semantic + control flow edges).
 */

import { getNodeRegistration } from './registry.js';

/**
 * Valid outgoing connections per source node type (semantic/asset edges).
 * Keys are source node types, values are arrays of allowed target types.
 * @type {Record<string, string[]>}
 */
export const VALID_CONNECTIONS = {
  'agent-blueprint': ['llm-profile', 'role-definition', 'prompt-template'],
  'role-definition': ['prompt-template'],
  'role-type': ['role-definition'],
  // llm-profile and prompt-template have no outgoing edges
};

/**
 * Maps "sourceType→targetType" to the semantic edge type.
 * @type {Record<string, string>}
 */
export const EDGE_TYPE_MAP = {
  'agent-blueprint→llm-profile': 'uses_llm',
  'agent-blueprint→role-definition': 'implements_role',
  'agent-blueprint→prompt-template': 'overrides_prompt',
  'role-definition→prompt-template': 'prompted_by',
  'role-type→role-definition': 'defines_role',
};

/**
 * Edge type display metadata (color, style, label).
 * @type {Record<string, { color: string, style: string, label: string }>}
 */
export const EDGE_STYLES = {
  uses_llm: { color: '#3b82f6', style: 'solid', label: 'Uses LLM' },
  implements_role: { color: '#8b5cf6', style: 'solid', label: 'Implements Role' },
  prompted_by: { color: '#10b981', style: 'dashed', label: 'Prompted By' },
  overrides_prompt: { color: '#f59e0b', style: 'dotted', label: 'Overrides Prompt' },
  defines_role: { color: '#ec4899', style: 'solid', label: 'Defines Role' },
  sequential: { color: '#6366f1', style: 'solid', label: 'Sequential' },
  conditional: { color: '#f59e0b', style: 'dashed', label: 'Conditional' },
  interjection: { color: '#f43f5e', style: 'dotted', label: 'Interjection' },
};

/**
 * Validate whether a connection between two node types is allowed.
 *
 * In Blueprint Mode, only semantic edges are allowed.
 * In Workflow Mode, both semantic and control flow edges are allowed.
 *
 * @param {string} sourceType - The source node type (e.g. 'agent-blueprint')
 * @param {string} targetType - The target node type (e.g. 'llm-profile')
 * @param {'blueprint'|'workflow'} [currentMode='blueprint'] - Current canvas mode
 * @returns {{ valid: boolean, edgeType?: string, reason?: string }}
 */
export function validateConnection(sourceType, targetType, currentMode = 'blueprint') {
  // In blueprint mode, only semantic edges allowed
  if (currentMode === 'blueprint') {
    return validateSemanticConnection(sourceType, targetType);
  }

  // In workflow mode, try semantic first, then control flow
  const semantic = validateSemanticConnection(sourceType, targetType);
  if (semantic.valid) return semantic;

  return validateControlFlowConnection(sourceType, targetType);
}

/**
 * Validate a semantic (asset) connection.
 * @param {string} sourceType
 * @param {string} targetType
 * @returns {{ valid: boolean, edgeType?: string, reason?: string }}
 */
function validateSemanticConnection(sourceType, targetType) {
  const allowedTargets = VALID_CONNECTIONS[sourceType];

  if (!allowedTargets) {
    return {
      valid: false,
      reason: `Node type "${sourceType}" cannot have outgoing connections`,
    };
  }

  if (!allowedTargets.includes(targetType)) {
    return {
      valid: false,
      reason: `Cannot connect "${sourceType}" to "${targetType}"`,
    };
  }

  const key = `${sourceType}→${targetType}`;
  const edgeType = EDGE_TYPE_MAP[key];

  return { valid: true, edgeType };
}

/**
 * Validate a control flow (workflow) connection.
 * Workflow nodes can connect sequentially to other workflow nodes.
 * @param {string} sourceType
 * @param {string} targetType
 * @returns {{ valid: boolean, edgeType?: string, reason?: string }}
 */
function validateControlFlowConnection(sourceType, targetType) {
  const sourceReg = getNodeRegistration(sourceType);
  const targetReg = getNodeRegistration(targetType);

  if (sourceReg?.category === 'workflow' && targetReg?.category === 'workflow') {
    return { valid: true, edgeType: 'sequential' };
  }

  return { valid: false, reason: 'invalid_control_flow' };
}

/**
 * Get the edge type for a valid connection.
 * Returns null if the connection is invalid.
 *
 * @param {string} sourceType
 * @param {string} targetType
 * @returns {string|null}
 */
export function getEdgeType(sourceType, targetType) {
  const key = `${sourceType}→${targetType}`;
  return EDGE_TYPE_MAP[key] || null;
}

/**
 * Check if a node type can have outgoing connections.
 * @param {string} nodeType
 * @returns {boolean}
 */
export function canHaveOutgoing(nodeType) {
  return nodeType in VALID_CONNECTIONS;
}

/**
 * Check if a node type can have incoming connections.
 * All node types can receive incoming connections.
 * @param {string} nodeType
 * @returns {boolean}
 */
export function canHaveIncoming(nodeType) {
  return true;
}
