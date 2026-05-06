## Bidirectional Workflow Nodes — UI & Usage Guide

The HITL (Human-in-the-Loop) system is **fully implemented** with a working UI. Here's how it works:

---

### Architecture Overview

The bidirectional workflow extends the standard debate graph with two new node types inserted around each agent:

```
initialize → hitl_check → run_agent → hitl_agent_query ⟲ (next_agent / check_consensus)
```

- **`hitl_check`** (pre-agent): Handles pause state + consumes user injections
- **`hitl_agent_query`** (post-agent): Analyzes agent output, creates interrupts if the agent needs clarification

Defined in [`backend/workflow/hitl/graph.py`](backend/workflow/hitl/graph.py:34).

---

### Direction 1: User → Agent (Context Injection)

**UI Component:** [`InjectPanel.svelte`](frontend/src/components/hitl/InjectPanel.svelte:1)

**How to use:**
1. Start a debate — HITL is enabled by default (`hitl_enabled: True`, `hitl_mode: "full"`) in [`backend/api/routers/debate.py:767`](backend/api/routers/debate.py:767)
2. While the debate runs, the **💉 Inject Context** panel appears below the debate output (line 1130 of [`DebateView.svelte`](frontend/src/views/DebateView.svelte:1130))
3. Click to expand → type context → optionally select a target agent (strategist/critic/optimizer/moderator) or "All agents"
4. Choose priority: Low / Normal / High / Urgent
5. Press **💉 Inject** or `Ctrl+Enter`

**What happens:**
- Frontend calls `POST /api/v1/debate/{id}/inject` via [`hitl.js:injectContext()`](frontend/src/lib/hitl.js:21)
- Backend queues the injection in [`api.py`](backend/workflow/hitl/api.py:96) (`_interaction_log`)
- Before the next agent runs, [`hitl_check_node()`](backend/workflow/hitl/nodes.py:42) consumes all pending injects and merges them into the agent's context
- SSE event `hitl_inject` is published → frontend refreshes interaction timeline

---

### Direction 2: Agent → User (Clarification Query)

**UI Component:** [`AgentQueryModal.svelte`](frontend/src/components/hitl/AgentQueryModal.svelte:1)

**How it works (automatic):**
1. After each agent produces output, [`hitl_agent_query_node()`](backend/workflow/hitl/nodes.py:131) runs
2. [`analyze_for_query()`](backend/workflow/hitl/agent_query.py:1) uses a hybrid approach to detect if the agent needs clarification:
   - **Marker detection**: Looks for `[NEEDS_CLARIFICATION]`, `[QUESTION]` tags in agent output
   - **Uncertainty detection**: Regex patterns for hedging language ("I'm not sure", "unclear", "insufficient information") in both English and German
   - **Loop detection**: If the agent repeats similar output across rounds (stalemate), it triggers a query
3. If a query is warranted (confidence below `auto_query_threshold: 0.4`), an **interrupt** is created
4. SSE event `hitl_query` is published → the **Agent Query Modal** pops up automatically
5. The modal shows: agent icon, role, round number, the agent's question, context snippet, elapsed time
6. User types a response and clicks **📤 Send Response** (or `Ctrl+Enter`)
7. Frontend calls `POST /api/v1/debate/{id}/respond` via [`hitl.js:respondToQuery()`](frontend/src/lib/hitl.js:35)
8. The response is injected back into the agent's context and the workflow continues

**Safety limits:**
- Max 3 interrupts per round ([`max_interrupts_per_round`](backend/workflow/hitl/nodes.py:151))
- 5-minute timeout per interrupt ([`interrupt_timeout_seconds: 300`](backend/workflow/hitl/api.py:76))
- User can click **Skip** to let the agent timeout and continue without answering

---

### Pause/Resume

**UI Component:** [`PauseControls.svelte`](frontend/src/components/hitl/PauseControls.svelte:1)

- **⏸️ Pause** button appears in the debate header when HITL is enabled (line 965 of [`DebateView.svelte`](frontend/src/views/DebateView.svelte:965))
- Clicking pauses the debate — the [`hitl_check_node()`](backend/workflow/hitl/nodes.py:60) polls every 2 seconds until resumed (max 10 minutes)
- SSE events `hitl_paused` / `hitl_resumed` update the UI

---

### Interaction Timeline

**UI Component:** [`InteractionTimeline.svelte`](frontend/src/components/hitl/InteractionTimeline.svelte:1)

- Shows all bidirectional interactions (injects, queries, responses) in chronological order
- Appears below the debate output when interactions exist (line 1316 of [`DebateView.svelte`](frontend/src/views/DebateView.svelte:1316))
- Polled every 5 seconds while debate runs ([`DebateView.svelte:478`](frontend/src/views/DebateView.svelte:478))

---

### HITL Modes

Defined in [`contracts.py:45`](backend/workflow/hitl/contracts.py:45):

| Mode | User → Agent | Agent → User |
|---|---|---|
| `full` | ✅ Inject | ✅ Query |
| `inject_only` | ✅ Inject | ❌ |
| `query_only` | ❌ | ✅ Query |
| `off` | ❌ | ❌ |

Default is `full`. The mode is set in the initial state at [`debate.py:768`](backend/api/routers/debate.py:768).

---

### Workflow Visualization Integration

The workflow graph nodes for HITL interactions are defined in [`graphReducer.js`](frontend/src/lib/workflow/graphReducer.js):
- **`USER_CLARIFICATION_REQUESTED`** → creates a `user_action` node (❓ clarify) with dashed orange edges to/from the requesting agent
- **`USER_CLARIFICATION_RECEIVED`** → marks the node as resolved (green border), activates the response edge
- **`USER_OUT_OF_BAND_INPUT`** → creates a side-input node (💬 provide_context) with blue dashed edges

These appear in the [`WorkflowCanvas`](frontend/src/components/workflow/WorkflowCanvas.svelte) as part of the cumulative graph.
