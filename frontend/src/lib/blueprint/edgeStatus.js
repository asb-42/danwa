/**
 * Edge execution status — shared helper for visual feedback during workflow execution.
 *
 * Edge states: idle | active | completed | taken | skipped
 *   - 'active'    → target node is currently executing (blue animated dash)
 *   - 'completed' → target node finished (green solid)
 *   - 'taken'     → gate decision: this branch was chosen (emerald glow)
 *   - 'skipped'   → gate decision: this branch was NOT chosen (gray faded)
 */

/**
 * Compute CSS class for edge execution status.
 * @param {Record<string, any>|undefined} data - Edge data object
 * @returns {string} CSS class name or empty string
 */
export function edgeStatusClass(data) {
  switch (data?.executionStatus) {
    case 'active':
      return 'edge-active';
    case 'completed':
      return 'edge-completed';
    case 'taken':
      return 'edge-taken';
    case 'skipped':
      return 'edge-skipped';
    default:
      return '';
  }
}
