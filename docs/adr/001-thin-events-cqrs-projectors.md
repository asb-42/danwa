# ADR-001: Thin Events with CQRS Projectors for Interactive Debate Mode

**Status:** Accepted  
**Date:** 2026-07-09  
**Deciders:** Danwa Core Team  
**Relates to:** Interactive Debate Mode (Event Sourcing)

---

## Context

The Interactive Debate Mode uses Event Sourcing where every action in a debate tree is recorded as an immutable event. Initially, the implementation introduced specific event types like `agent_speech`, `user_message`, `tool_call_requested`, etc. While functional, this approach risks "Fat Events" — where each new agent role (e.g., "Devil's Advocate", "Code Auditor") demands a new event type, causing:

1. **Event type explosion** — every new role/tool/interaction requires schema changes
2. **Tight coupling** — UI and consumers must know about every event variant
3. **Migration burden** — database schema changes for new business concepts
4. **Loss of generality** — events describe *how* something happened, not *what* happened

### Current State

The existing `debate_events` table uses these event types:

```
user_message, agent_speech, tool_call_requested, tool_result,
a2a_request, a2a_response, hitl_input, synthesis
```

This is already close to thin events, but the naming and metadata structure can be improved to fully embrace the DDD/CQRS pattern.

---

## Decision

We adopt **Thin, Generic Events** with a **Projector System** (CQRS pattern) for the Interactive Debate Mode.

### 1. Event Taxonomy (Thin Events)

Events are categorized into 4 domains. All events write to the same `debate_events` table.

#### A. Space Lifecycle

| Event Type | Description | Key Payload Fields |
|------------|-------------|-------------------|
| `SpaceCreated` | User starts a new interactive session | `title`, `description`, `initial_context` |
| `SpaceArchived` | Session is ended/paused | `reason`, `summary` |

#### B. Actor Interactions (Core Debate — 90% of events)

| Event Type | Description | Key Payload Fields |
|------------|-------------|-------------------|
| `UserActed` | Human intervenes (HITL) | `action_type` (question/correction/instruction), `content` |
| `AgentActed` | LLM responds | `content`, `structured_output` (claims, critiques, evidence) |
| `A2AActed` | External agent (via A2A protocol) provides input | `content`, `agent_card` |

#### C. System & Infrastructure

| Event Type | Description | Key Payload Fields |
|------------|-------------|-------------------|
| `ToolRequested` | Agent requests a tool (web search, code interpreter) | `tool_name`, `tool_params` |
| `ToolExecuted` | System delivers tool result | `tool_name`, `result`, `duration_ms` |
| `ContextSynthesized` | Context router built prompt for next agent | `prompt`, `token_costs`, `source_events` |
| `BranchForked` | User pressed [+] to create a parallel branch | `fork_point_event_id`, `branch_label` |

#### D. Milestones

| Event Type | Description | Key Payload Fields |
|------------|-------------|-------------------|
| `MilestoneReached` | Semantic completion point | `milestone_type` (consensus/report_generated/task_created/deadlock) |

### 2. Payload Structure

Every event uses the same thin envelope:

```python
class DebateEvent(BaseModel):
    event_id: str                          # UUID
    space_id: str                          # Parent space
    parent_id: str | None                  # Tree structure
    event_type: str                        # One of the thin event types above
    actor_type: Literal['user', 'agent', 'system', 'a2a']
    actor_id: str                          # e.g., "claude-sonnet", "user-123"
    role: str | None                       # e.g., "critic", "strategist"
    content: str                           # Free-text for UI display
    metadata: dict                         # Structured payload (see below)
    created_at: datetime
```

The `metadata` field carries the rich, structured payload:

```json
{
  "event_type": "AgentActed",
  "actor_id": "qwen-critic",
  "role": "critic",
  "content": "Die Strategie von Sonnet ist zu teuer...",
  "metadata": {
    "tokens_used": 450,
    "argumentation_pattern": "hegelian_dialectic",
    "structured_output": {
      "claims": ["Kosten sind nicht gedeckelt"],
      "critiques": ["Keine Kostendeckelung vorgesehen"],
      "evidence": ["Quelle X aus RAG-Doc 2"],
      "sentiment": "negative"
    }
  }
}
```

**Why this works:** A new "Code Auditor" role doesn't require a new event type. It fires `AgentActed` with `role: "code_auditor"` in metadata. UI and projectors handle it immediately.

### 3. CQRS Projectors

The UI and LLMs **never read the full event log**. Instead, 4 projectors build read models:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Event Stream (Redis)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Tree Projector│   │Context Project│   │Budget Projector│
│ (SvelteFlow)  │   │ (ChromaDB)    │   │ (Token Stats)  │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                    │                    │
        ▼                    ▼                    ▼
   nodes/edges          debate_state         token_budgets
   (Redis/SQLite)       (ChromaDB)           (SQLite)
```

#### Projector 1: Tree Graph (for SvelteFlow UI)

**Purpose:** Build the visual graph for the frontend.

**Storage:** Dedicated `debate_tree_nodes` and `debate_tree_edges` tables (or Redis JSON).

**Logic:**
- Listens to: `*Acted`, `BranchForked`
- Ignores large text content
- Stores: `id`, `parent_id`, `actor_name`, `role`, `label` (e.g., "Qwen kritisiert Kosten"), `timestamp`, `event_type`

**Benefit:** Frontend loads a lightweight tree on startup, not the 200-page log.

```sql
CREATE TABLE debate_tree_nodes (
    node_id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    role TEXT,
    label TEXT,           -- Short summary for UI
    created_at TEXT NOT NULL
);

