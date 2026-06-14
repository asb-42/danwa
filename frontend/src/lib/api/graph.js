/**
 * Graph API — Phase 4 / 5.4 frontend wrapper.
 *
 * Two endpoints introduced in plans/2026-06-14_case-space-workspace.md:
 *   GET /api/v1/graph/local?entity_type=…&entity_id=…&hops=…
 *   GET /api/v1/graph/edges?src=…&tgt=…
 *
 * Both are feature-gated by ``settings.enable_case_space_graph`` on
 * the backend; while the flag is False the endpoints return 404.
 * The wrapper functions surface the 404 as a typed error so the
 * InspectorGraphTab can render a "graph disabled" message instead
 * of crashing.
 *
 * The component in InspectorGraphTab.svelte is the only consumer
 * for now, but the data shapes (GraphPayload, EdgeDetail) are
 * frozen because the eventual Cytoscape renderer will share them.
 *
 * @see plans/2026-06-14_case-space-workspace.md (Phase 4 & 5.4)
 */

import { request } from './core.js';

/**
 * @typedef {Object} GraphNode
 * @property {string} id        "{type}:{entityId}" form
 * @property {string} type      "case" | "debate" | "document" | "tag" | "user" | "audit"
 * @property {string} label
 * @property {Object} [meta]     entity-type-specific extras
 */

/**
 * @typedef {Object} GraphEdge
 * @property {string} src
 * @property {string} tgt
 * @property {string} type       "contains" | "tagged_with" | "references" | …
 * @property {number} [weight]    [0..1] confidence / strength
 */

/**
 * @typedef {Object} GraphPayload
 * @property {GraphNode[]} nodes
 * @property {GraphEdge[]} edges
 * @property {boolean} [truncated]
 */

/**
 * @typedef {Object} EdgeDetail
 * @property {string}  src
 * @property {string}  tgt
 * @property {string}  type
 * @property {number}  [weight]
 * @property {string[]} [evidence]  human-readable list of why this edge exists
 * @property {string}  [created_at] ISO-8601
 */

/**
 * Fetch the 1-hop (or up to 2-hop) subgraph around one entity.
 * @param {string} entityType
 * @param {string} entityId
 * @param {number} [hops=1]
 * @returns {Promise<GraphPayload>}
 */
export async function getLocalGraph(entityType, entityId, hops = 1) {
  if (!entityType || !entityId) {
    throw new TypeError('getLocalGraph: entityType and entityId are required');
  }
  const url =
    `/api/v1/graph/local?entity_type=${encodeURIComponent(entityType)}` +
    `&entity_id=${encodeURIComponent(entityId)}&hops=${hops}`;
  return request(url);
}

/**
 * Fetch the tenant-wide subgraph (capped at ``limit`` cases).
 * @param {string} tenantId
 * @param {number} [limit=200]
 * @returns {Promise<GraphPayload>}
 */
export async function getGlobalGraph(tenantId, limit = 200) {
  if (!tenantId) {
    throw new TypeError('getGlobalGraph: tenantId is required');
  }
  return request(
    `/api/v1/graph/global?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`
  );
}

/**
 * Fetch metadata for one edge.
 * @param {string} src
 * @param {string} tgt
 * @returns {Promise<EdgeDetail>}
 */
export async function getEdgeDetails(src, tgt) {
  if (!src || !tgt) {
    throw new TypeError('getEdgeDetails: src and tgt are required');
  }
  return request(
    `/api/v1/graph/edges?src=${encodeURIComponent(src)}&tgt=${encodeURIComponent(tgt)}`
  );
}

/**
 * True if the error indicates the graph feature is disabled
 * (404 from the backend because ``enable_case_space_graph``
 * is False).  Used by the InspectorGraphTab to render a
 * non-error "feature disabled" hint instead of a red banner.
 *
 * @param {unknown} err
 * @returns {boolean}
 */
export function isGraphDisabled(err) {
  if (!err) return false;
  const msg = String(err?.message ?? err);
  return /DANWA_ENABLE_CASE_SPACE_GRAPH/.test(msg) || /404/.test(msg);
}
