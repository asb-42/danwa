/**
 * Interactive Debate Mode stores (Svelte 5 Runes).
 *
 * Provides reactive state management for the debate tree,
 * SSE streaming, and event operations.
 */

import { writable, derived } from 'svelte/store';
import {
  createSpace,
  listSpaces,
  listEvents,
  appendEvent,
  getFullTree,
  createEventStream,
  synthesizeContext,
  triggerAgent,
  triggerA2A,
  triggerHITL,
} from './api';

/**
 * @typedef {import('./api').DebateSpace} DebateSpace
 * @typedef {import('./api').DebateEvent} DebateEvent
 */

// ---------------------------------------------------------------------------
// Space Store
// ---------------------------------------------------------------------------

function createSpaceStore() {
  const { subscribe, set, update } = writable({
    current: /** @type {DebateSpace | null} */ (null),
    spaces: /** @type {DebateSpace[]} */ ([]),
    loading: false,
    error: /** @type {string | null} */ (null),
  });

  return {
    subscribe,

    async create(title, description) {
      update((s) => ({ ...s, loading: true, error: null }));
      try {
        const space = await createSpace({ title, description });
        update((s) => ({
          current: space,
          spaces: [space, ...s.spaces],
          loading: false,
        }));
        return space;
      } catch (err) {
        update((s) => ({ ...s, loading: false, error: err.message }));
        throw err;
      }
    },

    async loadSpaces() {
      update((s) => ({ ...s, loading: true }));
      try {
        const spaces = await listSpaces({ limit: 50 });
        update((s) => ({ ...s, spaces, loading: false }));
      } catch (err) {
        update((s) => ({ ...s, loading: false, error: err.message }));
      }
    },

    setCurrent(space) {
      update((s) => ({ ...s, current: space }));
    },
  };
}

// ---------------------------------------------------------------------------
// Event Store (Debate Tree)
// ---------------------------------------------------------------------------

function createEventStore() {
  const { subscribe, set, update } = writable({
    events: /** @type {Map<string, DebateEvent>} */ (new Map()),
    rootIds: /** @type {string[]} */ ([]),
    loading: false,
    error: /** @type {string | null} */ (null),
    lastEventId: /** @type {string | null} */ (null),
    selectedEventId: /** @type {string | null} */ (null),
  });

  /** @type {EventSource | null} */
  let eventSource = null;

  return {
    subscribe,

    /**
     * Load full tree for a space
     */
    async loadTree(spaceId) {
      update((s) => ({ ...s, loading: true, error: null }));
      try {
        const events = await getFullTree(spaceId);
        const eventMap = new Map();
        const rootIds = [];

        for (const evt of events) {
          eventMap.set(evt.event_id, evt);
          if (!evt.parent_id) {
            rootIds.push(evt.event_id);
          }
        }

        update((s) => ({
          events: eventMap,
          rootIds,
          loading: false,
          lastEventId: events.length > 0 ? events[events.length - 1].event_id : null,
        }));
      } catch (err) {
        update((s) => ({ ...s, loading: false, error: err.message }));
      }
    },

    /**
     * Start SSE streaming for a space
     */
    startStreaming(spaceId) {
      this.stopStreaming();

      const lastId = this._getLastEventId();
      eventSource = createEventStream(spaceId, (event) => {
        this._addEvent(event);
      }, lastId);
    },

    /**
     * Stop SSE streaming
     */
    stopStreaming() {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    },

    /**
     * Append a new event
     */
    async append(spaceId, params) {
      try {
        const event = await appendEvent(spaceId, params);
        this._addEvent(event);
        return event;
      } catch (err) {
        update((s) => ({ ...s, error: err.message }));
        throw err;
      }
    },

    /**
     * Trigger an agent response
     */
    async triggerAgent(spaceId, params) {
      try {
        const event = await triggerAgent(spaceId, params);
        this._addEvent(event);
        return event;
      } catch (err) {
        update((s) => ({ ...s, error: err.message }));
        throw err;
      }
    },

    /**
     * Trigger an A2A request
     */
    async triggerA2A(spaceId, params) {
      try {
        const event = await triggerA2A(spaceId, params);
        this._addEvent(event);
        return event;
      } catch (err) {
        update((s) => ({ ...s, error: err.message }));
        throw err;
      }
    },

    /**
     * Trigger a HITL request
     */
    async triggerHITL(spaceId, params) {
      try {
        const event = await triggerHITL(spaceId, params);
        this._addEvent(event);
        return event;
      } catch (err) {
        update((s) => ({ ...s, error: err.message }));
        throw err;
      }
    },

    /**
     * Synthesize context for an event
     */
    async synthesizeContext(spaceId, eventId, params) {
      return synthesizeContext(spaceId, eventId, params);
    },

    /**
     * Clear all events
     */
    clear() {
      this.stopStreaming();
      set({
        events: new Map(),
        rootIds: [],
        loading: false,
        error: null,
        lastEventId: null,
        selectedEventId: null,
      });
    },

    /**
     * Set the selected event (for detail panel)
     */
    setSelectedEvent(eventId) {
      update((s) => ({ ...s, selectedEventId: eventId }));
    },

    // --- Internal helpers ---

    /** @param {DebateEvent} event */
    _addEvent(event) {
      update((s) => {
        const newEvents = new Map(s.events);
        newEvents.set(event.event_id, event);

        let newRootIds = s.rootIds;
        if (!event.parent_id && !newRootIds.includes(event.event_id)) {
          newRootIds = [...newRootIds, event.event_id];
        }

        return {
          ...s,
          events: newEvents,
          rootIds: newRootIds,
          lastEventId: event.event_id,
        };
      });
    },

    _getLastEventId() {
      let lastId = null;
      subscribe((s) => {
        lastId = s.lastEventId;
      })();
      return lastId;
    },
  };
}

// ---------------------------------------------------------------------------
// Fork Modal Store
// ---------------------------------------------------------------------------

function createForkModalStore() {
  const { subscribe, set } = writable({
    open: false,
    /** @type {DebateEvent | null} */ targetEvent: null,
  });

  return {
    subscribe,
    open: (event) => set({ open: true, targetEvent: event }),
    close: () => set({ open: false, targetEvent: null }),
  };
}

// ---------------------------------------------------------------------------
// Exported stores
// ---------------------------------------------------------------------------

export const spaceStore = createSpaceStore();
export const eventStore = createEventStore();
export const forkModalStore = createForkModalStore();

// ---------------------------------------------------------------------------
// Derived stores
// ---------------------------------------------------------------------------

/**
 * Returns events as an array (for SvelteFlow nodes)
 */
export const eventsArray = derived(eventStore, ($store) => {
  return Array.from($store.events.values());
});

/**
 * Returns edges derived from parent_id relationships
 */
export const debateEdges = derived(eventStore, ($store) => {
  const edges = [];
  for (const [id, event] of $store.events) {
    if (event.parent_id) {
      edges.push({
        id: `e-${event.parent_id}-${id}`,
        source: event.parent_id,
        target: id,
      });
    }
  }
  return edges;
});