CREATE TABLE debate_tree_edges (
    edge_id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL
);
```

#### Projector 2: Context & RAG (for Synthesizer)

**Purpose:** Maintain the "Shared Debate Space" as structured objects and vectors.

**Storage:** ChromaDB (vectors) + `debate_state` table (structured facts).

**Logic:**
- Listens to: `AgentActed`, `UserActed`, `ToolExecuted`
- Extracts `structured_output` (claims, critiques, evidence) from metadata
- Embeds content text into ChromaDB
- Writes extracted facts to `debate_state`

**Benefit:** When user clicks [+] → "Ask Deepseek", the context router queries this projector: "What are the open questions and last 3 claims?" It builds the prompt from state, not from the log.

```sql
CREATE TABLE debate_state (
    id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    event_id TEXT NOT NULL,           -- Source event
    fact_type TEXT NOT NULL,          -- 'claim' | 'critique' | 'evidence' | 'question'
    fact_content TEXT NOT NULL,
    actor_id TEXT,
    created_at TEXT NOT NULL
);
```

#### Projector 3: Audit & Budget

**Purpose:** Token tracking and cost control.

**Storage:** `token_budgets` aggregate table.

**Logic:**
- Listens to: All events with `metadata.tokens_used`
- Sums tokens per branch, per actor, per space
- Groups by branch ID for comparative analysis

**Benefit:** UI can display live: "Branch A used 15k tokens, Branch B only 2k".

```sql
CREATE TABLE token_budgets (
    id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    branch_id TEXT,                    -- NULL = main thread
    actor_id TEXT,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    total_cost_usd REAL,               -- Calculated from profile
    updated_at TEXT NOT NULL
);
```

#### Projector 4: Synthesis (for Final Report)

**Purpose:** Prepare the final PDF/LaTeX/Markdown output.

**Storage:** In-memory / temporary files.

**Logic:**
- Listens to: `MilestoneReached` (type: `consensus` or `report_generated`)
- Traverses the main thread of the tree
- Collects free-text content from events
- Renders into clean Markdown document

**Benefit:** On-demand report generation without re-processing the entire event log.

---

## Consequences

### Positive

1. **Infinite extensibility** — New agent roles, tools, or interaction types don't require schema changes
2. **Clean separation** — Write model (events) is independent from read models (projectors)
3. **Performance** — Frontend queries lightweight read models, not full event logs
4. **Auditability** — Every fact is traceable to its source event
5. **Debugging** — `ContextSynthesized` events capture exact prompts and costs
6. **Flexibility** — Projectors can be added/removed without affecting the write path

### Negative

1. **Complexity** — More moving parts (event bus, projectors, read models)
2. **Eventual consistency** — Read models may lag behind writes (acceptable for UI)
3. **Storage duplication** — Same data in event log + read models
4. **Learning curve** — Team must understand CQRS concepts

### Mitigations

- **Complexity:** Document projector patterns clearly; provide starter templates
- **Consistency:** Use SSE to push updates immediately after write; projectors run synchronously in v1
- **Storage:** SQLite is cheap; ChromaDB is already required for RAG
- **Learning curve:** ADR + inline code comments

---

## Migration Path

### Phase 1: Event Renaming (Current)

Rename existing event types to match the thin taxonomy:

| Old | New | Notes |
|-----|-----|-------|
| `user_message` | `UserActed` | Add `action_type` to metadata |
| `agent_speech` | `AgentActed` | Add `structured_output` to metadata |
| `a2a_request` | `A2AActed` | Merge request/response into single event |
| `a2a_response` | *(removed)* | Use `A2AActed` with `direction` field |
| `hitl_input` | `UserActed` | With `action_type: "hitl_response"` |
| `tool_call_requested` | `ToolRequested` | Rename only |
| `tool_result` | `ToolExecuted` | Rename only |
| `synthesis` | `ContextSynthesized` | Add `prompt` and `token_costs` |
| *(new)* | `SpaceCreated` | Lifecycle event |
| *(new)* | `SpaceArchived` | Lifecycle event |
| *(new)* | `BranchForked` | Fork tracking |
| *(new)* | `MilestoneReached` | Semantic completion |

### Phase 2: Add Projectors

Implement the 4 projectors as background workers:

1. Tree Graph Projector (immediate — required for SvelteFlow)
2. Context & RAG Projector (immediate — required for ContextSynthesizer)
3. Audit & Budget Projector (shortly after)
4. Synthesis Projector (when export features are needed)

### Phase 3: Query API

Add read-only endpoints that query projector read models:

```
GET /api/v1/interactive/spaces/{id}/tree-graph    → Tree Projector
GET /api/v1/interactive/spaces/{id}/debate-state  → Context Projector
GET /api/v1/interactive/spaces/{id}/budget        → Budget Projector
POST /api/v1/interactive/spaces/{id}/synthesis    → Synthesis Projector
```

---

## Alternatives Considered

### 1. Fat Events (Rejected)

Each role/action gets its own event type: `StrategistResponded`, `CriticAnalyzed`, `DevilAdvocateChallenged`.

**Rejected because:** Schema explosion, tight coupling, migration burden.

### 2. Single JSONB Column (Rejected)

Store everything in a single JSON column without event types.

**Rejected because:** Loses queryability, no type safety, hard to build projectors.

### 3. Separate Tables per Event Type (Rejected)

Each event type gets its own table (e.g., `agent_speech_events`, `tool_events`).

**Rejected because:** Cross-table queries are expensive, hard to maintain chronological order.

---

## References

- [Martin Fowler — Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- [CQRS Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)
- [Domain-Driven Design — Eric Evans](https://www.domainlanguage.com/ddd/)
- [EventStoreDB — Thin Events](https://developers.eventstore.com/)

---

*This ADR supersedes the initial event type design in `backend/models/debate_event.py`.*
