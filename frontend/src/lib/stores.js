/**
 * Svelte writable stores for global state.
 */

import { writable } from 'svelte/store';

/** Current route (hash-based) */
export const route = writable('dashboard');

/** Backend health status */
export const healthStatus = writable({ status: 'unknown', version: '' });

/** Current debate state */
export const currentDebate = writable(null);

/** List of recent debates */
export const debates = writable([]);

/** Audit events for current debate */
export const auditEvents = writable([]);

/** SSE connection status */
export const sseConnected = writable(false);

/** Global error message */
export const error = writable(null);

/** Loading state */
export const loading = writable(false);

/** Selected LLM profile ID for debates (set in ConfigView, read in DebateView) */
export const selectedLLMProfile = writable('openrouter-claude');

/** Selected prompt variant for debates */
export const selectedPromptVariant = writable('default');

/** Selected agent persona IDs per role */
export const selectedPersonas = writable({
  strategist: 'strategist-default',
  critic: 'critic-default',
  optimizer: 'optimizer-default',
  moderator: 'moderator-default',
});
