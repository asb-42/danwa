/**
 * Blueprint Canvas — Register all node and edge types.
 *
 * Called once at app initialization to populate the central registry
 * with all asset nodes (Phase 3) and workflow nodes (Phase 4 placeholders).
 *
 * @module registerAll
 */

import { registerNode, registerEdge } from './registry.js';

// Asset node components (Phase 3)
import AgentBlueprintNode from '../../components/blueprint/nodes/AgentBlueprintNode.svelte';
import LLMProfileNode from '../../components/blueprint/nodes/LLMProfileNode.svelte';
import RoleDefinitionNode from '../../components/blueprint/nodes/RoleDefinitionNode.svelte';
import PromptTemplateNode from '../../components/blueprint/nodes/PromptTemplateNode.svelte';
import RoleTypeNode from '../../components/blueprint/nodes/RoleTypeNode.svelte';

// Workflow node components (Phase 1 — specialized per type)
import InputNode from '../../components/blueprint/nodes/InputNode.svelte';
import InitializeNode from '../../components/blueprint/nodes/InitializeNode.svelte';
import StrategistNode from '../../components/blueprint/nodes/StrategistNode.svelte';
import CriticNode from '../../components/blueprint/nodes/CriticNode.svelte';
import OptimizerNode from '../../components/blueprint/nodes/OptimizerNode.svelte';
import ModeratorNode from '../../components/blueprint/nodes/ModeratorNode.svelte';
import UserInjectionNode from '../../components/blueprint/nodes/UserInjectionNode.svelte';
import GateNode from '../../components/blueprint/nodes/GateNode.svelte';

// Semantic edge components (Phase 3)
import UsesLlmEdge from '../../components/blueprint/edges/UsesLlmEdge.svelte';
import ImplementsRoleEdge from '../../components/blueprint/edges/ImplementsRoleEdge.svelte';
import PromptedByEdge from '../../components/blueprint/edges/PromptedByEdge.svelte';
import OverridesPromptEdge from '../../components/blueprint/edges/OverridesPromptEdge.svelte';

// Control flow edge components (Phase 4)
import SequentialEdge from '../../components/blueprint/edges/SequentialEdge.svelte';
import ConditionalEdge from '../../components/blueprint/edges/ConditionalEdge.svelte';
import InterjectionEdge from '../../components/blueprint/edges/InterjectionEdge.svelte';
import FeedbackEdge from '../../components/blueprint/edges/FeedbackEdge.svelte';

// RoleType edge component
import DefinesRoleEdge from '../../components/blueprint/edges/DefinesRoleEdge.svelte';

/**
 * Register all node and edge types in the central registry.
 * Should be called once during app initialization.
 */
