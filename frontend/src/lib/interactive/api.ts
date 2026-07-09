/**
 * Interactive Debate Mode API client.
 *
 * Handles all communication with the backend's interactive endpoints:
 * - Space CRUD
 * - Event appending
 * - SSE streaming
 * - Context synthesis
 * - Worker triggers
 */

const API_BASE = '/api/v1/interactive';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DebateSpace {
  space_id: string;
  title: string;
  description: string | null;
  project_id: string | null;
  tenant_id: string | null;
  created_by: string | null;
  status: string;
  event_count: number;
  fork_count: number;
  created_at: string;
  updated_at: string;
}

export interface DebateEvent {
  event_id: string;
  space_id: string;
  parent_id: string | null;
  event_type: EventType;
  actor_type: ActorType;
  actor_id: string;
  role: string | null;
  content: string | Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  tokens_input: number | null;
  tokens_output: number | null;
  created_at: string;
}

export type EventType =
  | 'user_message'
  | 'agent_speech'
  | 'tool_call_requested'
  | 'tool_result'
  | 'a2a_request'
  | 'a2a_response'
  | 'hitl_input'
  | 'synthesis';

export type ActorType = 'user' | 'agent' | 'system' | 'a2a';

export interface ContextSynthesis {
  target_event_id: string;
  prompt_context: string;
  metadata: {
    thread_depth: number;
    side_branches_included: number;
    token_budget_used: number;
  };
}

// ---------------------------------------------------------------------------
// Space API
// ---------------------------------------------------------------------------

export async function createSpace(params: {
  title: string;
  description?: string;
  project_id?: string;
  tenant_id?: string;
}): Promise<DebateSpace> {
  const resp = await fetch(`${API_BASE}/spaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!resp.ok) throw new Error(`Failed to create space: ${resp.statusText}`);
  return resp.json();
}

export async function listSpaces(params?: {
  tenant_id?: string;
  project_id?: string;
  limit?: number;
  offset?: number;
}): Promise<DebateSpace[]> {
  const query = new URLSearchParams();
  if (params?.tenant_id) query.set('tenant_id', params.tenant_id);
  if (params?.project_id) query.set('project_id', params.project_id);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));

  const resp = await fetch(`${API_BASE}/spaces?${query}`);
  if (!resp.ok) throw new Error(`Failed to list spaces: ${resp.statusText}`);
  return resp.json();
}

export async function getSpace(spaceId: string): Promise<DebateSpace> {
  const resp = await fetch(`${API_BASE}/spaces/${spaceId}`);
  if (!resp.ok) throw new Error(`Failed to get space: ${resp.statusText}`);
  return resp.json();
}

// ---------------------------------------------------------------------------
// Event API
// ---------------------------------------------------------------------------

export async function appendEvent(
  spaceId: string,
  params: {
    parent_id?: string;
    event_type: EventType;
    actor_type: ActorType;
    actor_id: string;
    role?: string;
    content: string | Record<string, unknown>;
    metadata_json?: Record<string, unknown>;
  }
): Promise<DebateEvent> {
  const resp = await fetch(`${API_BASE}/spaces/${spaceId}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ space_id: spaceId, ...params }),
  });
  if (!resp.ok) throw new Error(`Failed to append event: ${resp.statusText}`);
  return resp.json();
}

export async function listEvents(
  spaceId: string,
  params?: {
    parent_id?: string;
    event_type?: string;
    limit?: number;
  }
): Promise<DebateEvent[]> {
  const query = new URLSearchParams();
  if (params?.parent_id) query.set('parent_id', params.parent_id);
  if (params?.event_type) query.set('event_type', params.event_type);
  if (params?.limit) query.set('limit', String(params.limit));

  const resp = await fetch(`${API_BASE}/spaces/${spaceId}/events?${query}`);
  if (!resp.ok) throw new Error(`Failed to list events: ${resp.statusText}`);
  return resp.json();
}

export async function getThread(
  spaceId: string,
  eventId: string,
  maxDepth?: number
): Promise<DebateEvent[]> {
  const query = new URLSearchParams();
  if (maxDepth !== undefined) query.set('max_depth', String(maxDepth));

  const resp = await fetch(
    `${API_BASE}/spaces/${spaceId}/thread/${eventId}?${query}`
  );
  if (!resp.ok) throw new Error(`Failed to get thread: ${resp.statusText}`);
  return resp.json();
}

