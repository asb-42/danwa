# Code Review — 2026-06-09 (Post-Sprint-49 Production-Grade Review)

**Scope:** Full backend codebase after recent fixes (2026-06-08 review findings 2.1–4.3).
**Focus:** Correctness, reliability, security, concurrency, and maintainability.
**Reviewer:** Automated deep-dive analysis.

---

## 1. Executive Summary

The recent fix batch (F-08 through F-10, plus review findings 2.1–4.3) addressed the most critical
issues cleanly. However, a deeper pass reveals remaining risks — most notably a no-op XSS
sanitization function, unbounded in-memory HITL state, a TOCTOU race in `DebateStore.update()`,
and residual `asyncio.new_event_loop()` patterns that should be modernized.

**Findings breakdown:**

| Severity | Count | IDs |
|----------|-------|-----|
| Critical | 2 | C-01, C-02 |
| High | 3 | H-01, H-02, H-03 |
| Should Fix | 5 | S-01 … S-05 |
| Nice to Have | 4 | N-01 … N-04 |

---

## 2. Critical Findings

### C-01 — `sanitize_for_display()` is a no-op (XSS defense bypassed)

**File:** [`backend/workflow/hitl/security.py:276`](backend/workflow/hitl/security.py:276)

```python
content = content.replace("<", "<").replace(">", ">")
```

Both replacements map a character to **itself**. Verified via hex dump:

```
3c → 3c   (< → <)
3e → 3e   (> → >)
```

The docstring says "Remove potential HTML/script injection for display" but the function
performs zero escaping. Any content returned via HITL endpoints that passes through
`sanitize_for_display()` before being embedded in an HTML context is vulnerable to stored XSS.

**Impact:** If any frontend component renders HITL interaction content as raw HTML
(e.g. an audit log view, report PDF, or email digest), attacker-supplied interjection
content like `<script>alert(1)</script>` would execute.

**Fix:**

```python
content = content.replace("&", "&").replace("<", "<").replace(">", ">")
```

### C-02 — HITL interaction log grows unboundedly (memory leak)

**File:** [`backend/workflow/hitl/api.py:56`](backend/workflow/hitl/api.py:56), [`backend/workflow/hitl/api.py:275`](backend/workflow/hitl/api.py:275)

```python
_interaction_log: dict[str, list[dict]] = {}
```

`_log_interaction()` appends every interaction to `_interaction_log[debate_id]`. The
cleanup function [`cleanup_hitl_state()`](backend/workflow/hitl/api.py:267) deliberately
**keeps** the log (line 272: "Keep interaction log for history") while only clearing
`_active_interrupts` and `_hitl_config`.

In a long-running deployment, `_interaction_log` accumulates entries for every debate
that ever ran, never freed. Each interaction entry includes full content text, metadata
dicts, and timestamps. With hundreds of debates and thousands of interactions, this will
consume significant heap.

Additionally, there is **no limit** on `_active_interrupts` — if a debate registers a
new query while one is already active, the previous interrupt is silently overwritten
(line 158: `_active_interrupts[debate_id] = interrupt`), potentially losing the agent's
question without the user ever seeing it.

**Fix:**

1. Add a `_max_log_per_debate` cap (e.g. 1000) and rotate oldest entries.
2. Add a TTL sweep (e.g. 24h) for all three in-memory dicts.
3. Add a guard in `register_agent_query()` to check if an interrupt is already
   active for the debate and either queue or reject the second one.

---

## 3. High-Severity Findings

### H-01 — `DebateStore.update()` releases lock before disk write (TOCTOU)

**File:** [`backend/persistence/debate_store.py:166`](backend/persistence/debate_store.py:166)

```python
def update(self, debate_id: str, **kwargs: Any) -> dict | None:
    with self._lock:
        debate = self._cache.get(debate_id)
        if not debate:
            return None
        debate.update(kwargs)        # ← in-memory mutation under lock
    self._save_to_disk(debate_id)    # ← disk write OUTSIDE lock
    return debate
```

The read-modify-write to `_cache` is atomic, but the `_save_to_disk()` call runs after
the lock is released. If the process crashes (or a `KeyboardInterrupt` fires) between
the `with` block exit and `_save_to_disk()`, the update is lost — the in-memory cache
had the mutation but it was never persisted.

In contrast, [`put()`](backend/persistence/debate_store.py:97) calls `_save_to_disk()`
inside the lock.

**Fix:** Move `_save_to_disk()` inside the `with self._lock:` block. The disk I/O is
fast (small JSON files) and the lock is per-store (not global), so contention is minimal.

### H-02 — `_serialize_state()` has no recursion depth guard (new risk from 3.1 fix)

**File:** [`backend/workflow/workflow_runner.py:388`](backend/workflow/workflow_runner.py:388)

