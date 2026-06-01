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

/** Active case — persisted to localStorage. Stores { id, title }. */
export const activeCase = persisted('danwa.activeCase', null);

/** Tags cache per tenant — { tenant_id: [tag, ...] } */
export const tagsByTenant = persisted('danwa.tagsByTenant', {});

/** User's preferred UI language — persisted to localStorage.
 * This is the single source of truth for the user's language preference.
 * It takes precedence over browser settings and is used for:
 * - UI translations
 * - Debate language (when not explicitly specified)
 * - Kitsune assistant responses
 * - Prompt loading
 * Falls back to 'de' (German) if not set.
 */
export const userLanguage = persisted('danwa.userLanguage', 'de');

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

/** Toast notifications — { id, message, type, timeout?, dismissible? } */
export const toasts = writable([]);

/** Remove a toast by ID. */
export function removeToast(id) {
  toasts.update((current) => current.filter((t) => t.id !== id));
}

/** Add a new toast. */
export function addToast({ message, type = 'info', timeout = 5000, dismissible = true }) {
  const id = crypto.randomUUID();
  toasts.update((current) => [...current, { id, message, type, timeout, dismissible }]);
  if (timeout > 0) {
    setTimeout(() => removeToast(id), timeout);
  }
  return id;
}

/** Backup-Stores (Sprint 18) */
export const backupConfig = persisted('danwa.backupConfig', {
	autoOnShutdown: false,
	retentionCount: 0,
	encrypt: false
});

/** Liste der verfügbaren Backups */
export const backups = writable([]);

/** Aktuell geladene Backup-Details (Dateiliste) */
export const backupDetails = writable(null);

/** Ladezustand für Backups */
export const isLoadingBackups = writable(false);