export async function getFullTree(spaceId: string): Promise<DebateEvent[]> {
  const resp = await fetch(`${API_BASE}/spaces/${spaceId}/tree`);
  if (!resp.ok) throw new Error(`Failed to get tree: ${resp.statusText}`);
  return resp.json();
}

export async function getTokenUsage(
  spaceId: string
): Promise<{ total_input: number; total_output: number }> {
  const resp = await fetch(`${API_BASE}/spaces/${spaceId}/tokens`);
  if (!resp.ok) throw new Error(`Failed to get token usage: ${resp.statusText}`);
  return resp.json();
}

// ---------------------------------------------------------------------------
// Context Synthesis
// ---------------------------------------------------------------------------

export async function synthesizeContext(
  spaceId: string,
  eventId: string,
  params?: {
    include_side_branches?: boolean;
    agent_role?: string;
  }
): Promise<ContextSynthesis> {
  const query = new URLSearchParams();
  if (params?.include_side_branches !== undefined)
    query.set('include_side_branches', String(params.include_side_branches));
  if (params?.agent_role) query.set('agent_role', params.agent_role);

  const resp = await fetch(
    `${API_BASE}/spaces/${spaceId}/context/${eventId}?${query}`,
    { method: 'POST' }
  );
  if (!resp.ok)
    throw new Error(`Failed to synthesize context: ${resp.statusText}`);
  return resp.json();
}

// ---------------------------------------------------------------------------
// Worker Triggers
// ---------------------------------------------------------------------------

export async function triggerAgent(
  spaceId: string,
  params: {
    parent_event_id: string;
    role?: string;
    llm_profile_id?: string;
    message: string;
  }
): Promise<DebateEvent> {
  const query = new URLSearchParams();
  query.set('parent_event_id', params.parent_event_id);
  if (params.role) query.set('role', params.role);
  if (params.llm_profile_id)
    query.set('llm_profile_id', params.llm_profile_id);
  query.set('message', params.message);

  const resp = await fetch(
    `${API_BASE}/spaces/${spaceId}/trigger/agent?${query}`,
    { method: 'POST' }
  );
  if (!resp.ok) throw new Error(`Failed to trigger agent: ${resp.statusText}`);
  return resp.json();
}

export async function triggerA2A(
  spaceId: string,
  params: {
    parent_event_id: string;
    agent_url: string;
    message: string;
  }
): Promise<DebateEvent> {
  const query = new URLSearchParams();
  query.set('parent_event_id', params.parent_event_id);
  query.set('agent_url', params.agent_url);
  query.set('message', params.message);

  const resp = await fetch(
    `${API_BASE}/spaces/${spaceId}/trigger/a2a?${query}`,
    { method: 'POST' }
  );
  if (!resp.ok) throw new Error(`Failed to trigger A2A: ${resp.statusText}`);
  return resp.json();
}

export async function triggerHITL(
  spaceId: string,
  params: {
    parent_event_id: string;
    query: string;
  }
): Promise<DebateEvent> {
  const queryStr = new URLSearchParams();
  queryStr.set('parent_event_id', params.parent_event_id);
  queryStr.set('query', params.query);

  const resp = await fetch(
    `${API_BASE}/spaces/${spaceId}/trigger/hitl?${queryStr}`,
    { method: 'POST' }
  );
  if (!resp.ok) throw new Error(`Failed to trigger HITL: ${resp.statusText}`);
  return resp.json();
}

// ---------------------------------------------------------------------------
// SSE Streaming
// ---------------------------------------------------------------------------

export function createEventStream(
  spaceId: string,
  onEvent: (event: DebateEvent) => void,
  lastEventId?: string
): EventSource {
  const query = new URLSearchParams();
  if (lastEventId) query.set('last_event_id', lastEventId);

  const source = new EventSource(
    `${API_BASE}/spaces/${spaceId}/stream?${query}`
  );

  source.addEventListener('message', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.kind === 'event' && data.payload) {
        onEvent(data.payload);
      }
    } catch (err) {
      console.error('Failed to parse SSE event:', err);
    }
  });

  source.onerror = (err) => {
    console.error('SSE error:', err);
  };

  return source;
}
