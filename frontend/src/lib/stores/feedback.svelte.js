/**
 * Unified Feedback Store (Svelte 5 Runes)
 *
 * Single source of truth for all user-facing feedback signals:
 * - Activity log (append-only, timestamped)
 * - Current status message (LLM thinking, layout computing, etc.)
 * - Classified errors (rate_limit, timeout, content_filter, network)
 * - LLM state tracking
 * - Layout state tracking
 *
 * Usage:
 *   import { feedbackStore } from './stores/feedback.svelte.js';
 *   feedbackStore.logActivity('llm', 'strategist', 'Calling GPT-4o…');
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
  /** @type {string|null} */
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
   * Set the current request ID for log correlation.
   * @param {string|null} id
   */
  setRequestId(id) {
    this.requestId = id;
  }

  /** Reset all feedback state (e.g. on workflow complete). */
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
   * Export the activity log as a JSON string.
   * @returns {string} JSON-formatted activity log
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
