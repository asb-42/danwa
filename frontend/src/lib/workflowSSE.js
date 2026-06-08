/**
 * Workflow SSE — Server-Sent Events connection for workflow execution.
 *
 * Establishes a persistent SSE connection to the backend workflow
 * execution stream and dispatches named events to typed handler
 * callbacks. Supports automatic reconnection with exponential backoff.
 *
 * Named events supported:
 * - **Workflow lifecycle:** `workflow.started`, `workflow.complete`,
 *   `workflow.paused`, `workflow.resumed`, `workflow.cancelled`
 * - **Node lifecycle:** `node.start`, `node.complete`, `node.error`
 * - **Decision/gate:** `gate.decision`
 * - **LLM feedback (Unified Feedback System):** `llm.call_started`,
 *   `llm.error`, `llm.fallback`
 * - **Interjections:** `interjection.received`, `interjection.consumed`
 * - **Consensus:** `consensus.reached`
 * - **HITL:** `hitl_query`, `hitl_response`, `hitl_inject`,
 *   `hitl_inject_consumed`, `hitl_pause`, `hitl_timeout`
 * - **Misc:** `round_update`, `status`, `ping`, `web_search`
 */

const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Create an SSE connection for a workflow execution session.
 *
 * Returns a cleanup function that closes the `EventSource` and cancels
 * any pending reconnection timer. The connection auto-reconnects with
 * exponential backoff (1 s → 30 s cap) until a terminal event
 * (`workflow.complete` or `node.error`) is received.
 *
 * @param {string} sessionId - The workflow session ID.
 * @param {Object} handlers - Event handler map.
 * @param {Function} [handlers.onEvent] - Generic handler called for **every** event.
 * @param {Function} [handlers.onWorkflowStarted] - `workflow.started` event.
 * @param {Function} [handlers.onNodeStart] - `node.start` event.
 * @param {Function} [handlers.onNodeComplete] - `node.complete` event.
 * @param {Function} [handlers.onNodeError] - `node.error` event.
 * @param {Function} [handlers.onInterjectionReceived] - `interjection.received` event.
 * @param {Function} [handlers.onInterjectionConsumed] - `interjection.consumed` event.
 * @param {Function} [handlers.onConsensusReached] - `consensus.reached` event.
 * @param {Function} [handlers.onWorkflowComplete] - `workflow.complete` event.
 * @param {Function} [handlers.onWorkflowPaused] - `workflow.paused` event.
 * @param {Function} [handlers.onWorkflowResumed] - `workflow.resumed` event.
 * @param {Function} [handlers.onLLMCallStarted] - `llm.call_started` event with model, provider, and request_id.
 * @param {Function} [handlers.onLLMError] - `llm.error` event carrying classified error info
 *   (`error_class`, `message`, `raw_error`, `node_id`) for display in the ErrorPanel.
 * @param {Function} [handlers.onLLMFallback] - `llm.fallback` event fired when a provider
 *   failure triggers an automatic switch to a fallback LLM profile.
 * @param {Function} [handlers.onError] - SSE connection error handler.
 * @param {Function} [handlers.onOpen] - Connection established handler.
 * @returns {Function} cleanup — Call to close the connection and stop reconnection.
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
    'gate.decision': 'onGateDecision',
    'interjection.received': 'onInterjectionReceived',
    'interjection.consumed': 'onInterjectionConsumed',
    'consensus.reached': 'onConsensusReached',
    'round_update': 'onRoundUpdate',
    'workflow.complete': 'onWorkflowComplete',
    'workflow.paused': 'onWorkflowPaused',
    'workflow.resumed': 'onWorkflowResumed',
    'status': 'onStatus',
    'ping': 'onPing',
    'llm.call_started': 'onLLMCallStarted',
    'llm.error': 'onLLMError',
    'llm.fallback': 'onLLMFallback',
    'web_search': 'onWebSearch',
    'hitl_query': 'onHITLQuery',
    'hitl_response': 'onHITLResponse',
    'hitl_inject': 'onHITLInject',
    'hitl_inject_consumed': 'onHITLInjectConsumed',
    'hitl_pause': 'onHITLPause',
    'hitl_timeout': 'onHITLTimeout',
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
      'gate.decision',
      'interjection.received',
      'interjection.consumed',
      'consensus.reached',
      'round_update',
      'workflow.complete',
      'workflow.paused',
      'workflow.resumed',
      'status',
      'ping',
      'connected',
      'llm.call_started',
      'llm.error',
      'llm.fallback',
      'web_search',
      'hitl_query',
      'hitl_response',
      'hitl_inject',
      'hitl_inject_consumed',
      'hitl_pause',
      'hitl_timeout',
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
