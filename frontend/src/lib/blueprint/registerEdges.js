/**
 * Blueprint Canvas — Register edge types.
 *
 * Edges are split into two categories:
 *   * ``semantic`` — describe a relationship between nodes
 *     (uses_llm, uses_core, uses_tone).
 *   * ``control_flow`` — drive workflow execution
 *     (sequential, conditional, interjection, feedback, injects_config,
 *      builds_upon, validates, decision).
 *
 * Split out of the monolithic ``registerAll.js`` in audit L5.
 *
 * Idempotent — safe to call multiple times; the registry's
 * ``Map.set`` overwrites previous entries.
 */

import { registerEdge } from './registry.js';

import UsesLlmEdge from '../../components/blueprint/edges/UsesLlmEdge.svelte';
import UsesCoreEdge from '../../components/blueprint/edges/UsesCoreEdge.svelte';
import UsesToneEdge from '../../components/blueprint/edges/UsesToneEdge.svelte';

import SequentialEdge from '../../components/blueprint/edges/SequentialEdge.svelte';
import ConditionalEdge from '../../components/blueprint/edges/ConditionalEdge.svelte';
import InterjectionEdge from '../../components/blueprint/edges/InterjectionEdge.svelte';
import FeedbackEdge from '../../components/blueprint/edges/FeedbackEdge.svelte';
import InjectsConfigEdge from '../../components/blueprint/edges/InjectsConfigEdge.svelte';
import BuildsUponEdge from '../../components/blueprint/edges/BuildsUponEdge.svelte';
import ValidatesEdge from '../../components/blueprint/edges/ValidatesEdge.svelte';
import DecisionEdge from '../../components/blueprint/edges/DecisionEdge.svelte';

export function registerEdges() {
  // ── Semantic edges ──────────────────────────────────────────────────

  registerEdge({ type: 'uses_llm', component: UsesLlmEdge, category: 'semantic' });
  registerEdge({ type: 'uses_core', component: UsesCoreEdge, category: 'semantic' });
  registerEdge({ type: 'uses_tone', component: UsesToneEdge, category: 'semantic' });

  // ── Control flow edges ──────────────────────────────────────────────

  const CONTROL_FLOW = [
    ['sequential', SequentialEdge],
    ['conditional', ConditionalEdge],
    ['interjection', InterjectionEdge],
    ['feedback', FeedbackEdge],
    ['injects_config', InjectsConfigEdge],
    ['builds_upon', BuildsUponEdge],
    ['validates', ValidatesEdge],
    ['decision', DecisionEdge],
  ];

  for (const [type, component] of CONTROL_FLOW) {
    registerEdge({ type, component, category: 'control_flow' });
  }
}
