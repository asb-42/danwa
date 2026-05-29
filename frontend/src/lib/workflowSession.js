/**
 * Active Workflow Session — localStorage-persisted state.
 *
 * Allows the sidebar and canvas to track a running workflow execution
 * across page navigations.
 */

const STORAGE_KEY = 'danwa_active_workflow_session';

/**
 * @typedef {Object} ActiveWorkflowSession
 * @property {string} sessionId
 * @property {string} workflowId
 * @property {string} workflowName
 * @property {string} context
 * @property {string} startedAt - ISO timestamp
 * @property {'running'|'paused'|'completed'|'failed'|'cancelled'} status
 */

/** @returns {ActiveWorkflowSession|null} */
export function getActiveWorkflowSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * @param {ActiveWorkflowSession} session
 */
export function setActiveWorkflowSession(session) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // localStorage may be full or disabled
  }
}

export function clearActiveWorkflowSession() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

/**
 * Update a single field without overwriting other fields.
 * @param {string} key
 * @param {*} value
 */
export function patchActiveWorkflowSession(key, value) {
  const current = getActiveWorkflowSession();
  if (current) {
    setActiveWorkflowSession({ ...current, [key]: value });
  }
}
