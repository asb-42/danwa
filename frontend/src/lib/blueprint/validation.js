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
 * Legacy types (agent-blueprint, role-definition, role-type, prompt-template)
 * removed — only llm-profile, agent-core, and tone-profile remain as assets.
 * @type {Record<string, string[]>}
 */
export const VALID_CONNECTIONS = {};

/**
 * Maps "sourceType→targetType" to the semantic edge type.
 * @type {Record<string, string>}
 */
export const EDGE_TYPE_MAP = {};

/**
 * Edge type display metadata (color, style, label).
 * @type {Record<string, { color: string, style: string, label: string }>}
 */
export const EDGE_STYLES = {
  uses_llm: { color: '#3b82f6', style: 'solid', label: 'Uses LLM' },
  uses_core: { color: '#0d9488', style: 'solid', label: 'Uses Core' },
  uses_tone: { color: '#f59e0b', style: 'solid', label: 'Uses Tone' },
  sequential: { color: '#6366f1', style: 'solid', label: 'Sequential' },
  conditional: { color: '#f59e0b', style: 'dashed', label: 'Conditional' },
  interjection: { color: '#f43f5e', style: 'dotted', label: 'Interjection' },
  feedback: { color: '#10b981', style: 'dash-dot', label: 'Feedback' },
  injects_config: { color: '#f59e0b', style: 'dashed', label: 'Injects Config' },
  builds_upon: { color: '#22c55e', style: 'dashed', label: 'Builds Upon' },
  validates: { color: '#64748b', style: 'solid', label: 'Validates' },
  decision: { color: '#f59e0b', style: 'dashed', label: 'Decision' },
};

/**
 * Allowed outgoing connections per workflow node type.
 * Keys are source node types, values are arrays of allowed target types.
 * @type {Record<string, string[]>}
 */
export const WORKFLOW_CONNECTION_RULES = {
  'wf-input': ['wf-initialize', 'wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-tone-profile'],
  'wf-initialize': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-tone-profile'],
  'wf-strategist': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-critic': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-builder', 'wf-angels-advocate', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-optimizer': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-moderator': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-builder', 'wf-gate', 'wf-tone-profile'],
  'wf-user-injection': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-tone-profile'],
  'wf-gate': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-user-injection', 'wf-gate', 'wf-tone-profile'],
  'wf-tone-profile': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-initialize', 'wf-gate', 'wf-user-injection'],
  'wf-analyst': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-creative': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-socratic-questioner': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-expert-reviewer': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-steel-manner': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-devils-advocate': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-troll': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-mediator': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-ethicist': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-synthesizer': ['wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-user-injection', 'wf-tone-profile'],
  'wf-phase': ['wf-phase', 'wf-input', 'wf-initialize', 'wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-gate', 'wf-tone-profile'],
  'wf-angels-advocate': ['wf-builder', 'wf-moderator', 'wf-critic', 'wf-gate', 'wf-tone-profile'],
  'wf-builder': ['wf-pragmatist', 'wf-moderator', 'wf-critic', 'wf-angels-advocate', 'wf-gate', 'wf-tone-profile'],
  'wf-pragmatist': ['wf-moderator', 'wf-builder', 'wf-critic', 'wf-angels-advocate', 'wf-gate', 'wf-tone-profile'],
};

/**
 * Agent node types that can receive injects_config edges from tone_profile nodes.
 * @type {string[]}
 */
export const INJECTABLE_AGENT_TYPES = [
  'wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator',
  'wf-analyst', 'wf-creative', 'wf-fact-checker',
  'wf-socratic-questioner', 'wf-expert-reviewer', 'wf-steel-manner',
  'wf-devils-advocate', 'wf-troll', 'wf-mediator', 'wf-ethicist', 'wf-synthesizer',
  'wf-builder', 'wf-pragmatist', 'wf-angels-advocate',
];

/**
 * Check if a source→target connection should use injects_config edge type.
 * @param {string} sourceType
 * @param {string} targetType
 * @param {string} sourceHandleId - The handle ID from the source port
 * @returns {boolean}
 */
export function isInjectsConfigConnection(sourceType, targetType, sourceHandleId) {
  return sourceType === 'wf-tone-profile' && INJECTABLE_AGENT_TYPES.includes(targetType);
}

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

  if (sourceReg?.category !== 'workflow' || targetReg?.category !== 'workflow') {
    return { valid: false, reason: 'invalid_control_flow' };
  }

  const allowedTargets = WORKFLOW_CONNECTION_RULES[sourceType];
  if (allowedTargets && allowedTargets.includes(targetType)) {
    return { valid: true, edgeType: getWorkflowEdgeType(sourceType, targetType) };
  }

  return { valid: false, reason: `Cannot connect "${sourceType}" to "${targetType}"` };
}

/**
 * Determine the workflow edge type based on source and target node types.
 * @param {string} sourceType
 * @param {string} targetType
 * @returns {string}
 */
export function getWorkflowEdgeType(sourceType, targetType) {
  // Tone profile → agent = injects_config
  if (sourceType === 'wf-tone-profile' && INJECTABLE_AGENT_TYPES.includes(targetType)) {
    return 'injects_config';
  }
  // Moderator → agent = feedback loop
  if (sourceType === 'wf-moderator' && targetType !== 'wf-gate') {
    return 'feedback';
  }
  // Gate → any = conditional
  if (sourceType === 'wf-gate') {
    return 'conditional';
  }
  // User injection → any = interjection
  if (sourceType === 'wf-user-injection') {
    return 'interjection';
  }
  // Critic → Angel's Advocate = sequential
  if (sourceType === 'wf-critic' && targetType === 'wf-angels-advocate') {
    return 'sequential';
  }
  // Angel's Advocate → Builder = builds_upon
  if (sourceType === 'wf-angels-advocate' && targetType === 'wf-builder') {
    return 'builds_upon';
  }
  // Critic → Builder = builds_upon
  if (sourceType === 'wf-critic' && targetType === 'wf-builder') {
    return 'builds_upon';
  }
  // Builder → Pragmatist = validates
  if (sourceType === 'wf-builder' && targetType === 'wf-pragmatist') {
    return 'validates';
  }
  // Moderator → Builder = decision (revision loop)
  if (sourceType === 'wf-moderator' && targetType === 'wf-builder') {
    return 'decision';
  }
  return 'sequential';
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
