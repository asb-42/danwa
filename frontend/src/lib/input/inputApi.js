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
