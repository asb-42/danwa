/**
 * Blueprint Canvas — Edge-to-Backend Wiring.
 *
 * When semantic edges are created or deleted on the canvas,
 * this module translates them into backend API calls that update
 * the corresponding FK fields on the target entities.
 *
 * Semantic edge types and their FK mappings:
 *   defines_role    : RoleType       → RoleDefinition  → role_type_id
 *   implements_role : RoleDefinition  → AgentBlueprint  → role_definition_id
 *   uses_llm        : LLMProfile     → AgentBlueprint  → llm_profile_id
 *   prompted_by     : PromptTemplate  → RoleDefinition  → prompt_template_id
 *   overrides_prompt: PromptTemplate  → AgentBlueprint  → prompt_template_id
 */

import {
  updateRoleDefinition,
  updateAgentBlueprint,
  getRoleDefinition,
  getAgentBlueprint,
} from './api.js';

/**
 * @typedef {Object} EdgeWiringConfig
 * @property {string} fkField - The FK field name on the target entity
 * @property {*} defaultFk - Default value when disconnecting
 * @property {(sourceId: string, targetId: string) => Promise<Object|null>} wire - API call on connect
 * @property {(targetId: string) => Promise<Object|null>} unwire - API call on disconnect
 */

/** @type {Record<string, EdgeWiringConfig>} */
const EDGE_WIRING = {
  defines_role: {
    fkField: 'role_type_id',
    defaultFk: 'strategist',
    async wire(sourceId, targetId) {
      const target = await getRoleDefinition(targetId);
      if (!target) return null;
      return updateRoleDefinition(targetId, {
        ...target,
        role_type_id: sourceId,
      });
    },
    async unwire(targetId) {
      const target = await getRoleDefinition(targetId);
      if (!target) return null;
      return updateRoleDefinition(targetId, {
        ...target,
        role_type_id: 'strategist',
      });
    },
  },

  implements_role: {
    fkField: 'role_definition_id',
    defaultFk: null,
    async wire(sourceId, targetId) {
      const target = await getAgentBlueprint(targetId);
      if (!target) return null;
      return updateAgentBlueprint(targetId, {
        ...target,
        role_definition_id: sourceId,
      });
    },
    async unwire(targetId) {
      const target = await getAgentBlueprint(targetId);
      if (!target) return null;
      return updateAgentBlueprint(targetId, {
        ...target,
        role_definition_id: '',
      });
    },
  },

  uses_llm: {
    fkField: 'llm_profile_id',
    defaultFk: null,
    async wire(sourceId, targetId) {
      const target = await getAgentBlueprint(targetId);
      if (!target) return null;
      return updateAgentBlueprint(targetId, {
        ...target,
        llm_profile_id: sourceId,
      });
    },
    async unwire(targetId) {
      const target = await getAgentBlueprint(targetId);
      if (!target) return null;
      return updateAgentBlueprint(targetId, {
        ...target,
        llm_profile_id: '',
      });
    },
  },

  prompted_by: {
    fkField: 'prompt_template_id',
    defaultFk: null,
    async wire(sourceId, targetId) {
      const target = await getRoleDefinition(targetId);
      if (!target) return null;
      return updateRoleDefinition(targetId, {
        ...target,
        prompt_template_id: sourceId,
      });
    },
    async unwire(targetId) {
      const target = await getRoleDefinition(targetId);
      if (!target) return null;
      return updateRoleDefinition(targetId, {
        ...target,
        prompt_template_id: null,
      });
    },
  },

  overrides_prompt: {
    fkField: 'prompt_template_id',
    defaultFk: null,
    async wire(sourceId, targetId) {
      const target = await getAgentBlueprint(targetId);
      if (!target) return null;
      return updateAgentBlueprint(targetId, {
        ...target,
        prompt_template_id: sourceId,
      });
    },
    async unwire(targetId) {
      const target = await getAgentBlueprint(targetId);
      if (!target) return null;
      return updateAgentBlueprint(targetId, {
        ...target,
        prompt_template_id: null,
      });
    },
  },
};

/**
 * Wire a semantic edge — update the target entity's FK in the backend.
 *
 * @param {import('@xyflow/svelte').Edge} edge - The edge being created
 * @param {import('@xyflow/svelte').Node[]} nodes - Current canvas nodes
 * @param {(nodeId: string, data: Record<string, any>) => void} updateNodeData - Store method
 * @returns {Promise<boolean>} true if wired successfully
 */
export async function wireEdgeOnConnect(edge, nodes, updateNodeData) {
  const wiring = EDGE_WIRING[edge.type];
  if (!wiring) return false;

  const sourceNode = nodes.find((n) => n.id === edge.source);
  const targetNode = nodes.find((n) => n.id === edge.target);
  if (!sourceNode || !targetNode) return false;

  const sourceId = sourceNode.data?.blueprint_id || sourceNode.id;
  const targetId = targetNode.data?.blueprint_id || targetNode.id;

  try {
    const result = await wiring.wire(sourceId, targetId);
    if (result) {
      updateNodeData(targetNode.id, { [wiring.fkField]: sourceId });
      return true;
    }
    return false;
  } catch (err) {
    console.error(`[edgeWiring] Failed to wire ${edge.type}:`, err);
    return false;
  }
}

/**
 * Unwire a semantic edge — reset the target entity's FK in the backend.
 *
 * @param {import('@xyflow/svelte').Edge} edge - The edge being removed
 * @param {import('@xyflow/svelte').Node[]} nodes - Current canvas nodes
 * @param {(nodeId: string, data: Record<string, any>) => void} updateNodeData - Store method
 * @returns {Promise<boolean>} true if unwired successfully
 */
export async function wireEdgeOnDisconnect(edge, nodes, updateNodeData) {
  const wiring = EDGE_WIRING[edge.type];
  if (!wiring) return false;

  const targetNode = nodes.find((n) => n.id === edge.target);
  if (!targetNode) return false;

  const targetId = targetNode.data?.blueprint_id || targetNode.id;

  try {
    const result = await wiring.unwire(targetId);
    if (result) {
      updateNodeData(targetNode.id, { [wiring.fkField]: wiring.defaultFk });
      return true;
    }
    return false;
  } catch (err) {
    console.error(`[edgeWiring] Failed to unwire ${edge.type}:`, err);
    return false;
  }
}

/**
 * Check if an edge type is a semantic edge that requires backend wiring.
 * @param {string} edgeType
 * @returns {boolean}
 */
export function isSemanticEdge(edgeType) {
  return edgeType in EDGE_WIRING;
}
