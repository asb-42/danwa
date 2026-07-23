# Interactive Mode — Backend Investigation & Action System Design

> Date: 2026-07-19 (Updated)
> Original: 2026-07-14
> Status: Decisions made — ready for implementation
> Related: Frontend API client at `frontend/src/lib/interactive/api.ts`

---

## 1. Problem Statement

The interactive debate mode provides a non-linear shared debate space resembling an unstructured conversation (talk show, working group discussion) rather than a structured parliamentary debate. The frontend UI is built and functional — graph rendering, SSE streaming, forking, side panel — but the backend has **zero endpoints** implemented. All API calls to `/api/v1/interactive/...` fail silently.

The event sourcing model consists of three layers:
- **Event store** — append-only event log with tree relationships (`parent_id`)
- **Context router** — builds prompt context from thread history for agent triggers
- **Pub/sub layer** — broadcasts events to all connected clients via SSE

---

## 2. Frontend API Contract

Base URL: `/api/v1/interactive`

### 2.1 Data Types

```
DebateSpace:
  space_id: string
  title: string
  description: string | null
  project_id: string | null
  tenant_id: string | null
  created_by: string | null
  status: string
  event_count: int
  fork_count: int
  created_at: datetime
  updated_at: datetime

DebateEvent:
  event_id: string
  space_id: string
  parent_id: string | null
  event_type: EventType          # enum
  actor_type: ActorType          # enum
  actor_id: string
  role: string | null
  content: string | object
  metadata_json: object
  tokens_input: int | null
  tokens_output: int | null
  created_at: datetime

EventType: UserActed | AgentActed | A2AActed | A2AResponse |
           ContextSynthesized | ToolRequested | ToolExecuted | SpaceCreated

ActorType: user | agent | system | a2a

ContextSynthesis:
  target_event_id: string
  prompt_context: string
  metadata:
    thread_depth: int
    side_branches_included: int
    token_budget_used: int
```

### 2.2 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spaces` | Create a new debate space |
| `GET` | `/spaces` | List spaces (filtered by tenant/project) |
| `GET` | `/spaces/{id}` | Get a single space |
| `POST` | `/spaces/{id}/events` | Append an event (user/system) |
| `GET` | `/spaces/{id}/events` | List events (filterable by parent, type) |
| `GET` | `/spaces/{id}/thread/{eventId}` | Get thread from root to event |
| `GET` | `/spaces/{id}/tree` | Get full event tree |
| `GET` | `/spaces/{id}/tokens` | Get cumulative token usage |
| `POST` | `/spaces/{id}/context/{eventId}` | Synthesize context for an event |
| `POST` | `/spaces/{id}/trigger/agent` | Trigger an LLM agent response |
| `POST` | `/spaces/{id}/trigger/a2a` | Trigger an external A2A agent |
| `POST` | `/spaces/{id}/trigger/hitl` | Request human-in-the-loop input |
| `GET` | `/spaces/{id}/stream` | SSE event stream (with `last_event_id` resumption) |

### 2.3 SSE Stream Contract

```
EventSource: GET /api/v1/interactive/spaces/{id}/stream?last_event_id={id}

Each SSE message:
  event: message
  data: {"kind": "event", "payload": <DebateEvent>}

Lifecycle: subscribe → stream indefinitely → no terminal event
Reconnection: 3s backoff, passes last_event_id for catch-up
```

---

## 3. Existing Backend Infrastructure (Reusable)

| Component | Location | Reuse |
|-----------|----------|-------|
| Event bus | `backend/api/events.py` | **As-is** — `subscribe(space_id)` / `publish(space_id, ...)` |
| SSE pattern | `backend/api/routers/debate_stream.py` | **Adapt** — same `EventSourceResponse` pattern, new key |
| LLM Service | `backend/services/llm_service.py` | **As-is** — `generate(profile_id, prompt)` with token counting |
| Profile Service | `backend/services/profile_service.py` | **As-is** — resolves `llm_profile_id` → model config |
| A2A Adapter | `backend/a2a/adapter.py` | **As-is** — sends messages to external agents |
| Tone Prompt Injector | `backend/services/tone_prompt_injector.py` | **As-is** — role-specific prompt injection |
| JSON file store pattern | `backend/persistence/debate_store.py` | **Copy** — for SpaceStore CRUD |
| SQLite store pattern | `backend/persistence/tenant_store.py` | **Copy** — for EventStore with tree queries |
| Interjection Service | `backend/workflow/interjection.py` | **Adapt** — HITL queue/consume pattern |
| Assistant Service | `backend/services/assistant_service.py` | **Reference** — context building patterns |

