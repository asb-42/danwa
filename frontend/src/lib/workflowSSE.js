/**
 * Workflow SSE — Server-Sent Events connection for workflow execution.
 *
 * Same pattern as createSSE() but for workflow-specific events.
 * Supports named events: workflow.started, node.start, node.complete,
 * node.error, interjection.received, consensus.reached, workflow.complete,
 * workflow.paused, workflow.resumed.
 */

const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Create an SSE connection for a workflow execution session.
 * Returns a cleanup function to close the connection.
 *
 * @param {string} sessionId - The workflow session ID.
 * @param {Object} handlers - Event handlers.
 * @param {Function} [handlers.onEvent] - Generic event handler (receives all events).
 * @param {Function} [handlers.onWorkflowStarted] - workflow.started event.
 * @param {Function} [handlers.onNodeStart] - node.start event.
 * @param {Function} [handlers.onNodeComplete] - node.complete event.
 * @param {Function} [handlers.onNodeError] - node.error event.
 * @param {Function} [handlers.onInterjectionReceived] - interjection.received event.
 * @param {Function} [handlers.onConsensusReached] - consensus.reached event.
 * @param {Function} [handlers.onWorkflowComplete] - workflow.complete event.
 * @param {Function} [handlers.onWorkflowPaused] - workflow.paused event.
 * @param {Function} [handlers.onWorkflowResumed] - workflow.resumed event.
 * @param {Function} [handlers.onError] - Error handler.
 * @param {Function} [handlers.onOpen] - Connection open handler.
 * @returns {Function} cleanup — Call to close the connection.
 */
export function createWorkflowSSE(sessionId, handlers = {}) {
  const url = `${API_BASE}/api/v1/workflow-exec/${sessionId}/stream`;
  let eventSource = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  let settled = false;

  /** Map of event names to handler function names */
  const eventHandlerMap = {
    'workflow.started': 'onWorkflowStarted',
    'node.start': 'onNodeStart',
    'node.complete': 'onNodeComplete',
    'node.error': 'onNodeError',
    'interjection.received': 'onInterjectionReceived',
    'consensus.reached': 'onConsensusReached',
    'round_update': 'onRoundUpdate',
    'workflow.complete': 'onWorkflowComplete',
    'workflow.paused': 'onWorkflowPaused',
    'workflow.resumed': 'onWorkflowResumed',
    'status': 'onStatus',
    'ping': 'onPing',
  };

  function connect() {
    eventSource = new EventSource(url);

    eventSource.onopen = () => {
      reconnectDelay = 1000;
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

    // Handle named events
    const namedEvents = [
      'workflow.started',
      'node.start',
      'node.complete',
      'node.error',
      'interjection.received',
      'consensus.reached',
      'round_update',
      'workflow.complete',
      'workflow.paused',
      'workflow.resumed',
      'status',
      'ping',
      'connected',
    ];

    for (const eventName of namedEvents) {
      eventSource.addEventListener(eventName, (event) => {
        try {
          const data = JSON.parse(event.data);

          // Mark as settled on terminal events
          if (eventName === 'workflow.complete' || eventName === 'node.error') {
            settled = true;
          }

          // Call specific handler if registered
          const handlerKey = eventHandlerMap[eventName];
          if (handlerKey && handlers[handlerKey]) {
            handlers[handlerKey](data);
          }

          // Always call generic handler
          handlers.onEvent?.(data);
        } catch {
          handlers.onEvent?.({ type: 'raw', data: event.data });
        }
      });
    }

    eventSource.onerror = () => {
      if (settled) {
        cleanup();
        return;
      }

      handlers.onError?.(new Error('SSE connection lost'));

      // Reconnect with backoff
      cleanup();
      reconnectTimer = setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        connect();
      }, reconnectDelay);
    };
  }

  function cleanup() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  connect();
  return cleanup;
}
