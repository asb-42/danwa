/**
 * Unified Feedback Store (Svelte 5 Runes)
 *
 * Single source of truth for all user-facing feedback signals in the
 * Unified Feedback System. Exposes Svelte 5 `$state` runes so components
 * react to changes automatically.
 *
 * Subsystems managed:
 * - **Activity log** — append-only, timestamped, pruned at 500 entries.
 * - **Status message** — current operation indicator (LLM thinking, layout
 *   computing, etc.) with automatic type-based color coding.
 * - **Classified errors** — user-friendly error cards grouped by class
 *   (rate_limit, timeout, content_filter, network, unknown).
 * - **LLM state** — tracks idle/calling/streaming/error plus the active
 *   model and provider names.
 * - **Layout state** — tracks idle/computing/error for the layout engine.
 * - **Request correlation** — a `requestId` attached to every log entry
 *   so entries from the same workflow run can be filtered or exported
 *   together.
 *
 * @example
 *   import { feedbackStore } from './stores/feedback.svelte.js';
 *   feedbackStore.setRequestId('abc-123');
 *   feedbackStore.logActivity('llm', 'strategist', 'Calling GPT-4o…');
 *   feedbackStore.setLlmState('calling', 'gpt-4o', 'openrouter');
 */

class FeedbackStore {
  // ─── Activity Log (append-only) ──────────────────────────────────
  /** @type {Array<{id: string, timestamp: number, type: string, source: string, message: string, details?: any, level: 'info'|'warn'|'error'}>} */
  activityLog = $state([]);

  // ─── Current Status ──────────────────────────────────────────────
  /** @type {{text: string, type: string, since: number} | null} */
  statusMessage = $state(null);

  // ─── Classified Errors ───────────────────────────────────────────
  /** @type {Array<{id: string, errorClass: string, message: string, rawError?: string, nodeId?: string, timestamp: number}>} */
  activeErrors = $state([]);

  // ─── LLM State ──────────────────────────────────────────────────
  /** @type {'idle'|'calling'|'streaming'|'error'} */
  llmState = $state('idle');
  /** @type {string|null} */
  llmModel = $state(null);
  /** @type {string|null} */
  llmProvider = $state(null);

  // ─── Layout State ────────────────────────────────────────────────
  /** @type {'idle'|'computing'|'error'} */
  layoutState = $state('idle');

  // ─── Request Correlation ─────────────────────────────────────────
  /**
   * Current request ID for log/SSE correlation. Injected by the
   * workflow runner and attached to every activity log entry so that
   * entries from a single workflow execution can be grouped or exported.
   * @type {string|null}
   */
  requestId = $state(null);

  // ─── Max log entries before oldest are pruned ────────────────────
  #MAX_LOG_ENTRIES = 500;

  // ─── Actions ─────────────────────────────────────────────────────

  /**
   * Append an entry to the activity log.
   * @param {string} type - Category: 'llm', 'workflow', 'node', 'system', 'error'
   * @param {string} source - Originating component/role (e.g. 'strategist', 'elk', 'sse')
   * @param {string} message - Human-readable message
   * @param {any} [details] - Optional structured details
   * @param {'info'|'warn'|'error'} [level='info'] - Severity level
   */
  logActivity(type, source, message, details = undefined, level = 'info') {
    const entry = {
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      type,
      source,
      message,
      level,
      ...(this.requestId ? { requestId: this.requestId } : {}),
    };
    if (details !== undefined) entry.details = details;

    this.activityLog = [...this.activityLog, entry];

    // Prune old entries
    if (this.activityLog.length > this.#MAX_LOG_ENTRIES) {
      this.activityLog = this.activityLog.slice(-this.#MAX_LOG_ENTRIES);
    }
  }

  /**
   * Set the current status message.
   * @param {string} text - Status text to display
   * @param {string} type - Category (e.g. 'llm', 'layout', 'workflow')
   */
  setStatus(text, type = 'general') {
    this.statusMessage = { text, type, since: Date.now() };
  }

  /** Clear the current status message. */
  clearStatus() {
    this.statusMessage = null;
  }

  /**
   * Report a classified error.
   * @param {string} errorClass - One of: rate_limit, timeout, content_filter, network, unknown
   * @param {string} message - User-friendly error message
   * @param {string} [rawError] - Raw error string for debugging
   * @param {string} [nodeId] - Node that produced the error
   */
  reportError(errorClass, message, rawError = undefined, nodeId = undefined) {
    const entry = {
      id: crypto.randomUUID(),
      errorClass,
      message,
      rawError,
      nodeId,
      timestamp: Date.now(),
    };
    this.activeErrors = [...this.activeErrors, entry];
    this.logActivity('error', nodeId || 'system', message, { errorClass, rawError }, 'error');
  }

  /**
   * Dismiss an error by ID.
   * @param {string} id
   */
  dismissError(id) {
    this.activeErrors = this.activeErrors.filter(e => e.id !== id);
  }

  /** Dismiss all errors. */
  dismissAllErrors() {
    this.activeErrors = [];
  }

  /**
   * Set the LLM state and optionally the model/provider.
   * @param {'idle'|'calling'|'streaming'|'error'} state
   * @param {string} [model]
   * @param {string} [provider]
   */
  setLlmState(state, model = null, provider = null) {
    this.llmState = state;
    if (model !== null) this.llmModel = model;
    if (provider !== null) this.llmProvider = provider;

    if (state === 'calling') {
      const modelLabel = model || this.llmModel || '…';
      this.setStatus(`LLM calling ${modelLabel}…`, 'llm');
    } else if (state === 'idle') {
      if (this.statusMessage?.type === 'llm') {
        this.clearStatus();
      }
    }
  }

  /**
   * Set the layout engine state.
   * @param {'idle'|'computing'|'error'} state
   */
  setLayoutState(state) {
    this.layoutState = state;
    if (state === 'computing') {
      this.setStatus('Layout engine computing…', 'layout');
    } else if (state === 'idle') {
      if (this.statusMessage?.type === 'layout') {
        this.clearStatus();
      }
    }
  }

  /**
   * Set the current request ID for log/SSE correlation.
   *
   * Called by the workflow runner at the start of each execution so
   * all subsequent log entries carry the same `requestId`. Pass
   * `null` to clear the correlation (e.g. on workflow complete).
   *
   * @param {string|null} id - The request UUID, or `null` to clear.
   */
  setRequestId(id) {
    this.requestId = id;
  }

  /**
   * Reset all feedback state to initial values.
   *
   * Clears the activity log, status message, active errors, LLM/layout
   * state, and request ID. Typically called when a workflow completes
   * or the user starts a new session.
   */
  clearAll() {
    this.activityLog = [];
    this.statusMessage = null;
    this.activeErrors = [];
    this.llmState = 'idle';
    this.llmModel = null;
    this.llmProvider = null;
    this.layoutState = 'idle';
    this.requestId = null;
  }

  /**
   * Export the activity log and active errors as a JSON string.
   *
   * The exported object includes the current `requestId`, an
   * `exportedAt` ISO timestamp, the full `entries` array, and any
   * unresolved `errors`. Useful for debugging or sharing with support.
   *
   * @returns {string} Pretty-printed JSON containing request metadata,
   *   activity entries, and active errors.
   */
  exportLog() {
    return JSON.stringify({
      requestId: this.requestId,
      exportedAt: new Date().toISOString(),
      entries: this.activityLog,
      errors: this.activeErrors,
    }, null, 2);
  }
}

/** Singleton feedback store instance. */
export const feedbackStore = new FeedbackStore();