---

## 4. Components to Build

### 4.1 Router: `backend/api/routers/interactive.py`

13 endpoints following existing router patterns. Register in app factory.

### 4.2 Persistence: `backend/persistence/interactive_store.py`

**DebateSpaceStore** (JSON file-based, like `DebateStore`):
- `create_space(title, description, project_id, tenant_id, created_by) -> DebateSpace`
- `get_space(space_id) -> DebateSpace | None`
- `list_spaces(tenant_id?, project_id?, limit, offset) -> DebateSpace[]`
- `update_event_count(space_id, delta)`
- `update_fork_count(space_id, delta)`

**EventStore** (SQLite-based, needs recursive CTE for tree queries):
- `append_event(space_id, event) -> DebateEvent`
- `list_events(space_id, parent_id?, event_type?, limit) -> DebateEvent[]`
- `get_thread(space_id, event_id, max_depth) -> DebateEvent[]` — recursive CTE walking `parent_id`
- `get_full_tree(space_id) -> DebateEvent[]`
- `get_token_usage(space_id) -> {total_input, total_output}`
- `get_last_event_id(space_id) -> str | None`

### 4.3 Models: `backend/models/interactive.py`

Pydantic request/response schemas for all 13 endpoints.

### 4.4 Services: `backend/services/interactive_service.py`

**ContextSynthesizer** — builds prompt context from the event tree:
- Traverses parent chain from target event to root
- Optionally includes side branches (sibling subtrees)
- Respects token budget (truncate or summarize older events)
- Returns `ContextSynthesis` with `prompt_context`, `thread_depth`, `side_branches_included`, `token_budget_used`

**AgentTriggerService** — orchestrates agent responses:
1. Synthesize context for the parent event
2. Resolve `llm_profile_id` via ProfileService
3. Call `LLMService.generate()` with synthesized context
4. Append response as `AgentActed` event
5. Publish to event bus for SSE streaming

**A2ATriggerService** — wraps A2AAdapter for external agent calls.

**HITLTriggerService** — creates human-in-the-loop request, could reuse InterjectionService.

### 4.5 DB Migration

Two new tables:
- `debate_spaces` — space metadata
- `debate_events` — append-only event log with `parent_id` foreign key

### 4.6 SSE Streaming Endpoint

Adapt `debate_stream.py` pattern:
```python
async def _interactive_events(space_id, last_event_id, store):
    # 1. Send catch-up events after last_event_id
    # 2. Subscribe to event bus for space_id
    # 3. Yield {"kind": "event", "payload": event}
    # 4. Keepalive every 300s
    # 5. Unsubscribe in finally
```

Key difference from debate streaming: **no terminal events** — spaces accumulate indefinitely.

### 4.7 Effort Estimate

| Component | Effort |
|-----------|--------|
| Router (13 endpoints) | 0.5 day |
| SpaceStore (JSON) | 0.25 day |
| EventStore (SQLite + recursive CTE) | 0.5 day |
| Pydantic models | 0.25 day |
| ContextSynthesizer | 0.5 day |
| AgentTriggerService | 0.5 day |
| A2A + HITL triggers | 0.25 day |
| SSE streaming | 0.25 day |
| DB migration | 0.1 day |
| **Total** | **~3 days** |

---

## 5. Token Cost Analysis

### 5.1 Per-Event Token Breakdown

```
System prompt:        ~1,000 tokens (fixed, per agent call)
Synthesized context:  ~1,000–4,000 tokens (grows with tree depth)
LLM output:           ~500–1,500 tokens
─────────────────────────────────────────
Total per event:      ~2,500–6,500 tokens
```

### 5.2 Cost Scenarios

Using GPT-4o pricing ($2.50/1M input, $10/1M output):

| Scenario | Agents | Events | Tokens | Cost |
|----------|--------|--------|--------|------|
| Quick interaction | 1 | 5 | ~15k | ~$0.10 |
| Working session | 2 | 20 | ~80k | ~$0.70 |
| Extended debate | 4 | 50 | ~250k | ~$2.50 |
| Marathon session | 4 | 200 | ~1M | ~$10.00 |