The recursive `_serialize_value()` function walks dicts, lists, and Pydantic models
without a depth limit. The previous implementation used `str(v)` (flat) and was immune
to this. If a Pydantic model has circular references (e.g. a self-referential graph node
structure), this will raise `RecursionError` and crash the workflow finalization path.

**Fix:** Add a `max_depth` parameter (default 20) and a `current_depth` counter:

```python
def _serialize_value(v: Any, depth: int = 0) -> Any:
    if depth > 20:
        return str(v)
    ...
    if isinstance(v, dict):
        return {k: _serialize_value(val, depth + 1) for k, val in v.items()}
```

### H-03 — `generate_sync()` creates a new event loop per call

**File:** [`backend/services/llm_service.py:717`](backend/services/llm_service.py:717)

```python
def _run_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(self.generate(...))
    finally:
        loop.close()
```

This allocates and tears down a full event loop + thread pool per call. Under load
(e.g. title generation, service LLM calls, follow-up prompts), this creates GC pressure
and thread churn.

The same pattern exists in:
- [`backend/tasks/workflow.py:43`](backend/tasks/workflow.py:43)
- [`backend/tasks/debate.py:41`](backend/tasks/debate.py:41)

**Fix:** Use `asyncio.run()` (Python 3.10+), which handles loop lifecycle internally,
or maintain a module-level `_sync_loop` that is reused:

```python
import asyncio

def _run_in_thread():
    return asyncio.run(self.generate(...))
```

---

## 4. Should-Fix Findings

### S-01 — `_interaction_log` is the only HITL state not backed by the workflow state backend

**File:** [`backend/workflow/hitl/api.py:56`](backend/workflow/hitl/api.py:56)

Sprint 38 migrated `_paused_debates` into `WorkflowStateBackend` (Redis/in-memory),
but `_interaction_log` and `_active_interrupts` remain as module-level dicts. In a
multi-worker Gunicorn deployment, each worker has its own copy — an inject submitted
via worker A is invisible to worker B's HITL status endpoint.

The `is_paused()` function correctly delegates to `get_workflow_state().get_hitl_pause()`,
but `get_pending_injects()`, `consume_inject()`, and `list_interactions()` all read from
the process-local `_interaction_log`.

**Impact:** HITL inject/interact endpoints return inconsistent data depending on which
worker handles the request.

### S-02 — `_active_interrupts` silently overwrites pending queries

**File:** [`backend/workflow/hitl/api.py:158`](backend/workflow/hitl/api.py:158)

```python
_active_interrupts[debate_id] = interrupt
```

If two agents both call `register_agent_query()` in the same debate (e.g. the strategist
and the critic both need clarification in the same round), the first interrupt is silently
discarded. The user never sees it.

**Fix:** Queue interrupts per-debate rather than replacing, or raise/reject if one is
already active.

### S-03 — `update_me` accepts raw `dict` without Pydantic validation

**File:** [`backend/api/routers/auth.py:139`](backend/api/routers/auth.py:139)

```python
@router.put("/me", response_model=UserResponse)
def update_me(
    body: dict,        # ← should be a Pydantic model
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    display_name = body.get("display_name")
```

All other endpoints use typed request models. This endpoint accepts any JSON body,
which bypasses input validation (e.g. no length limit on `display_name`, no stripping
of whitespace, no protection against injection if display_name is ever rendered).

**Fix:** Create an `UpdateProfileRequest` Pydantic model with appropriate constraints.

### S-04 — `change_password` does not revoke existing JWT tokens

**File:** [`backend/api/routers/auth.py:157`](backend/api/routers/auth.py:157)

After a password change, all previously issued access and refresh tokens remain valid
until their natural expiration. If a user changes their password because their account
was compromised, the attacker's stolen token continues to work.

**Fix:** Add a `token_version` field to the User model and include it in JWT claims.
Increment on password change; reject tokens with stale version.

### S-05 — `select_tenant` does not validate tenant membership for the target tenant's role

**File:** [`backend/api/routers/auth.py:258`](backend/api/routers/auth.py:258)

The `select_tenant` endpoint verifies membership (`membership_store.get(tenant_id, user.id)`)
and issues a new token with the selected tenant. However, the `role` in the new token is
the **user's global role** (`user.role`), not the role within that tenant. This means a user
who is `"admin"` globally but `"viewer"` in tenant X would get an `"admin"` token when
switching to tenant X.

```python
access_token = create_access_token(user, tenant_id=tenant_id)
# user.role is the GLOBAL role, not tenant-specific
```

**Fix:** Use `membership.role` as the token role:

```python
access_token = create_access_token(user, tenant_id=tenant_id, role_override=membership.role)
```

---

## 5. Nice-to-Have Findings

### N-01 — Diagnostic logging left in production code

