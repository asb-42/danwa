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
import AgentCoreNode from '../../components/blueprint/nodes/AgentCoreNode.svelte';

// Workflow node components (Phase 1 — specialized per type)
import InputNode from '../../components/blueprint/nodes/InputNode.svelte';
import InitializeNode from '../../components/blueprint/nodes/InitializeNode.svelte';
import StrategistNode from '../../components/blueprint/nodes/StrategistNode.svelte';
import CriticNode from '../../components/blueprint/nodes/CriticNode.svelte';
import OptimizerNode from '../../components/blueprint/nodes/OptimizerNode.svelte';
import ModeratorNode from '../../components/blueprint/nodes/ModeratorNode.svelte';
import FactCheckerNode from '../../components/blueprint/nodes/FactCheckerNode.svelte';
import AnalystNode from '../../components/blueprint/nodes/AnalystNode.svelte';
import CreativeNode from '../../components/blueprint/nodes/CreativeNode.svelte';
import SocraticQuestionerNode from '../../components/blueprint/nodes/SocraticQuestionerNode.svelte';
import ExpertReviewerNode from '../../components/blueprint/nodes/ExpertReviewerNode.svelte';
import SteelMannerNode from '../../components/blueprint/nodes/SteelMannerNode.svelte';
import DevilsAdvocateNode from '../../components/blueprint/nodes/DevilsAdvocateNode.svelte';
import TrollNode from '../../components/blueprint/nodes/TrollNode.svelte';
import MediatorNode from '../../components/blueprint/nodes/MediatorNode.svelte';
import EthicistNode from '../../components/blueprint/nodes/EthicistNode.svelte';
import SynthesizerNode from '../../components/blueprint/nodes/SynthesizerNode.svelte';
import PhaseNode from '../../components/blueprint/nodes/PhaseNode.svelte';
import UserInjectionNode from '../../components/blueprint/nodes/UserInjectionNode.svelte';
import GateNode from '../../components/blueprint/nodes/GateNode.svelte';
import ToneProfileNode from '../../components/blueprint/nodes/ToneProfileNode.svelte';
import AgentNode from '../../components/blueprint/nodes/AgentNode.svelte';
import AngelsAdvocateNode from '../../components/blueprint/nodes/AngelsAdvocateNode.svelte';
import BuilderNode from '../../components/blueprint/nodes/BuilderNode.svelte';
import PragmatistNode from '../../components/blueprint/nodes/PragmatistNode.svelte';

// Semantic edge components (Phase 3)
import UsesLlmEdge from '../../components/blueprint/edges/UsesLlmEdge.svelte';
import ImplementsRoleEdge from '../../components/blueprint/edges/ImplementsRoleEdge.svelte';
import UsesCoreEdge from '../../components/blueprint/edges/UsesCoreEdge.svelte';
import PromptedByEdge from '../../components/blueprint/edges/PromptedByEdge.svelte';
import OverridesPromptEdge from '../../components/blueprint/edges/OverridesPromptEdge.svelte';
import UsesToneEdge from '../../components/blueprint/edges/UsesToneEdge.svelte';