### 5.3 Comparison with Standard Debate

| Metric | Standard Debate | Interactive Mode |
|--------|----------------|------------------|
| Event structure | Linear rounds | Branching tree |
| Events per session | `max_rounds × num_agents` (bounded) | Unbounded (user-driven) |
| Context growth | `current_draft` accumulator (capped at ~12.5k tokens) | Thread path (grows linearly with depth) |
| Cost predictability | High (fixed formula) | Low (depends on user activity) |
| Token control | `max_rounds` + `MAX_RUNNING_DRAFT_LEN` | **None implemented** |

### 5.4 Existing Token Budgeting Mechanisms

**What exists:**
- `max_tokens` per LLM profile (default 4096) — max completion per call
- `context_window` per LLM profile — model's total context limit
- `MAX_RUNNING_DRAFT_LEN` (50,000 chars ≈ 12,500 tokens) — draft truncation
- Per-tenant debate rate limits (10/hour)
- LLM call timeout (600s)

**What does NOT exist:**
- No per-space token budget or limit
- No token-based rate limiting
- No dynamic context window management
- No cost alerting or hard stop
- `token_budget_used` in the frontend contract — **not implemented in backend**

### 5.5 Recommended Token Controls

1. **Per-space token budget** — configurable, with default cap (e.g., $5/session)
2. **Context window-aware truncation** — use `context_window` from LLM profiles to truncate synthesized context
3. **SSE cost milestones** — emit events at 25%, 50%, 75%, 100% of budget
4. **Cost estimation endpoint** — `GET /spaces/{id}/cost-estimate` before triggering agents

---

## 6. Action System Design

### 6.1 Problem

The [+] button currently always opens a text input for forking. The intended design is that [+] triggers **context-aware actions** — different operations depending on the selected node and the user's intent.

### 6.2 Action Model

An action is a typed operation that produces one or more events in the tree. Actions are defined as a registry of templates, each with:
- **id** — unique identifier
- **label** — display text (i18n key)
- **icon** — emoji or icon identifier
- **category** — grouping for the action menu
- **applicable_when** — condition for when this action is available
- **template** — the event type, actor type, role, and prompt template
- **params** — user-configurable parameters (shown in the action form)

### 6.3 Built-in Actions

#### Category: Response

| Action | ID | Description | Event Type | Actor |
|--------|----|-------------|------------|-------|
| Reply as Agent | `agent_reply` | Generate an LLM response as a specific role | `AgentActed` | `agent` |
| Reply as User | `user_reply` | Add a user message (manual text input) | `UserActed` | `user` |
| Reply to All | `broadcast_reply` | Trigger all agents in the space to respond | Multiple `AgentActed` | `agent` |

#### Category: Analysis

| Action | ID | Description | Event Type | Actor |
|--------|----|-------------|------------|-------|
| Fact-Check | `fact_check` | Verify claims in the selected event | `AgentActed` | `agent` (role: fact-checker) |
| Summarize Thread | `summarize_thread` | Generate a summary of the thread leading to this event | `AgentActed` | `agent` (role: summarizer) |
| Find Contradictions | `find_contradictions` | Identify conflicting statements in the tree | `AgentActed` | `agent` (role: analyst) |
| Extract Action Items | `extract_actions` | Pull out concrete action items from the discussion | `AgentActed` | `agent` (role: analyst) |

#### Category: External

| Action | ID | Description | Event Type | Actor |
|--------|----|-------------|------------|-------|
| A2A Request | `a2a_request` | Send to an external agent via A2A protocol | `A2AActed` | `a2a` |
| Human Input | `hitl_request` | Request input from a human participant | — | — |
| Web Search | `web_search` | Search the web for information related to this event | `ToolRequested` | `system` |
| RAG Lookup | `rag_lookup` | Search the DMS for relevant documents | `ToolRequested` | `system` |

#### Category: Output

| Action | ID | Description | Event Type | Actor |
|--------|----|-------------|------------|-------|
| Synthesize Transcript | `synthesize_transcript` | Generate a full transcript of the space | `ContextSynthesized` | `system` |
| Export MD | `export_markdown` | Export the tree as a structured Markdown document | `ToolExecuted` | `system` |
| Export PDF | `export_pdf` | Generate a PDF deliverable | `ToolExecuted` | `system` |

