/**
 * HITL (Human-in-the-Loop) Svelte 5 stores.
 *
 * Manages reactive state for bidirectional interactions during debates:
 * - Active interrupt (agent waiting for user response)
 * - Pause state
 * - Interaction history
 * - HITL configuration
 */

/** @type {import('svelte/store').Writable<Object|null>} */
import { writable, derived } from 'svelte/store';

/** Current HITL status for the active debate */
export const hitlStatus = writable({
  hitl_enabled: false,
  hitl_mode: 'off',
  is_paused: false,
  active_interrupt: null,
  total_interactions: 0,
  interactions_by_type: {},
  round_interrupt_count: 0,
  max_interrupts_per_round: 3,
});

/** Interaction log for the active debate */
export const hitlInteractions = writable([]);

/** Whether the agent query modal is visible */
export const showAgentQueryModal = writable(false);

/** Current agent query data (for the modal) */
export const currentAgentQuery = writable(null);

/** Whether the inject panel is expanded */
export const showInjectPanel = writable(false);

/** Whether HITL is actively engaged (paused or has active interrupt) */
export const hitlActive = derived(
  hitlStatus,
  ($status) => $status.is_paused || $status.active_interrupt !== null
);

/** Number of pending interactions */
export const pendingInteractionCount = derived(
  hitlStatus,
  ($status) => {
    const types = $status.interactions_by_type || {};
    return (types.inject || 0) + (types.query || 0);
  }
);
