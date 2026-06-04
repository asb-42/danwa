/**
 * Blueprint Canvas — Edge-to-Backend Wiring.
 *
 * Legacy semantic edge wiring (defines_role, implements_role, prompted_by,
 * overrides_prompt, uses_llm, uses_tone) was removed in Phase 3 deprecation.
 *
 * The remaining semantic edges (uses_llm, uses_core, uses_tone) and
 * control flow edges do not require FK wiring — they are visual-only
 * connections stored in the canvas layout.
 */

/**
 * Wire a semantic edge — no-op (legacy wiring removed).
 * @returns {Promise<boolean>} false (no wiring needed)
 */
export async function wireEdgeOnConnect(_edge, _nodes, _updateNodeData) {
  return false;
}

/**
 * Unwire a semantic edge — no-op (legacy wiring removed).
 * @returns {Promise<boolean>} false (no wiring needed)
 */
export async function wireEdgeOnDisconnect(_edge, _nodes, _updateNodeData) {
  return false;
}

/**
 * Check if an edge type is a semantic edge that requires backend wiring.
 * @returns {boolean} false (no edges require wiring)
 */
export function isSemanticEdge(_edgeType) {
  return false;
}
