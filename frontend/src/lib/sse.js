/**
 * Server-Sent Events (SSE) connection manager.
 * Handles connect, reconnect with backoff, and event dispatching.
 *
 * Supports both default messages and named SSE events.
 */

import { sseConnected } from './stores.js';

const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Create an SSE connection for a debate.
 * Returns a cleanup function to close the connection.
 *
 * Named events (agent_started, agent_output, round_update, status_change)
 * are dispatched to onEvent with the parsed data.
 *
 * @param {string} debateId
 * @param {Object} handlers - { onEvent, onError, onOpen }
 * @returns {Function} cleanup
 */
export function createSSE(debateId, handlers = {}) {
  const url = `${API_BASE}/api/v1/debate/${debateId}/stream`;
  let eventSource = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;

  function connect() {
    eventSource = new EventSource(url);

    eventSource.onopen = () => {
      sseConnected.set(true);
      reconnectDelay = 1000; // reset backoff
      handlers.onOpen?.();
    };

    // Handle default (unnamed) messages
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handlers.onEvent?.(data);
      } catch {
        handlers.onEvent?.({ type: 'raw', data: event.data });
      }
    };

    // Handle named events from the backend
    const namedEvents = [
      'agent_started',
      'agent_output',
      'round_update',
      'status_change',
      'error',
      'keepalive',
    ];

    for (const eventName of namedEvents) {
      eventSource.addEventListener(eventName, (event) => {
        try {
          const data = JSON.parse(event.data);
          handlers.onEvent?.(data);
        } catch {
          handlers.onEvent?.({ type: 'raw', data: event.data });
        }
      });
    }

    eventSource.onerror = () => {
      sseConnected.set(false);
      eventSource.close();
      handlers.onError?.();

      // Reconnect with exponential backoff
      reconnectTimer = setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        connect();
      }, reconnectDelay);
    };
  }

  connect();

  return {
    close: () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (eventSource) eventSource.close();
      sseConnected.set(false);
    },
  };
}
