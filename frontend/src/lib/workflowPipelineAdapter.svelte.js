/**
 * workflowPipelineAdapter.js
 *
 * Adapters that feed `WorkflowPipeline.svelte` with real data from the
 * backend. The component itself is data-only — these helpers do the
 * fetching, mapping, and SSE plumbing.
 *
 * Public surface:
 *   - useLastCompletedDebatePipeline(projectId?)
 *       → Svelte 5 reactive object exposing meta/nodes/edges/activeNodeId
 *         for the most recently completed debate in the current project.
 *
 *   - useLiveWorkflowPipeline(debateId)
 *       → Subscribes to /api/v1/workflow_exec/{id}/stream and exposes
 *         meta/nodes/edges/activeNodeId that update as the debate runs.
 *         Returns null meta/nodes while loading.
 */

import { get } from 'svelte/store';
import { getDebates, getDebate } from './api/debate.js';
import { getWorkflowState } from './workflowExec.js';
import { createWorkflowSSE } from './workflowSSE.js';
import { activeProject } from './stores.js';
import {
  paletteFor,
  NODE_STATUS,
  EDGE_KIND,
  statusFromOutput,
  indexOutputs,
} from './workflow/pipeline-utils.js';

/**
 * Fetch the most recently completed debate in the given project.
 * Returns null if no completed debate exists.
 */
async function fetchLastCompletedDebate(projectId) {
  const params = { status: 'completed', limit: 1 };
  const list = await getDebates(1, params);
  if (!Array.isArray(list) || list.length === 0) return null;
  const item = list[0];
  // Pull full detail so we have session_id
  const full = await getDebate(item.debate_id);
  return full || item;
}

/**
 * Fetch the workflow definition (nodes + edges) for a given workflow id.
 * Falls back to an empty array if the endpoint fails — caller decides
 * whether to render an empty state or fall back to inferred topology.
 */
async function fetchWorkflowDefinition(workflowId) {
  if (!workflowId) return { nodes: [], edges: [] };
  try {
    const res = await fetch(`/api/v1/workflow_definitions/${encodeURIComponent(workflowId)}`);
    if (!res.ok) return { nodes: [], edges: [] };
    const def = await res.json();
    return {
      nodes: Array.isArray(def?.nodes) ? def.nodes : [],
      edges: Array.isArray(def?.edges) ? def.edges : [],
    };
  } catch {
    return { nodes: [], edges: [] };
  }
}

/**
 * Build PipelineNode[] + PipelineEdge[] from a workflow definition
 * and a map of node_outputs. The definition supplies topology and
 * labels; outputs supply status and metrics.
 */
function buildPipelineFromDefinition(definition, nodeOutputs, currentNodeId) {
  const outIndex = indexOutputs(nodeOutputs);

  const nodes = (definition.nodes || []).map((n) => {
    const id = n.id || n.node_id;
    const palette = paletteFor(n.role || n.type || n.id);
    const out = outIndex.get(id);
    const status = out ? statusFromOutput(out) : NODE_STATUS.PENDING;
    return {
      id,
      label: n.label || n.name || n.role || id,
      icon: n.icon || palette.icon,
      color: n.color || palette.color,
      width: n.width || 120,
      height: n.height || 48,
      status,
      metrics: out
        ? {
            tokens: (out.prompt_tokens || 0) + (out.completion_tokens || 0),
            durationMs: out.latency_ms,
            round: out.round,
            consensusScore: out.consensus_score,
          }
        : null,
      meta: n,
    };
  });

  const edges = (definition.edges || []).map((e) => ({
    id: e.id || `${e.source || e.from}->${e.target || e.to}`,
    source: e.source || e.from,
    target: e.target || e.to,
    label: e.label,
    kind: e.kind || EDGE_KIND.FORWARD,
  }));

  return { nodes, edges, activeNodeId: currentNodeId || null };
}

/**
 * useLastCompletedDebatePipeline — reactive store-like object for the
 * Dashboard's "exemplary flow of the last completed debate" use case.
 *
 * Usage in a component:
 *   const pipeline = useLastCompletedDebatePipeline();
 *   $effect(() => { if (pipeline.meta) { ... } });
 */
