# Known Issues

Last updated: 2026-05-19

---

## 1. Legacy Workflow ignores UI language setting

**Status:** Open — investigation incomplete, fix partial

**Symptom:** When the UI language is set to English (or any non-German language), agents in a Legacy Workflow debate still respond in German. The system prompt resolution falls back to German templates despite `language="en"` being passed in the debate request.

**Root cause (partial):** The `_resolve_system_prompt()` function in `backend/workflow/nodes.py` calls the PromptService with the correct `language` parameter, but the DB-seeded prompt templates have incorrect cache keys and role names:
- Files like `strategist-en.md` were stored with `role="strategist-en"` instead of `role="strategist"` + `language="en"`
- Cache keys were hardcoded to `/de` regardless of actual file language

**Attempted fix:** `backend/services/profile_service.py` — `_seed_prompts_to_db()` now extracts language suffix from filename and uses correct cache keys. However, the issue persists after restart, suggesting the DB already contains stale entries that are not being re-seeded, or the PromptService resolves templates from a different code path (persona system_prompt fallback) that bypasses the language-aware lookup.

**Workaround:** Manually delete `data/blueprints.db` and let the backend re-seed on startup. Or use Canvas/Workflow debates which may handle language differently.

**Related files:**
- `backend/workflow/nodes.py:637-701` — `_resolve_system_prompt()`
- `backend/services/profile_service.py:309-350` — `_seed_prompts_to_db()`
- `backend/services/prompt_service.py:56-156` — `get_prompt()`
- `backend/services/module_profile_sync.py:201-217` — `get_prompt_templates_from_modules()`

---

## 2. OOB Inject Context stays "pending" forever

**Status:** Open — root cause identified, fix not yet implemented

**Symptom:** When clicking "Inject Context" → "Insert into workflow" during a running debate, the UI shows "1 pending" and the inject is never consumed. The badge persists until the debate ends.

**Root cause:** The OOB (Out-of-Band) input system uses an in-memory module-level dictionary `_oob_queues` in `backend/services/debate_workflow.py`. The API endpoint (`POST /api/v1/debate/{id}/oob`) enqueues the input in the worker process that handles the HTTP request. The debate workflow runs as a background task, potentially in the same process. Debug logging was added to trace consumption but no consumption logs appear, suggesting either:
- The `debate_id` in the workflow state doesn't match the one used to enqueue
- The OOB queue is empty when `get_oob_for_debate()` is called (different process/memory space)
- The relevance filter `_is_oob_relevant()` rejects all OOB entries due to target mismatch

**Investigation needed:** Add INFO-level logging (not just DEBUG) to confirm whether `get_oob_for_debate()` returns any entries at all, and whether the `debate_id` matches between enqueue and consume.

**Related files:**
- `backend/services/debate_workflow.py:28,56-77` — `_oob_queues` dict and helpers
- `backend/api/routers/debate.py:921-978` — `submit_oob_input()` endpoint
- `backend/workflow/nodes.py:248-284` — OOB consumption in `run_agent_node()`
- `backend/workflow/nodes.py:1057-1083` — `_is_oob_relevant()`
- `frontend/src/components/workflow/OOBInputPanel.svelte` — UI component

---

## 3. Agent "questions" are fragmentary statements, not actual questions

**Status:** Open — not yet investigated

**Symptom:** During a debate, an agent may present "questions" to the user (via HITL interrupt). However, these are not coherent questions but rather fragmentary statements extracted from the debate transcript. The user cannot meaningfully respond to them.

**Suspected cause:** The HITL interrupt mechanism (`hitl_agent_query_node` in `backend/workflow/hitl/nodes.py`) generates interrupts based on agent output analysis. The interrupt content may be derived from raw agent output segments rather than properly formulated questions. Alternatively, the legacy debate graph may not support HITL interrupts at all, and the feature only works correctly with Canvas-modeled workflows.

**Note:** This may be a fundamental limitation of the Legacy Workflow path. If HITL interrupts are designed for Canvas workflows only, the Legacy path may need a different approach or the feature should be disabled for legacy debates.

**Related files:**
- `backend/workflow/hitl/nodes.py:39-135` — `hitl_check_node()` and interrupt handling
- `backend/workflow/hitl/graph.py:85-151` — HITL graph construction
- `backend/workflow/debate_graph.py` — Legacy graph (no HITL check node)
