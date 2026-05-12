/**
 * Input Composer API client functions.
 */

const BASE = '/api/v1';

export async function listInputPlugins() {
  const res = await fetch(`${BASE}/input-plugins`);
  if (!res.ok) throw new Error(`Failed to list plugins: ${res.status}`);
  return res.json();
}

export async function submitInput(pluginKey, config = {}, topic = '', rawData = {}) {
  const res = await fetch(`${BASE}/input/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plugin_key: pluginKey, config, topic, raw_data: rawData }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Submit failed: ${res.status} ${detail}`);
  }
  return res.json();
}

export async function getInputJobStatus(jobId) {
  const res = await fetch(`${BASE}/input/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get job: ${res.status}`);
  return res.json();
}

export async function deleteInputJob(jobId) {
  const res = await fetch(`${BASE}/input/jobs/${jobId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw new Error(`Delete failed: ${res.status}`);
}

export async function approveA2A(taskId) {
  const res = await fetch(`${BASE}/input/a2a/${taskId}/approve`, { method: 'POST' });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Approve failed: ${res.status} ${detail}`);
  }
  return res.json();
}

export async function rejectA2A(taskId) {
  const res = await fetch(`${BASE}/input/a2a/${taskId}/reject`, { method: 'POST' });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Reject failed: ${res.status} ${detail}`);
  }
  return res.json();
}

/**
 * Launch a workflow execution from a completed input job.
 * @param {string} jobId - The completed InputJob ID.
 * @param {object} [options] - Launch options.
 * @param {string} [options.workflow_id] - Specific workflow ID (optional).
 * @param {number} [options.max_rounds] - Max debate rounds.
 * @param {number} [options.consensus_threshold] - Consensus threshold.
 * @param {string} [options.language] - Language code.
 * @param {string} [options.project_id] - Project ID.
 * @returns {Promise<{ session_id: string, status: string, workflow_id: string }>}
 */
export async function launchWorkflow(jobId, options = {}) {
  const res = await fetch(`${BASE}/input/launch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, ...options }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Launch failed: ${res.status} ${detail}`);
  }
  return res.json();
}
