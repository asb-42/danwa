/**
 * Blueprint Canvas — Drag & Drop utilities.
 *
 * Handles coordinate transformation from screen space to Svelte Flow
 * canvas space, and creates draft nodes from palette drops.
 */

/**
 * Default data for each node type when creating a draft node.
 * @type {Record<string, object>}
 */
const DEFAULT_NODE_DATA = {
  'agent-blueprint': {
    name: 'New Agent Blueprint',
    description: '',
    llm_profile_id: '',
    role_definition_id: '',
    prompt_template_id: null,
    tags: [],
    is_active: true,
  },
  'llm-profile': {
    name: 'New LLM Profile',
    provider: 'openrouter',
    model: '',
    temperature: 0.7,
    max_tokens: 4096,
    api_base: null,
    api_key_env: null,
    a2a_endpoint: null,
  },
  'role-definition': {
    name: 'New Role Definition',
    role: 'strategist',
    description: '',
    prompt_template_id: null,
    max_rounds: 3,
    consensus_threshold: 0.7,
    tags: [],
  },
  'prompt-template': {
    name: 'New Prompt Template',
    role: 'strategist',
    variant: 'default',
    language: 'de',
    content: '',
    variables: [],
  },
  // Workflow node types (Phase 1)
  'wf-input': {
    label: 'Input',
  },
  'wf-initialize': {
    label: 'Initialize',
  },
  'wf-strategist': {
    label: 'Strategist',
    agent_blueprint_id: null,
  },
  'wf-critic': {
    label: 'Critic',
    agent_blueprint_id: null,
  },
  'wf-optimizer': {
    label: 'Optimizer',
    agent_blueprint_id: null,
  },
  'wf-moderator': {
    label: 'Moderator',
    agent_blueprint_id: null,
  },
  'wf-user-injection': {
    label: 'User Input',
    config: { input_type: 'user_query' },
  },
  'wf-fact-checker': {
    label: 'Fact Checker',
    agent_blueprint_id: null,
  },
  'wf-analyst': {
    label: 'Analyst',
    agent_blueprint_id: null,
  },
  'wf-creative': {
    label: 'Creative',
    agent_blueprint_id: null,
  },
  'wf-socratic-questioner': {
    label: 'Socratic Questioner',
    agent_blueprint_id: null,
  },
  'wf-expert-reviewer': {
    label: 'Expert Reviewer',
    agent_blueprint_id: null,
  },
  'wf-steel-manner': {
    label: 'Steel Manner',
    agent_blueprint_id: null,
  },
  'wf-devils-advocate': {
    label: "Devil's Advocate",
    agent_blueprint_id: null,
  },
  'wf-troll': {
    label: 'Troll',
    agent_blueprint_id: null,
  },
  'wf-mediator': {
    label: 'Mediator',
    agent_blueprint_id: null,
  },
  'wf-ethicist': {
    label: 'Ethicist',
    agent_blueprint_id: null,
  },
  'wf-synthesizer': {
    label: 'Synthesizer',
    agent_blueprint_id: null,
  },
  'wf-gate': {
    label: 'Gate',
    config: { condition: '' },
  },
  'wf-phase': {
    label: 'Debate Phase',
    config: { color: '#6366f1', max_rounds: 3, roles: [] },
  },
  'wf-agent': {
    label: 'Agent (Bundle)',
    bundle_id: null,
    role_type_icon: '\u{1F464}',
    role_type_name: '',
    role_type_color: '#8b5cf6',
  },
};

/**
 * Convert screen (client) coordinates to Svelte Flow canvas coordinates.
 *
 * @param {DragEvent} event - The drop event
 * @param {{ x: number, y: number, zoom: number }} viewport - Current viewport transform
 * @param {DOMRect} bounds - Bounding rect of the flow container element
 * @returns {{ x: number, y: number }}
 */
export function screenToFlowPosition(event, viewport, bounds) {
  return {
    x: (event.clientX - bounds.left - viewport.x) / viewport.zoom,
    y: (event.clientY - bounds.top - viewport.y) / viewport.zoom,
  };
}

/**
 * Create a draft node from a palette drop.
 *
 * @param {string} nodeType - The blueprint node type (e.g. 'agent-blueprint')
 * @param {{ x: number, y: number }} position - Canvas position
 * @returns {import('@xyflow/svelte').Node}
 */
export function createDraftNode(nodeType, position) {
  const id = `draft-${crypto.randomUUID().slice(0, 8)}`;
  return {
    id,
    type: nodeType,
    position,
    data: {
      isDraft: true,
      blueprint_id: id,
      ...getDefaultData(nodeType),
    },
  };
}

/**
 * Get default data for a node type.
 * @param {string} nodeType
 * @returns {object}
 */
export function getDefaultData(nodeType) {
  return { ...(DEFAULT_NODE_DATA[nodeType] || {}) };
}

/**
 * Sanitize entity data for SvelteFlow node storage.
 * Preserves all fields including content — UI freeze concerns
 * are handled by the form components, not by stripping data.
 */
function sanitizeNodeData(data) {
  if (!data) return {};
  return { ...data };
}

/**
 * Set up drag start data on a palette item.
 *
 * @param {DragEvent} event
 * @param {string} nodeType
 */
export function handlePaletteDragStart(event, nodeType) {
  if (!event.dataTransfer) return;
  event.dataTransfer.setData('application/blueprint-node-type', nodeType);
  event.dataTransfer.effectAllowed = 'move';
}

/**
 * Set up drag start data on an existing entity from the palette.
 *
 * @param {DragEvent} event
 * @param {string} nodeType - The node type (e.g. 'llm-profile')
 * @param {string} entityId - The entity's DB ID
 */
export function handleEntityDragStart(event, nodeType, entityId) {
  if (!event.dataTransfer) return;
  event.dataTransfer.setData('application/blueprint-node-type', nodeType);
  event.dataTransfer.setData('application/blueprint-entity-id', entityId);
  event.dataTransfer.effectAllowed = 'move';
}

/**
 * Extract the node type from a drop event.
 *
 * @param {DragEvent} event
 * @returns {string|null}
 */
export function getNodeTypeFromDrop(event) {
  return event.dataTransfer?.getData('application/blueprint-node-type') || null;
}

/**
 * Extract the entity ID from a drop event (if dropping an existing entity).
 *
 * @param {DragEvent} event
 * @returns {string|null}
 */
export function getEntityIdFromDrop(event) {
  return event.dataTransfer?.getData('application/blueprint-entity-id') || null;
}

/**
 * Create a node from an existing DB entity (non-draft).
 *
 * @param {string} nodeType - The blueprint node type
 * @param {string} entityId - The entity's DB ID
 * @param {object} entityData - The full entity data from the API
 * @param {{ x: number, y: number }} position - Canvas position
 * @returns {import('@xyflow/svelte').Node}
 */
export function createEntityNode(nodeType, entityId, entityData, position) {
  const id = `entity-${entityId}`;
  return {
    id,
    type: nodeType,
    position,
    data: {
      isDraft: false,
      blueprint_id: entityId,
      ...sanitizeNodeData(entityData),
    },
  };
}
