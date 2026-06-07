/**
 * Blueprint Canvas — Register asset node types.
 *
 * Asset nodes are the reusable building blocks (LLM profiles, agent
 * cores, tone profiles) that workflow nodes reference.  Split out of
 * the monolithic ``registerAll.js`` in audit L5 so the orchestrator
 * stays small and the asset vs. workflow split is explicit.
 *
 * Idempotent — safe to call multiple times; the registry's
 * ``Map.set`` overwrites previous entries.
 */

import { registerNode } from './registry.js';

import LLMProfileNode from '../../components/blueprint/nodes/LLMProfileNode.svelte';
import AgentCoreNode from '../../components/blueprint/nodes/AgentCoreNode.svelte';
import ToneProfileNode from '../../components/blueprint/nodes/ToneProfileNode.svelte';

export function registerAssetNodes() {
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
}
