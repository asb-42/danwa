/**
 * Blueprint Canvas — Register workflow node types.
 *
 * Workflow nodes are the executable steps in a workflow definition
 * (input, initialize, the 19 agent roles, phase/gate/user-injection/
 * tone-profile/agent/builder/pragmatist/angels-advocate).  Split out
 * of the monolithic ``registerAll.js`` in audit L5.
 *
 * Idempotent — safe to call multiple times; the registry's
 * ``Map.set`` overwrites previous entries.
 */

import { registerNode } from './registry.js';

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

export function registerWorkflowNodes() {
  // ── Workflow structure nodes ────────────────────────────────────────

  registerNode({
    type: 'wf-input',
    component: InputNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '📥',
    labelKey: 'blueprint.palette.wfInput',
    defaultData: () => ({ isDraft: true, label: 'Case Input' }),
    active: true,
  });

  registerNode({
    type: 'wf-initialize',
    component: InitializeNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🚀',
    labelKey: 'blueprint.palette.wfInitialize',
    defaultData: () => ({ isDraft: true, label: 'Initialize' }),
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
    type: 'wf-gate',
    component: GateNode,
    category: 'workflow',
    schemaRef: 'WorkflowDefinition',
    icon: '🔀',
    labelKey: 'blueprint.palette.wfGate',
    defaultData: () => ({ isDraft: true, label: 'Gate', config: { condition: '' } }),
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

  // ── Agent role nodes ────────────────────────────────────────────────

  const ROLE_TYPES = [
    ['wf-strategist', '🧠', 'wfStrategist', 'Strategist', StrategistNode],
    ['wf-critic', '🔍', 'wfCritic', 'Critic', CriticNode],
    ['wf-optimizer', '⚡', 'wfOptimizer', 'Optimizer', OptimizerNode],
    ['wf-moderator', '🎯', 'wfModerator', 'Moderator', ModeratorNode],
    ['wf-fact-checker', '✅', 'wfFactChecker', 'Fact Checker', FactCheckerNode],
    ['wf-analyst', '📊', 'wfAnalyst', 'Analyst', AnalystNode],
    ['wf-creative', '💡', 'wfCreative', 'Creative', CreativeNode],
    [
      'wf-socratic-questioner',
      '❓',
      'wfSocraticQuestioner',
      'Socratic Questioner',
      SocraticQuestionerNode,
    ],
    [
      'wf-expert-reviewer',
      '🔬',
      'wfExpertReviewer',
      'Expert Reviewer',
      ExpertReviewerNode,
    ],
    ['wf-steel-manner', '🛡️', 'wfSteelManner', 'Steel Manner', SteelMannerNode],
    [
      "wf-devils-advocate",
      '👿',
      'wfDevilsAdvocate',
      "Devil's Advocate",
      DevilsAdvocateNode,
    ],
    ['wf-troll', '🤡', 'wfTroll', 'Troll', TrollNode],
    ['wf-mediator', '🤝', 'wfMediator', 'Mediator', MediatorNode],
    ['wf-ethicist', '⚖️', 'wfEthicist', 'Ethicist', EthicistNode],
    ['wf-synthesizer', '🔗', 'wfSynthesizer', 'Synthesizer', SynthesizerNode],
    [
      'wf-angels-advocate',
      '🛡️',
      'wfAngelsAdvocate',
      "Angel's Advocate",
      AngelsAdvocateNode,
    ],
    ['wf-builder', '🔨', 'wfBuilder', 'Builder', BuilderNode],
    ['wf-pragmatist', '⚖️', 'wfPragmatist', 'Pragmatist', PragmatistNode],
  ];

  for (const [type, icon, labelKey, label, component] of ROLE_TYPES) {
    registerNode({
      type,
      component,
      category: 'workflow',
      schemaRef: 'WorkflowDefinition',
      icon,
      labelKey: `blueprint.palette.${labelKey}`,
      defaultData: () => ({
        isDraft: true,
        label,
        agent_blueprint_id: null,
      }),
      active: true,
    });
  }

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
}
