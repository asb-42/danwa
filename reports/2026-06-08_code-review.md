# Code Review — Deep-Dive (Post Sprint 39-49 Fixes)

**Date:** 2026-06-08
**Scope:** Full backend (API, workflow, services, state, persistence) + key frontend (registerWorkflowNodes.js)
**Baseline:** `a7b1b7a` (F-10 fix pushed)

---

## 1. Executive Summary

The codebase has matured significantly since the previous audit. The L6 (InterjectionService persistence), M11 (extension-zone), and C3 (verdict-map) fixes are well-implemented with good test coverage. However, three structural issues remain: (1) a **privilege-escalation vulnerability** in the self-registration endpoint that allows any user to register as `admin`; (2) a **duplicated prompt block** in `agent_nodes.py` that doubles the system prompt for every wf-critic invocation in transactional drafting, wasting tokens and confusing the LLM; and (3) an **unbounded in-memory subscriber map** in `events.py` that grows monotonically. The HITL security scanner and the safe-eval AST walker are solid designs. The concurrency story is much improved (F-01/F-02/F-04/F-06 fixes) but two `asyncio.get_event_loop()` call sites remain and should be modernized.

---

## 2. Critical & High Severity Issues (Must Fix)

### 2.1 Privilege Escalation via Self-Registration — Security

- **Location:** `backend/api/routers/auth.py:34-66`, [`register_user()`](backend/api/routers/auth.py:35)

- **The Problem:** The `POST /auth/register` endpoint accepts `body.role` from the request and passes it directly to `user_store.create(role=role)`. The only guard is promoting the first user to `admin` when `count() == 0`. After that, any unauthenticated caller can register with `{"email": "evil@x.com", "password": "...", "role": "admin"}` and gain full admin privileges — including the ability to list users, invite users, and manage tenants. The `UserCreate` model likely has a `role` field with a default, but nothing prevents the caller from overriding it.

- **The Fix:**

```python
# backend/api/routers/auth.py — register_user
@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(
    body: UserCreate,
    user_store=Depends(get_user_store),
):
    """Register a new user (self-signup). First user is auto-promoted to admin."""
    existing = user_store.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Self-registration always creates a "user" role.  Admin promotion
    # happens only for the very first account; subsequent users must be
    # invited by an admin (POST /auth/users/invite).
    role = "user"
    if user_store.count() == 0:
        role = "admin"
        logger.info("First user registered — promoting to admin: %s", body.email)

    password_hash = hash_password(body.password)

    try:
        user = user_store.create(
            email=body.email,
            display_name=body.display_name,
            password_hash=password_hash,
            role=role,
            tenant_id="_default",
        )
    except Exception as e:
        logger.error("Failed to create user %s: %s", body.email, e)
        raise HTTPException(status_code=500, detail="Failed to create user")

    logger.info("User registered: %s (role=%s)", user.email, user.role)
    return user_to_response(user)
```

### 2.2 Duplicated System Prompt Block for wf-critic — Correctness / Cost

- **Location:** `backend/workflow/nodes/agent_nodes.py:126-171`, [`_agent_node()`](backend/workflow/nodes/agent_nodes.py:95)

- **The Problem:** Inside the `if node_type == "wf-critic"` branch, the decision matrix, rules block, and JSON schema are appended to `system_prompt` **twice** — lines 132-151 and again at lines 152-171 are identical. This doubles the system prompt length for every wf-critic invocation in transactional drafting (~2-4 KB of duplicated text per call). The LLM receives redundant instructions, which wastes tokens, increases cost, and may cause the model to over-emphasize the rules.

- **The Fix:** Remove the duplicate block (lines 152-171):

