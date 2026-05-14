/**
 * Svelte writable stores for global state.
 */

import { writable } from 'svelte/store';

/** Current route (hash-based) */
export const route = writable('dashboard');

/** Route parameters (e.g. debate ID from #/debate/{id}) */
export const routeParams = writable([]);

/** Backend health status */
export const healthStatus = writable({ status: 'unknown', version: '' });

/** Application version loaded from the /api/v1/config/version endpoint */
export const appVersion = writable('');

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

/**
 * Create a writable store that persists to localStorage.
 */
function persisted(key, defaultValue) {
  let initial = defaultValue;
  if (typeof localStorage !== 'undefined') {
    try {
      const stored = localStorage.getItem(key);
      if (stored !== null) {
        initial = JSON.parse(stored);
      }
    } catch { /* ignore parse errors */ }
  }
  const store = writable(initial);
  if (typeof localStorage !== 'undefined') {
    store.subscribe((value) => {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch { /* ignore quota errors */ }
    });
  }
  return store;
}

/** Active project — persisted to localStorage. Stores { id, name }. */
export const activeProject = persisted('danwa.activeProject', null);

/** Selected LLM profile ID for debates (set in ConfigView, read in DebateView) */
export const selectedLLMProfile = persisted('danwa.selectedLLMProfile', 'openrouter-claude');

/** Selected prompt variant for debates */
export const selectedPromptVariant = persisted('danwa.selectedPromptVariant', 'default');

/** Selected agent persona IDs per role */
export const selectedPersonas = persisted('danwa.selectedPersonas', {
  strategist: 'strategist-default',
  critic: 'critic-default',
  optimizer: 'optimizer-default',
  moderator: 'moderator-default',
});

/** When true, DebateView auto-starts the current debate on mount */
export const autoStartDebate = writable(false);

/** Currently selected module ID for translation */
export const selectedModuleId = writable(null);

/** Translation results { moduleId, results[] } */
export const translationResults = writable({});

/** Supported languages list */
export const supportedLanguages = writable([]);

/** Translation statistics { moduleId, stats } */
export const translationStatistics = writable({});