**Files:**
- [`backend/workflow/interjection.py:513`](backend/workflow/interjection.py:513) — `DIAG submit()`
- [`backend/workflow/interjection.py:731`](backend/workflow/interjection.py:731) — `DIAG consume()`
- [`backend/workflow/nodes/agent_nodes.py:236`](backend/workflow/nodes/agent_nodes.py:236) — `DIAG Failed to consume`

These `DIAG` prefixed `logger.info()` calls were added during debugging and should be
downgraded to `logger.debug()` or removed before release.

### N-02 — 127 bare `except Exception:` clauses across the backend

Many swallow errors with only `logger.debug(..., exc_info=True)`. While appropriate for
non-critical side effects (audit logging, SSE publishing), some are in data-persistence
paths where silent failure causes data loss:

- [`backend/workflow/workflow_runner.py:247`](backend/workflow/workflow_runner.py:247) — debate record update
- [`backend/workflow/workflow_runner.py:306`](backend/workflow/workflow_runner.py:306) — debate record update (cancel path)
- [`backend/workflow/workflow_runner.py:348`](backend/workflow/workflow_runner.py:348) — debate record update (failure path)

These should log at `logger.warning()` minimum.

### N-03 — `RenderJobStore` opens a new SQLite connection per operation

**File:** [`backend/services/render_job_store.py:32`](backend/services/render_job_store.py:32)

Unlike `AuditLogger` and `InterjectionService` which cache their connections (fixed in
earlier sprints), `RenderJobStore._connect()` opens a fresh `sqlite3.connect()` on every
call. This adds ~1-2ms latency per render job operation and creates file descriptor churn
under concurrent rendering.

**Fix:** Adopt the same cached-connection + double-checked-locking pattern used by
`AuditLogger._get_conn()`.

### N-04 — `events.py` cleanup runs every 100 publishes — no timer fallback

**File:** [`backend/api/events.py:62`](backend/api/events.py:62)

The stale-subscriber cleanup (2.3 fix) is triggered by `_publish_count % 100 == 0`. In
low-traffic deployments, it may take hours between cleanups, allowing empty subscriber
lists to accumulate. A timer-based fallback (e.g. run cleanup every 60 seconds regardless
of publish count) would be more reliable.

---

## 6. Verification of Previous Fixes

| Fix | Status | Notes |
|-----|--------|-------|
| 2.1 — Auth privilege escalation | ✅ Correct | `role = "user"` hardcoded in `register_user()` |
| 2.2 — Duplicate system_prompt | ✅ Correct | Single injection block remains for wf-critic + TRANSACTIONAL_DRAFTING |
| 2.3 — Subscriber cleanup | ✅ Correct | `_cleanup_stale_subscribers()` runs every 100 publishes |
| 3.1 — Recursive serialization | ✅ Functional | Missing depth guard (H-02 above) |
| 3.2 — `DebateStore.move()` | ✅ Correct | `target_store.put()` wrapped in try/except |
| 3.3 — `set_count` property | ✅ Correct | Protocol + both impls expose public property |
| 3.4 — LLM timeout | ✅ Correct | `LLMProfile.timeout` passed to httpx |
| 4.1 — `get_running_loop()` | ✅ Correct | Zero `get_event_loop()` calls remain in backend |
| 4.2 — BM25 cache | ✅ Correct | Index cached alongside corpus in `_corpus_cache` tuple |
| 4.3 — JWT secret check | ✅ Correct | Startup disables auth if `jwt_secret_key` is empty |

---

## 7. Recommended Priority

| Priority | ID | Effort | Risk |
|----------|----|--------|------|
| P0 — Ship-blocking | C-01 | 5 min | XSS in HITL display paths |
| P0 — Ship-blocking | C-02 | 1-2h | Memory leak in long-running deployments |
| P1 — Next sprint | H-01 | 15 min | Data loss on crash during `DebateStore.update()` |
| P1 — Next sprint | H-02 | 15 min | RecursionError on deep state serialization |
| P1 — Next sprint | H-03 | 30 min | Thread/event-loop churn under load |
| P2 — Backlog | S-01 | 2-4h | Multi-worker HITL inconsistency |
| P2 — Backlog | S-02 | 1h | Lost agent queries |
| P2 — Backlog | S-03 | 30 min | Unvalidated profile update input |
| P2 — Backlog | S-04 | 1-2h | Token non-revocation after password change |
| P2 — Backlog | S-05 | 30 min | Cross-tenant role escalation via tenant switch |
| P3 — Cleanup | N-01 | 10 min | Diagnostic noise in logs |
| P3 — Cleanup | N-02 | 1h | Silent data loss in persistence paths |
| P3 — Cleanup | N-03 | 30 min | SQLite connection churn in RenderJobStore |
| P3 — Cleanup | N-04 | 15 min | Delayed cleanup in low-traffic deployments |
