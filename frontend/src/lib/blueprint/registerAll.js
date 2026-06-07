/**
 * Blueprint Canvas — Register all node and edge types.
 *
 * Thin orchestrator that delegates to three focused modules:
 *   * ``registerAssetNodes`` — ``llm-profile``, ``agent-core``,
 *     ``tone-profile`` (3 reusable building blocks).
 *   * ``registerWorkflowNodes`` — all ``wf-*`` workflow node types
 *     (structure + agent roles + bundle agents).
 *   * ``registerEdges`` — ``semantic`` + ``control_flow`` edges.
 *
 * Split out of the previous 568-line monolithic file in audit L5.
 * Public surface (``registerAllNodeTypes``) is unchanged so callers
 * (``Palette.svelte``, ``BlueprintCanvas.svelte``) need no edits.
 *
 * Should be called once during app initialization; idempotent.
 */

import { registerAssetNodes } from './registerAssetNodes.js';
import { registerWorkflowNodes } from './registerWorkflowNodes.js';
import { registerEdges } from './registerEdges.js';

export function registerAllNodeTypes() {
  registerAssetNodes();
  registerWorkflowNodes();
  registerEdges();
}

export { registerAssetNodes, registerWorkflowNodes, registerEdges };