// Control flow edge components (Phase 4)
import SequentialEdge from '../../components/blueprint/edges/SequentialEdge.svelte';
import ConditionalEdge from '../../components/blueprint/edges/ConditionalEdge.svelte';
import InterjectionEdge from '../../components/blueprint/edges/InterjectionEdge.svelte';
import FeedbackEdge from '../../components/blueprint/edges/FeedbackEdge.svelte';
import InjectsConfigEdge from '../../components/blueprint/edges/InjectsConfigEdge.svelte';
import BuildsUponEdge from '../../components/blueprint/edges/BuildsUponEdge.svelte';
import ValidatesEdge from '../../components/blueprint/edges/ValidatesEdge.svelte';
import DecisionEdge from '../../components/blueprint/edges/DecisionEdge.svelte';

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

  registerNode({
    type: 'agent-core',
    component: AgentCoreNode,
    category: 'asset',
    schemaRef: null,
    icon: '🧬',
    labelKey: 'blueprint.palette.agentCore',
    defaultData: () => ({
      isDraft: true,
      module_id: null,
      name: '',
      role: '',
      description: '',
    }),
    active: true,
  });

  registerNode({
    type: 'tone-profile',
    component: ToneProfileNode,
    category: 'asset',
    schemaRef: 'ToneProfile',
    icon: '🎵',
    labelKey: 'blueprint.palette.toneProfile',
    defaultData: () => ({
      isDraft: true,
      label: '',
      tone_profile_id: null,
      inline_profile: null,
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
    type: 'wf-fact-checker',
    component: FactCheckerNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '✅',
    labelKey: 'blueprint.palette.wfFactChecker',
    defaultData: () => ({
      isDraft: true,
      label: 'Fact Checker',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-analyst',
    component: AnalystNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '📊',
    labelKey: 'blueprint.palette.wfAnalyst',
    defaultData: () => ({
      isDraft: true,
      label: 'Analyst',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-creative',
    component: CreativeNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '💡',
    labelKey: 'blueprint.palette.wfCreative',
    defaultData: () => ({
      isDraft: true,
      label: 'Creative',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-socratic-questioner',
    component: SocraticQuestionerNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '❓',
    labelKey: 'blueprint.palette.wfSocraticQuestioner',
    defaultData: () => ({
      isDraft: true,
      label: 'Socratic Questioner',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-expert-reviewer',
    component: ExpertReviewerNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🔬',
    labelKey: 'blueprint.palette.wfExpertReviewer',
    defaultData: () => ({
      isDraft: true,
      label: 'Expert Reviewer',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-steel-manner',
    component: SteelMannerNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🛡️',
    labelKey: 'blueprint.palette.wfSteelManner',
    defaultData: () => ({
      isDraft: true,
      label: 'Steel Manner',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-devils-advocate',
    component: DevilsAdvocateNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '👿',
    labelKey: 'blueprint.palette.wfDevilsAdvocate',
    defaultData: () => ({
      isDraft: true,
      label: "Devil's Advocate",
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-troll',
    component: TrollNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🤡',
    labelKey: 'blueprint.palette.wfTroll',
    defaultData: () => ({
      isDraft: true,
      label: 'Troll',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-mediator',
    component: MediatorNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🤝',
    labelKey: 'blueprint.palette.wfMediator',
    defaultData: () => ({
      isDraft: true,
      label: 'Mediator',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-ethicist',
    component: EthicistNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '⚖️',
    labelKey: 'blueprint.palette.wfEthicist',
    defaultData: () => ({
      isDraft: true,
      label: 'Ethicist',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-synthesizer',
    component: SynthesizerNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🔗',
    labelKey: 'blueprint.palette.wfSynthesizer',
    defaultData: () => ({
      isDraft: true,
      label: 'Synthesizer',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-phase',
    component: PhaseNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '📋',
    labelKey: 'blueprint.palette.wfPhase',
    defaultData: () => ({
      isDraft: true,
      label: 'Phase',
      phase_name: 'New Phase',
      description: '',
      roles: [],
      max_rounds: 3,
      color: '#6366f1',
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

  registerNode({
    type: 'wf-tone-profile',
    component: ToneProfileNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🎵',
    labelKey: 'blueprint.palette.wfToneProfile',
    defaultData: () => ({
      isDraft: true,
      label: 'Tone Profile',
      tone_profile_id: null,
      inline_profile: null,
    }),
    active: true,
  });

  // ── Generic Agent Node (Bundle architecture) ───────────────────────

  registerNode({
    type: 'wf-agent',
    component: AgentNode,
    category: 'workflow',
    schemaRef: 'AgentBundle',
    icon: '🤖',
    labelKey: 'blueprint.palette.wfAgent',
    defaultData: () => ({
      isDraft: true,
      label: 'Agent (Bundle)',
      bundle_id: null,
      role_type_icon: '\u{1F464}',
      role_type_name: '',
      role_type_color: '#8b5cf6',
    }),
    active: true,
  });

  registerNode({
    type: 'wf-builder',
    component: BuilderNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🔨',
    labelKey: 'blueprint.palette.wfBuilder',
    defaultData: () => ({
      isDraft: true,
      label: 'Builder',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-pragmatist',
    component: PragmatistNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '⚖️',
    labelKey: 'blueprint.palette.wfPragmatist',
    defaultData: () => ({
      isDraft: true,
      label: 'Pragmatist',
      agent_blueprint_id: null,
    }),
    active: true,
  });

  registerNode({
    type: 'wf-angels-advocate',
    component: AngelsAdvocateNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🛡️',
    labelKey: 'blueprint.palette.wfAngelsAdvocate',
    defaultData: () => ({
      isDraft: true,
      label: "Angel's Advocate",
      agent_blueprint_id: null,
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

  registerEdge({
    type: 'uses_tone',
    component: UsesToneEdge,
    category: 'semantic',
  });

  registerEdge({
    type: 'uses_core',
    component: UsesCoreEdge,
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

  registerEdge({
    type: 'injects_config',
    component: InjectsConfigEdge,
    category: 'control_flow',
  });

  registerEdge({
    type: 'builds_upon',
    component: BuildsUponEdge,
    category: 'control_flow',
  });

  registerEdge({
    type: 'validates',
    component: ValidatesEdge,
    category: 'control_flow',
  });

  registerEdge({
    type: 'decision',
    component: DecisionEdge,
    category: 'control_flow',
  });
}