```python
# backend/workflow/nodes/agent_nodes.py — inside _agent_node()
        if node_type == "wf-critic" and state.get("workflow_template") == WorkflowTemplate.TRANSACTIONAL_DRAFTING:
            from backend.models.transactional import CriticItem

            schema = CriticItem.model_json_schema()
            agent_tags = resolved_config.get("agent_tags") or []
            decision_matrix = get_decision_matrix(agent_tags)
            system_prompt = system_prompt + "\n\n" + decision_matrix + "\n\n"
            system_prompt += (
                "## Rules\n"
                "- Maximum 10 CriticItems per round. Prioritize blocking and critical severity.\n"
                "- You MUST NEVER say 'Das sollte überprüft werden' or 'Man sollte prüfen, ob…'. "
                "Instead: 'Die Klausel verstößt gegen X, weil Y.'\n"
                "- Every item MUST have a concrete target, principle, and flaw.\n\n"
            )
            system_prompt += "## Output Format\nRespond with a JSON array. Every object must match this schema:\n" + _json.dumps(
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": schema["properties"],
                        "required": schema.get("required", []),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
            # <-- DUPLICATE BLOCK REMOVED (was lines 152-171)
```

### 2.3 Unbounded `_subscribers` Map — Memory Leak

- **Location:** `backend/api/events.py:17`, [`_subscribers`](backend/api/events.py:17)

- **The Problem:** The module-level `_subscribers: dict[str, list[asyncio.Queue]]` maps `debate_id` → subscriber queues. When a client disconnects, `unsubscribe()` removes the queue, and if the list is empty, it pops the debate_id key. **However**, if a client disconnects without calling `unsubscribe()` (e.g. browser tab close without SSE teardown, network drop, or server-initiated close), the empty queue list and debate_id key remain forever. Over weeks of operation, this dict grows monotonically. With thousands of debates, this becomes a significant memory leak.

- **The Fix:** Add a cleanup mechanism — either a periodic task that removes empty entries, or use weak references:

```python
# backend/api/events.py — add cleanup
import asyncio

def _cleanup_stale_subscribers() -> None:
    """Remove debate_ids whose subscriber list is empty."""
    stale = [did for did, subs in _subscribers.items() if not subs]
    for did in stale:
        _subscribers.pop(did, None)
    if stale:
        logger.debug("Cleaned up %d stale subscriber entries", len(stale))


# In publish() and publish_async(), trigger cleanup periodically:
# (use a simple counter to avoid running on every publish)
_publish_count = 0

async def publish_async(debate_id: str, event_type: str, data: Any) -> None:
    """Async version of publish — for use inside async nodes."""
    global _publish_count
    _publish_count += 1
    if _publish_count % 100 == 0:
        _cleanup_stale_subscribers()

    subs = _subscribers.get(debate_id, [])
    if not subs:
        return
    payload = json.dumps(data, default=str)
    for q in subs:
        q.put_nowait((event_type, payload))
```

---

## 3. Architectural & Design Improvements (Should Fix)

### 3.1 `_serialize_state` Destroys Nested Dict Structure — Correctness

- **Location:** `backend/workflow/workflow_runner.py:379-394`, [`_serialize_state()`](backend/workflow/workflow_runner.py:379)

- **The Problem:** Line 391 converts nested dicts to `{k: str(v)}`, which flattens all nested structures (e.g. `consensus_result`, `tone_profiles`, `build_responses`) into string representations. This means state snapshots stored in SQLite lose their structure and cannot be queried or reconstructed. The `state_snapshot` is supposed to enable replay and debugging, but stringified nested dicts make that impossible.

- **The Fix:** Recursively serialize nested dicts instead of stringifying them:

```python
def _serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Serialize WorkflowState for snapshot storage.

    Converts non-JSON-serializable values to strings.  Nested dicts
    are preserved (not stringified) so snapshots can be queried.
    """
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, dict):
            return {k: _serialize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_serialize_value(item) for item in value]
        # Pydantic models
        if hasattr(value, "model_dump"):
            return _serialize_value(value.model_dump(mode="json"))
        # Enums
        if hasattr(value, "value"):
            return value.value
        return str(value)

    return {k: _serialize_value(v) for k, v in state.items()}
```

### 3.2 `DebateStore.move()` Non-Atomic Race — Concurrency

- **Location:** `backend/persistence/debate_store.py:139-155`, [`move()`](backend/persistence/debate_store.py:139)