### 6.4 Action Registry (Data Structure)

```typescript
interface ActionDef {
  id: string;
  label: string;           // i18n key
  icon: string;
  category: 'response' | 'analysis' | 'external' | 'output';
  
  // When is this action available?
  applicable_when: {
    node_type?: string[];      // event_types this applies to
    actor_type?: string[];     // actor_types this applies to
    has_parent?: boolean;      // only for non-root nodes
    has_children?: boolean;    // only for leaf nodes
    max_depth?: number;        // only within N levels of root
  };
  
  // What does this action produce?
  template: {
    event_type: EventType;
    actor_type: ActorType;
    role?: string;              // agent role for LLM triggers
    llm_profile_id?: string;    // specific profile, or null for default
    prompt_template: string;    // with {{variable}} placeholders
    tool?: string;              // tool to execute (for ToolRequested)
  };
  
  // What parameters does the user configure?
  params: ActionParam[];
}

interface ActionParam {
  key: string;
  label: string;
  type: 'text' | 'textarea' | 'select' | 'toggle';
  default?: any;
  options?: { value: string; label: string }[];
  required?: boolean;
}
```

### 6.5 Context-Aware Prompt Templates

Each action's `prompt_template` uses the event tree to build context. The template has access to:

```
{{thread}}         — the thread from root to the selected event (linear path)
{{event.content}}  — the content of the selected event
{{event.actor_id}} — who wrote the selected event
{{event.role}}     — the role of the actor
{{siblings}}       — sibling events (same parent, other branches)
{{space.title}}    — the space title
{{space.description}} — the space description
```

Example fact-check template:
```
You are a fact-checking agent. Verify the claims in the following statement.

Thread context:
{{thread}}

Statement to fact-check:
{{event.content}}

Task: Identify factual claims, verify them against your knowledge,
and provide a confidence rating for each claim.
```

### 6.6 Action Menu UX

When the user clicks [+] on a node:

1. **Action menu opens** (ForkModal is sufficient — no floating panel replacement needed yet; this is priority 2+ UX polish)
2. **Actions are grouped by category** with icons
3. **Applicable actions are highlighted**; inapplicable ones are grayed out with a tooltip explaining why
4. **User selects an action** → action-specific form appears (params from `ActionParam[]`)
5. **User submits** → `triggerAgent` / `triggerA2A` / `appendEvent` is called with the appropriate parameters

The action menu renders within the existing ForkModal container. Floating panel replacement is deferred to priority 2 or later — not structurally required.

### 6.7 Action Customization

Actions are defined in a JSON/YAML configuration file that can be extended:

```yaml
# config/interactive-actions.yaml
actions:
  - id: agent_reply
    label: actions.agentReply
    icon: 🤖
    category: response
    applicable_when:
      has_parent: true
    template:
      event_type: AgentActed
      actor_type: agent
      role: "{{param:role}}"
      prompt_template: |
        You are {{event.role}}. Continue the discussion.
        
        Thread:
        {{thread}}
        
        Your response:
    params:
      - key: role
        label: Agent Role
        type: select
        options:
          - value: strategist
            label: Strategist
          - value: critic
            label: Critic
          - value: creative
            label: Creative Thinker
        required: true

  - id: fact_check
    label: actions.factCheck
    icon: 🔍
    category: analysis
    applicable_when:
      actor_type: [user, agent]
    template:
      event_type: AgentActed
      actor_type: agent
      role: fact-checker
      prompt_template: |
        Verify the claims in this statement.
        Statement: {{event.content}}
        Thread context: {{thread}}
    params: []
```

This allows:
- **Adding new actions** without code changes (just add to config)
- **Customizing prompts** per deployment or tenant
- **Role-based action availability** (admin-only actions, etc.)

### 6.8 Frontend Changes Required

1. **Replace `ForkModal` content with `ActionMenu`** — new component that loads action definitions and renders the dynamic form (within existing modal container)
2. **Action definitions API** — `GET /api/v1/interactive/actions` returns the available actions (could be config-driven or database-driven)
3. **Dynamic form rendering** — render `ActionParam[]` as a form with appropriate input types
4. **Action result display** — show the resulting event in the graph after submission

