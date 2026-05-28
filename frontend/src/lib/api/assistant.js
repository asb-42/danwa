/**
 * Danwa Assistant API functions.
 */

import { request } from './core.js';

/** Create a new chat session with the Danwa assistant. */
export function createAssistantSession(title = 'New Conversation', profileId = null) {
  const params = new URLSearchParams({ title });
  if (profileId) params.append('profile_id', profileId);
  return request(`/api/v1/assistant/sessions?${params}`, { method: 'POST' });
}

/** List all active chat sessions. */
export function listAssistantSessions() {
  return request('/api/v1/assistant/sessions');
}

/** Get a specific session with full message history. */
export function getAssistantSession(sessionId) {
  return request(`/api/v1/assistant/sessions/${sessionId}`);
}

/** Delete a chat session. */
export function deleteAssistantSession(sessionId) {
  return request(`/api/v1/assistant/sessions/${sessionId}`, { method: 'DELETE' });
}

/** Send a message to the assistant and get a response. */
export function sendAssistantMessage(sessionId, message, profileId = null) {
  const params = new URLSearchParams({ message });
  if (profileId) params.append('profile_id', profileId);
  return request(`/api/v1/assistant/sessions/${sessionId}/chat?${params}`, {
    method: 'POST',
  });
}

/** Quick chat — creates session and sends message in one call. */
export function quickAssistantChat(message, profileId = null) {
  const params = new URLSearchParams({ message });
  if (profileId) params.append('profile_id', profileId);
  return request(`/api/v1/assistant/chat?${params}`, { method: 'POST' });
}

/**
 * Get current LLM activity status (active calls, recent history, token totals).
 * Designed to be polled every 3-5 seconds by the header indicator.
 */
export function getLLMActivity() {
  return request('/api/v1/monitor/activity');
}