- **The Problem:** `move()` calls `target_store.put(debate_id, debate)` first (which writes to the target's memory and disk), then deletes from the source. If the target's disk write fails silently (in-memory succeeds, disk fails — possible on NFS/EBS), the debate exists in both stores' in-memory caches but only in the source's disk. On next restart, it appears in the source again. More critically, if the process crashes between the `put` and the source `unlink`, the debate is duplicated on disk.

- **The Fix:** Wrap in a try/except that rolls back the target on source-deletion failure:

```python
def move(self, debate_id: str, target_store: DebateStore) -> bool:
    """Move a debate file to another project's store and update caches."""
    with self._lock:
        debate = self._cache.get(debate_id)
        if not debate:
            return False
    try:
        target_store.put(debate_id, debate)
    except Exception as exc:
        logger.error("Failed to write debate %s to target store: %s", debate_id, exc)
        return False
    with self._lock:
        self._cache.pop(debate_id, None)
    path = self._data_dir / f"{debate_id}.json"
    try:
        if path.exists():
            path.unlink()
    except Exception as exc:
        logger.error("Failed to delete source debate file after move %s: %s", path, exc)
        # Note: target already has the data, so the move partially succeeded.
        # The source file remains but the in-memory cache no longer references it.
    return True
```

### 3.3 `InterjectionService._ensure_loaded` Accesses Private Attribute — Coupling

- **Location:** `backend/workflow/interjection.py:221`, [`_ensure_loaded()`](backend/workflow/interjection.py:192)

- **The Problem:** `channel._set_count` is a private implementation detail of `InMemoryChannel` (and `RedisChannel`). Accessing it from `InterjectionService` couples the service to the pub/sub implementation. If the internal counter is renamed or the channel implementation changes, the hydration version tracking silently breaks — `_hydration_version` would always be `None`/`0`, causing redundant re-hydration on every operation.

- **The Fix:** Expose `set_count` as a public method/property on the channel protocol:

```python
# backend/state/pubsub.py — add to PubSubChannel protocol and impls
class PubSubChannel(Protocol):
    """A named pub/sub channel."""
    @property
    def set_count(self) -> int:
        """Number of times publish/set has been called on this channel."""
        ...

# InMemoryChannel:
    @property
    def set_count(self) -> int:
        """Number of times publish/set has been called on this channel."""
        return self._set_count

# backend/workflow/interjection.py:221 — use public API
    current_version = channel.set_count
```

### 3.4 No LLM Call Timeout — Resilience

- **Location:** `backend/services/llm_service.py:175-200`, [`generate()`](backend/services/llm_service.py:175)

- **The Problem:** The `generate()` method calls the LLM endpoint without an explicit timeout (or relies on `httpx` defaults, which are effectively unlimited for streaming). If the LLM provider hangs (e.g. overloaded API, network partition), the agent node blocks indefinitely. With a `max_rounds * num_agents` concurrency, a single hung LLM call can block the entire workflow for minutes. The `workflow_runner` has a `recursion_limit` but no wall-clock timeout per node.

- **The Fix:** Pass a timeout to the httpx call and expose it on the profile:

```python
# backend/services/llm_service.py — in generate()
    timeout_seconds = self._profile.timeout_seconds if hasattr(self._profile, 'timeout_seconds') and self._profile.timeout_seconds else 120.0

    if self._is_local():
        response = await client.post(
            f"{api_base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout_seconds,  # Explicit timeout
        )
```

---

## 4. Performance & Resilience Optimizations (Nice to Have)

### 4.1 `asyncio.get_event_loop()` Deprecated in Python 3.11+

- **Location:** `backend/api/events.py:51`, `backend/workflow/interjection.py:599,601`

- **The Problem:** `asyncio.get_event_loop()` raises a `DeprecationWarning` in Python 3.10+ when called without a running loop and will be removed in Python 3.12. In `events.py`, `publish()` (sync function) uses it to call `call_soon_threadsafe`. In `interjection.py`, `consume_blocking()` uses `.time()` for deadline tracking.

- **The Fix:**

```python
# backend/api/events.py:51 — use asyncio.get_running_loop() for the sync publish
def publish(debate_id: str, event_type: str, data: Any) -> None:
    """Publish an event to all subscribers (sync-safe)."""
    subs = _subscribers.get(debate_id, [])
    if not subs:
        return
    payload = json.dumps(data, default=str)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # No event loop running — cannot dispatch
    for q in subs:
        loop.call_soon_threadsafe(q.put_nowait, (event_type, payload))

# backend/workflow/interjection.py:599 — use asyncio.get_running_loop()
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
```

### 4.2 BM25 Reconstructs `BM25Okapi` on Every Non-Cached Query

- **Location:** `backend/services/dms/hybrid_retriever.py:134-156`, [`_bm25_retrieve()`](backend/services/dms/hybrid_retriever.py:134)

- **The Problem:** On cache miss (every 5 minutes), `_fetch_chunks_uncached` loads all chunks, then `_bm25_retrieve` tokenizes the entire corpus and constructs a new `BM25Okapi`. For a project with 10,000 chunks, this means ~10,000 string splits + object allocations every 5 minutes. The BM25 index itself is not cached — only the raw chunks are.

- **The Fix:** Cache the BM25 index alongside the corpus:

```python
# backend/services/dms/hybrid_retriever.py
    def __init__(self, ...):
        ...
        # BM25 corpus + index cache: (project_id, timestamp, chunks, bm25_index)
        self._corpus_cache: tuple[str, float, list[dict], BM25Okapi | None] | None = None

    def _fetch_chunks(self, project_id: str | None) -> tuple[list[dict], BM25Okapi | None]:
        now = time.time()
        if self._corpus_cache is not None and self._corpus_cache[0] == project_id and (now - self._corpus_cache[1]) < _CORPUS_CACHE_TTL:
            return self._corpus_cache[1], self._corpus_cache[3]

        chunks = self._fetch_chunks_uncached(project_id)
        bm25 = None
        if chunks:
            tokenized = [self._tokenize(c["text"]) for c in chunks]
            bm25 = BM25Okapi(tokenized)
        self._corpus_cache = (project_id, now, chunks, bm25)
        return chunks, bm25
```

### 4.3 `jwt_secret_key` Empty Default Can Lead to Insecure Tokens

- **Location:** `backend/core/config.py:95`

- **The Problem:** `jwt_secret_key: str = ""` defaults to empty string. If `auth_enabled=True` but `DANWA_JWT_SECRET_KEY` is not set, tokens are signed with an empty key — trivially forgeable. There is no startup validation that warns or fails when this combination occurs.

- **The Fix:** Add a startup check:

```python
# backend/main.py — in lifespan(), after settings load
    if settings.auth_enabled and not settings.jwt_secret_key:
        logger.critical(
            "SECURITY: auth_enabled=True but jwt_secret_key is empty! "
            "Set DANWA_JWT_SECRET_KEY in .env. Disabling auth as fallback."
        )
        settings.auth_enabled = False
```

### 4.4 `_subscribers` in `events.py` Is Single-Process Only

- **Location:** `backend/api/events.py:17`

- **The Problem:** The SSE event bus is a module-level dict. In a multi-worker deployment (e.g. Gunicorn with 4 workers), worker A publishes events but worker B's SSE subscriber never sees them. The `InterjectionService` solved this with pub/sub (F-01), but `events.py` still uses the old in-memory pattern. This means SSE streaming only works when the publishing workflow and the subscribing SSE endpoint happen to be in the same worker process.

- **The Fix:** Wire `publish_async` through the shared `PubSubBackend` (same as interjection wake events), or document that SSE is single-process and recommend a reverse-proxy sticky-session configuration.

---

## 5. Clarifying Questions for the Author

1. **Multi-worker deployment target:** The `InterjectionService` F-01 fix added cross-process wake-up via `PubSubBackend`, but `events.py` (`_subscribers`) and `_running_tasks` (`workflow_runner.py:40`) are still single-process dicts. Is the production deployment single-worker (Uvicorn) or multi-worker (Gunicorn)? If multi-worker, both `events.py` and `_running_tasks` need the same pub/sub treatment.

2. **`auth_enabled=False` production usage:** The dev-mode fallback in `get_current_user` returns a synthetic admin with `tenant_id="_default"`. Is this ever used in production (e.g. behind a reverse proxy that handles auth externally), or is it strictly for local development? If the latter, the startup warning (4.3) should be a hard failure.

3. **`DebateStore` migration to SQLite:** The `DebateStore` uses JSON files + in-memory cache + `threading.Lock`. With the `InterjectionService` already on SQLite, is there a plan to migrate `DebateStore` to SQLite as well? The JSON approach has no schema versioning and the `_save_to_disk` method does no atomic-write (partial writes on crash corrupt the file).