### 6.9 Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| **Phase 1: Core actions** | `agent_reply`, `user_reply`, `hitl_request` — basic fork functionality with role selection | 0.5 day |
| **Phase 2: Analysis actions** | `fact_check`, `summarize_thread`, `find_contradictions` — analysis templates | 0.5 day |
| **Phase 3: External actions** | `a2a_request`, `web_search`, `rag_lookup` — external integrations | 0.5 day |
| **Phase 4: Output actions** | `synthesize_transcript`, `export_markdown`, `export_pdf` — deliverable generation | 1 day |
| **Phase 5: Config system** | YAML-based action registry, hot-reload, tenant-specific overrides | 0.5 day |

---

## 7. Decisions (2026-07-19)

### 7.1 ForkModal — Keep As-Is
**Decision:** Do not replace ForkModal with floating panel. It works. Floating panel is UX polish, not structural.
**Rationale:** ForkModal functions correctly for text input. ActionMenu replaces the *content* of ForkModal, not the container. Floating panel is priority 2+ — not blocking.

### 7.2 Action Scope — Global Default
**Decision:** Actions are global by default, with optional per-space overrides added later.
**Rationale:** Per-space actions from day one is over-engineering. Global registry covers all current use cases. Per-space override is trivial to add when needed.

### 7.3 Agent Auto-Response — No
**Decision:** When user triggers `agent_reply`, they explicitly select which agent responds. No auto-response.
**Rationale:** Explicit agent selection is the core of interactive mode. Auto-response collapses back into the old linear debate mode.

### 7.4 HITL Delivery — In-App Nodes
**Decision:** Human-in-the-loop requests are delivered as nodes in the graph. No email/webhook.
**Rationale:** Consistent with the rest of the system. Email/webhook is phase 47/11 — not now.

### 7.5 Context Caching — None (For Now)
**Decision:** `synthesizeContext` always recomputes. No caching.
**Rationale:** Cache invalidation complexity on a living tree is not worth it at current scale.

### 7.6 Branching Token Explosion — Guard Required
**Decision:** `side_branches_included` in ContextSynthesis defaults to **0**. Only activated explicitly.
**Rationale:** Branching through recursive earlier contributions is conceptually correct but token explosion is real. Default to 0 prevents runaway costs. User enables explicitly when needed.

### 7.7 Event Ordering — FIFO
**Decision:** Simultaneous responses from multiple agents are ordered FIFO (deterministic).
**Rationale:** Concurrent same-parent events are a problem that shows up only with real usage. FIFO is simple, deterministic, and defers complexity.

### 7.8 Implementation Priority
**Decision:** Priority 1 (3 days backend) directly. Priority 2 (action system) after. Everything else when core works.
**Rationale:** Get the working prototype first. Action system is the critical UX improvement but depends on backend.

---

## 8. Recommendations

### Priority 1: Minimal Backend (3 days) — START HERE
Build the core event sourcing backend: Space CRUD, Event append + tree queries, SSE streaming, and `trigger/agent`. This unblocks the branching UX and gives a working prototype.

### Priority 2: Action System (2 days)
Build the action registry and replace ForkModal content with ActionMenu. Start with `agent_reply` and `user_reply`, then add analysis actions. This is the critical UX improvement.

### Priority 3: Token Controls (1 day)
Implement `token_budget_used` tracking (already in the frontend contract), per-space budgets, and SSE cost milestones. Essential before any production use.

### Priority 4: Advanced Actions (2 days)
A2A integration, output synthesis, web search, RAG lookup. These add depth but aren't blocking the core workflow.

**Total estimated effort: ~8 days for a fully functional interactive mode with action system and cost controls.**

---

## 9. Open Questions

1. ~~**Action scope**~~ — **Resolved:** Global default, per-space overrides later.
2. ~~**Agent auto-response**~~ — **Resolved:** Explicit selection only, no auto-response.
3. ~~**Context freshness**~~ — **Resolved:** Always recompute, no caching.
4. ~~**Event ordering**~~ — **Resolved:** FIFO, deterministic.
5. ~~**HITL delivery**~~ — **Resolved:** In-app nodes only.
6. **DB migration timing** — Should the `debate_events` table be SQLite from day one, or start with JSON file-based EventStore and migrate to SQLite when needed?
7. **Agent role resolution** — When user selects "Reply as Agent" without specifying a role, which agent is chosen? First available? Random? Prompt the user?
8. **Space creation flow** — Does the user create a space first, or does the first event automatically create one?