export function registerAllNodeTypes() {
  // ── Asset nodes (Phase 3) ──────────────────────────────────────────

  registerNode({
    type: 'agent-blueprint',
    component: AgentBlueprintNode,
    category: 'asset',
    schemaRef: 'AgentBlueprint',
    icon: '🤖',
    labelKey: 'blueprint.palette.agentBlueprint',
    defaultData: () => ({
      isDraft: true,
      name: '',
      description: '',
      tags: [],
    }),
    active: true,
  });

  registerNode({
    type: 'llm-profile',
    component: LLMProfileNode,
    category: 'asset',
    schemaRef: 'BlueprintLLMProfile',
    icon: '🧠',
    labelKey: 'blueprint.palette.llmProfile',
    defaultData: () => ({
      isDraft: true,
      name: '',
      provider: 'openrouter',
      model: '',
    }),
    active: true,
  });

  registerNode({
    type: 'role-definition',
    component: RoleDefinitionNode,
    category: 'asset',
    schemaRef: 'RoleDefinition',
    icon: '👤',
    labelKey: 'blueprint.palette.roleDefinition',
    defaultData: () => ({
      isDraft: true,
      name: '',
      role: 'strategist',
    }),
    active: true,
  });

  registerNode({
    type: 'prompt-template',
    component: PromptTemplateNode,
    category: 'asset',
    schemaRef: 'PromptTemplate',
    icon: '📝',
    labelKey: 'blueprint.palette.promptTemplate',
    defaultData: () => ({
      isDraft: true,
      name: '',
      content: '',
      role: 'strategist',
    }),
    active: true,
  });

  registerNode({
    type: 'role-type',
    component: RoleTypeNode,
    category: 'asset',
    schemaRef: 'RoleType',
    icon: '🏷️',
    labelKey: 'blueprint.palette.roleType',
    defaultData: () => ({
      isDraft: true,
      name: '',
      description: '',
      icon: '👤',
      color: '#8b5cf6',
      default_max_rounds: 5,
      default_consensus_threshold: 0.9,
    }),
    active: true,
  });

  // ── Workflow nodes (Phase 1 — specialized components) ──────────────

  registerNode({
    type: 'wf-input',
    component: InputNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '📥',
    labelKey: 'blueprint.palette.wfInput',
    defaultData: () => ({
      isDraft: true,
      label: 'Case Input',
    }),
    active: true,
  });

  registerNode({
    type: 'wf-initialize',
    component: InitializeNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🚀',
    labelKey: 'blueprint.palette.wfInitialize',
    defaultData: () => ({
      isDraft: true,
      label: 'Initialize',
    }),
    active: true,
  });

  registerNode({
    type: 'wf-strategist',
    component: StrategistNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🧠',
    labelKey: 'blueprint.palette.wfStrategist',
    defaultData: () => ({
      isDraft: true,
      label: 'Strategist',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-critic',
    component: CriticNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🔍',
    labelKey: 'blueprint.palette.wfCritic',
    defaultData: () => ({
      isDraft: true,
      label: 'Critic',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-optimizer',
    component: OptimizerNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '⚡',
    labelKey: 'blueprint.palette.wfOptimizer',
    defaultData: () => ({
      isDraft: true,
      label: 'Optimizer',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-moderator',
    component: ModeratorNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🎯',
    labelKey: 'blueprint.palette.wfModerator',
    defaultData: () => ({
      isDraft: true,
      label: 'Moderator',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-user-injection',
    component: UserInjectionNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '👤',
    labelKey: 'blueprint.palette.wfUserInjection',
    defaultData: () => ({
      isDraft: true,
      label: 'User Input',
      config: { input_type: 'user_query' },
    }),
    active: true,
  });

  registerNode({
    type: 'wf-gate',
    component: GateNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🔀',
    labelKey: 'blueprint.palette.wfGate',
    defaultData: () => ({
      isDraft: true,
      label: 'Gate',
      config: { condition: '' },
    }),
    active: true,
  });

  // ── Semantic edges (Phase 3) ───────────────────────────────────────

  registerEdge({
    type: 'uses_llm',
    component: UsesLlmEdge,
    category: 'semantic',
  });

  registerEdge({
    type: 'implements_role',
    component: ImplementsRoleEdge,
    category: 'semantic',
  });

  registerEdge({
    type: 'prompted_by',
    component: PromptedByEdge,
    category: 'semantic',
  });

  registerEdge({
    type: 'overrides_prompt',
    component: OverridesPromptEdge,
    category: 'semantic',
  });

  registerEdge({
    type: 'defines_role',
    component: DefinesRoleEdge,
    category: 'semantic',
  });

  // ── Control flow edges (Phase 4) ───────────────────────────────────

  registerEdge({
    type: 'sequential',
    component: SequentialEdge,
    category: 'control_flow',
  });

  registerEdge({
    type: 'conditional',
    component: ConditionalEdge,
    category: 'control_flow',
  });

  registerEdge({
    type: 'interjection',
    component: InterjectionEdge,
    category: 'control_flow',
  });

  registerEdge({
    type: 'feedback',
    component: FeedbackEdge,
    category: 'control_flow',
  });
}
