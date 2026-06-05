/**
 * pipeline-utils.js
 *
 * Shared utilities for the WorkflowPipeline visualization.
 * Kept side-effect-free and tree-shakable so sub-components
 * and the main component can import only what they need.
 */

import { getElk } from '../elk-service.js';

export const NODE_STATUS = Object.freeze({
  PENDING: 'pending',
  RUNNING: 'running',
  DONE: 'done',
  FAILED: 'failed',
  SKIPPED: 'skipped',
});

export const EDGE_KIND = Object.freeze({
  FORWARD: 'forward',
  FEEDBACK: 'feedback',
});

/**
 * Color tokens per node status. Frontend-only — no backend coupling.
 * Dark variants live next to the light ones for easy Tailwind class lookup.
 */
export const STATUS_COLORS = Object.freeze({
  pending: { fill: '#9ca3af', text: '#9ca3af', glow: 'none', opacity: 0.5 },
  running: { fill: '#3b82f6', text: '#3b82f6', glow: '#3b82f6', opacity: 1.0 },
  done:    { fill: '#10b981', text: '#10b981', glow: '#10b981', opacity: 1.0 },
  failed:  { fill: '#ef4444', text: '#ef4444', glow: '#ef4444', opacity: 1.0 },
  skipped: { fill: '#9ca3af', text: '#9ca3af', glow: 'none', opacity: 0.4 },
});

/**
 * Default node palette. Mirrors the previous DashboardWorkflowGraph
 * mapping so a single component covers the same visual identity.
 */
export const ROLE_PALETTE = Object.freeze({
  input:      { color: '#6b7280', icon: '📥' },
  strategist: { color: '#8b5cf6', icon: '🧠' },
  critic:     { color: '#ef4444', icon: '🔍' },
  optimizer:  { color: '#f59e0b', icon: '⚡' },
  moderator:  { color: '#6366f1', icon: '🎯' },
  result:     { color: '#10b981', icon: '📋' },
  // Fallback for unknown roles
  _default:   { color: '#6b7280', icon: '▫️' },
});

export function paletteFor(role) {
  return ROLE_PALETTE[role] || ROLE_PALETTE._default;
}

/**
 * Compute a directed graph layout via ELK.
 * Pure: same input → same output. Cached by the caller if needed.
 *
 * @param {Array<{id:string,width:number,height:number}>} nodes
 * @param {Array<{id:string,sources:string[],targets:string[]}>} edges
 * @param {{direction?: 'RIGHT'|'DOWN'|'LEFT'|'UP'}} [options]
 * @returns {Promise<{children:Array, edges:Array, width:number, height:number}>}
 */
export async function computeLayout(nodes, edges, options = {}) {
  const elk = getElk();
  const direction = options.direction || 'RIGHT';

  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': direction,
      'elk.layered.spacing.nodeNodeBetweenLayers': '60',
      'elk.spacing.nodeNode': '30',
      'elk.layered.feedbackEdges': 'true',
      'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
    },
    children: nodes.map((n) => ({
      id: n.id,
      width: n.width,
      height: n.height,
    })),
    edges: edges.map((e) => ({
      id: e.id,
      sources: e.sources || [e.source],
      targets: e.targets || [e.target],
    })),
  };

  const result = await elk.layout(graph);

  // Compute bounding box
  let maxX = 0;
  let maxY = 0;
  function walk(node) {
    if (node.x != null) maxX = Math.max(maxX, node.x + (node.width || 0));
    if (node.y != null) maxY = Math.max(maxY, node.y + (node.height || 0));
    if (node.children) node.children.forEach(walk);
  }
  if (result.children) result.children.forEach(walk);

  return {
    children: result.children || [],
    edges: result.edges || [],
    width: maxX + 60,
    height: maxY + 80,
  };
}

/**
 * Look up a node's position by id in a layout result.
 * Returns null if the node is not present.
 */
export function nodePosition(layout, nodeId) {
  if (!layout?.children) return null;
  for (const child of layout.children) {
    if (child.id === nodeId) {
      return { x: child.x ?? 0, y: child.y ?? 0 };
    }
  }
  return null;
}

/**
 * Build a cubic Bezier path between two laid-out nodes.
 * Feedback edges (typically moderator → earlier node) are routed
 * underneath the main flow with a downward arc.
 */
export function edgePath(layout, edge, sourceNode, targetNode) {
  const src = nodePosition(layout, edge.source);
  const tgt = nodePosition(layout, edge.target);
  if (!src || !tgt || !sourceNode || !targetNode) return '';

  const isFeedback = edge.kind === EDGE_KIND.FEEDBACK;

  if (isFeedback) {
    const x1 = src.x + sourceNode.width / 2;
    const y1 = src.y + sourceNode.height;
    const x2 = tgt.x + targetNode.width / 2;
    const y2 = tgt.y + targetNode.height;
    const midY = Math.max(y1, y2) + 40;
    return `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;
  }

  const x1 = src.x + sourceNode.width;
  const y1 = src.y + sourceNode.height / 2;
  const x2 = tgt.x;
  const y2 = tgt.y + targetNode.height / 2;
  const cx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`;
}

/**
 * Map a backend node_outputs entry to a PipelineNode status.
 * Output entries from /api/v1/workflow_exec/{sid}/state have
 * { node_id, status, tokens, duration_ms, ... }.
 */
export function statusFromOutput(out) {
  if (!out) return NODE_STATUS.PENDING;
  const s = (out.status || '').toLowerCase();
  if (s === 'completed' || s === 'done' || s === 'success') return NODE_STATUS.DONE;
  if (s === 'failed' || s === 'error') return NODE_STATUS.FAILED;
  if (s === 'skipped' || s === 'bypassed') return NODE_STATUS.SKIPPED;
  if (s === 'running' || s === 'in_progress') return NODE_STATUS.RUNNING;
  return NODE_STATUS.PENDING;
}

/**
 * Build a quick lookup of node_id → node_outputs entry.
 * Used by the Dashboard adapter to fill metrics in.
 */
export function indexOutputs(nodeOutputs) {
  const map = new Map();
  for (const o of nodeOutputs || []) {
    if (o?.node_id) map.set(o.node_id, o);
  }
  return map;
}