export function useLastCompletedDebatePipeline() {
  const result = $state({
    meta: null,
    nodes: [],
    edges: [],
    activeNodeId: null,
    loading: false,
    error: null,
  });

  async function load() {
    result.loading = true;
    result.error = null;
    try {
      const projectId = get(activeProject)?.id;
      const debate = await fetchLastCompletedDebate(projectId);
      if (!debate) {
        result.meta = null;
        result.nodes = [];
        result.edges = [];
        return;
      }

      const sessionId = debate.session_id;
      const workflowId = debate.workflow_id;

      // Load state + definition in parallel
      const [state, definition] = await Promise.all([
        sessionId
          ? getWorkflowState(sessionId).catch(() => null)
          : Promise.resolve(null),
        fetchWorkflowDefinition(workflowId),
      ]);

      const nodeOutputs = state?.node_outputs || [];
      const built = buildPipelineFromDefinition(definition, nodeOutputs, null);

      result.meta = {
        id: debate.debate_id,
        name: debate.title || 'Last completed debate',
        description: '',
        source: 'replay',
        workflowId,
      };
      result.nodes = built.nodes;
      result.edges = built.edges;
      result.activeNodeId = built.activeNodeId;
    } catch (err) {
      result.error = err?.message || String(err);
    } finally {
      result.loading = false;
    }
  }

  // Auto-load on construction and whenever the project changes
  $effect(() => {
    void get(activeProject)?.id; // dependency tracking
    load();
  });

  return result;
}

/**
 * useLiveWorkflowPipeline — reactive pipeline state for a running debate.
 * Subscribes to the SSE stream and updates node status + activeNodeId.
 *
 * Returns null meta/nodes while loading; pass debateId as null/undefined
 * to get a clean empty state (component renders PipelineEmptyState).
 */
export function useLiveWorkflowPipeline(debateId) {
  const result = $state({
    meta: null,
    nodes: [],
    edges: [],
    activeNodeId: null,
    loading: false,
    error: null,
  });

  let cleanup = null;

  async function subscribe() {
    if (!debateId) {
      result.meta = null;
      result.nodes = [];
      result.edges = [];
      return;
    }
    result.loading = true;
    result.error = null;

    try {
      const state = await getWorkflowState(debateId).catch(() => null);
      const definition = await fetchWorkflowDefinition(state?.workflow_id);

      const nodeOutputs = state?.node_outputs || [];
      const built = buildPipelineFromDefinition(
        definition,
        nodeOutputs,
        state?.current_node_id
      );

      result.meta = {
        id: debateId,
        name: 'Live workflow',
        description: '',
        source: 'live',
        workflowId: state?.workflow_id,
      };
      result.nodes = built.nodes;
      result.edges = built.edges;
      result.activeNodeId = built.activeNodeId;

      // Subscribe to SSE for live updates
      cleanup?.();
      cleanup = createWorkflowSSE(debateId, {
        onWorkflowStarted: () => {
          result.activeNodeId = null;
        },
        onNodeStart: (payload) => {
          if (payload?.node_id) {
            result.activeNodeId = payload.node_id;
            // Mark this node as running in the local cache
            const n = result.nodes.find((x) => x.id === payload.node_id);
            if (n) n.status = NODE_STATUS.RUNNING;
          }
        },
        onNodeComplete: (payload) => {
          if (payload?.node_id) {
            const n = result.nodes.find((x) => x.id === payload.node_id);
            if (n) {
              n.status = NODE_STATUS.DONE;
              n.metrics = {
                tokens: (payload.prompt_tokens || 0) + (payload.completion_tokens || 0),
                durationMs: payload.latency_ms,
                round: payload.round,
              };
            }
          }
        },
        onNodeError: (payload) => {
          if (payload?.node_id) {
            const n = result.nodes.find((x) => x.id === payload.node_id);
            if (n) n.status = NODE_STATUS.FAILED;
          }
        },
        onWorkflowComplete: () => {
          result.activeNodeId = null;
        },
      });
    } catch (err) {
      result.error = err?.message || String(err);
    } finally {
      result.loading = false;
    }
  }

  $effect(() => {
    void debateId;
    subscribe();
    return () => {
      cleanup?.();
      cleanup = null;
    };
  });

  return result;
}
