# Code Review — Sprints 39-49 (Blueprint/Workflow Audit Fixes)

**Datum:** 2026-06-07
**Reviewer:** Senior Engineering (Production-Grade)
**Scope:** `feat/current-draft-bound` Branch (Sprints 39-49), gemerged in `1d08d98`, HEAD `a63a7ee`
**Primärer Fokus:** L6 (InterjectionService SQLite-Persistenz) + M10 (Connection-Reuse), M11 (Extension-Routing), M3 (Decision-Edges in Topo-Sort), L4/L5 (Frontend-Splits)
**Risikoklasse:** Production multi-process Python (FastAPI + Gunicorn 4 workers, UvicornWorker, asyncio event loop)
**Traffic-Profil:** Interaktiv — wenige submits/s, blocking consumes bis 5 min, Workflow-Sessions Minuten–Stunden

---

## 1. Mentales Modell

### 1.1 Subsystem: User-Interjection (HITL)

```
[User / HITL API / Frontend]
   │
   │ POST /api/v1/workflow/{sid}/interject  →  interjection_service.submit()
   │ POST /api/v1/hitl/inject               →  interjection_service.submit()
   │
   ▼
[InterjectionService Singleton] ── module-level ── erstellt beim Import (bevor event loop startet)
   │
   │ in-memory queues[session_id] + asyncio.Event wake_events[session_id]
   │ seit L6: SQLite mirror in data/blueprints.db (gleiche DB wie audit_logger + state_snapshot)
   │
   ▼
[Workflow Node] system_nodes.interjection_node / agent_nodes._agent_node
   │
   │ consume_blocking(session_id, timeout=300)  ← blockiert via asyncio.Event
   │ consume(session_id)                        ← opportunistisch
   │
   ▼
[Workflow runner] interjection_service.clear(session_id)  im finally-Block
```

### 1.2 Kritische Pfade

**Pfad A — Submit ohne Response (5-min blocking):**
`POST /interject` → `submit()` → `asyncio.Lock` + `_ensure_loaded` (SELECT) + `_persist_insert` (INSERT) + wake event → return 200. Gleichzeitig: Workflow-Worker hängt in `consume_blocking` → wacht auf → `_drain_pending` → `asyncio.Lock` + `_ensure_loaded` (SELECT) + `_persist_mark_consumed` (UPDATE).

**Pfad B — Server-Restart mit offener Interjection:**
Worker crashed → neuer Worker startet → `interjection_service` Singleton neu initialisiert → `_queues` und `_loaded_sessions` leer → `consume_blocking` für offene Session → `_ensure_loaded` lädt pending rows aus DB → returnt sie an den Node.

**Pfad C — Multi-Worker-Deployment (4 Gunicorn-Worker):**
Worker A.submit() schreibt nach DB. Worker B.consume() liest aus DB — **cross-worker visibility funktioniert dank L6**. ABER: Worker B's `asyncio.Event` ist nicht von Worker A's `submit()` gesetzt → blocking consumer auf Worker B wartet 5 min oder bis eigenes `submit()` kommt.

### 1.3 Concurrency-Primitive-Inventar

| Primitive | Wo | Schutz | Schützt vor |
|-----------|-----|--------|-------------|
| `asyncio.Lock` | InterjectionService | Pro event loop, pro Prozess | Coroutine-level race |
| `threading.RLock` | `_get_conn`, `_persist_*` | Pro Prozess | Thread-level race (FastAPI threadpool) |
| `asyncio.Event` | `_wake_events[session_id]` | Pro event loop, pro Prozess | Wake-up ohne polling |
| `interjection_id` UUID | `f"inj-{uuid4().hex[:12]}"` | Nicht kollidierend | Doppel-Insert |
| `created_at` ISO 8601 | Sortierschlüssel | Microsecond-Auflösung | FIFO-Order |

---

## 2. Findings

> Sortiert nach Severity (CRITICAL → HIGH → MEDIUM → LOW → INFO). Confidence in [0, 1].

---

### F-01 — Multi-Worker Wake-Up für `consume_blocking` ist nicht gelöst (L6 löst nur die Persistenz, nicht das Wecksignal)

**Severity:** HIGH
**Confidence:** 0.95
**Files:** `backend/workflow/interjection.py:297-308, 387-461`, `Dockerfile.backend` (4× `--workers`)
**Category:** Concurrency / Cross-Process Correctness

**Mechanismus:**

L6 macht die In-Memory-Queue persistent in SQLite — `submit()` schreibt, `consume()` liest beim ersten Zugriff per `_ensure_loaded()`. Damit ist die **Daten-Sichtbarkeit** cross-worker gelöst.

Die **Wake-Up-Mechanik** für `consume_blocking()` ist aber weiterhin prozess-lokal:

```python
# interjection.py:353 — submit():
self._get_wake_event(session_id).set()    # ← nur im aktuellen Prozess

# interjection.py:438 — consume_blocking:
await asyncio.wait_for(event.wait(), ...) # ← wartet auf Event im aktuellen Prozess
```

In `Dockerfile.backend` läuft die App mit `--workers 4` (Gunicorn + UvicornWorker) — 4 separate Python-Prozesse, 4 separate `asyncio.Event`-Instanzen pro Session.

**Failure Scenario:**

1. Workflow-Node läuft in Worker A und ruft `interjection_service.consume_blocking("sess-42", timeout=300)`.
2. User schickt `POST /api/v1/workflow/sess-42/interject` → landet per Load-Balancing in Worker B.
3. Worker B's `submit()` setzt das `asyncio.Event` in Worker B und schreibt in SQLite.
4. Worker A's `consume_blocking` schläft weiter — sein Event wurde nie gesetzt.
5. Nach 5 min: `TimeoutError` → `is_paused=True`, der User-Inject bleibt in der DB bis Worker A ihn nach 5 min durch einen eigenen `submit` oder `_ensure_loaded` liest.

Der User sieht entweder eine 5-Min-Pause oder die nächste `consume()` (durch z.B. `agent_node.consume()`) findet die Daten — aber **die Pause-Mechanik schlägt fehl**.

**User/Business Impact:**

- "Pause and wait for human input" funktioniert in Multi-Worker-Setups nur, wenn `submit()` zufällig im selben Worker landet wie `consume_blocking()`. Bei 4 Workern ist das 25 % — der User wartet typischerweise das volle Timeout ab.
- Das Symptom ist nicht offensichtlich: `_drain_pending` ruft `_ensure_loaded` und lädt die Daten **beim ersten Aufruf** — d.h. der Node bekommt die Daten beim nächsten `consume()`, aber die "echte Pause" hat versagt.
- Audit H1 (Sprint 37+38) hat nur die `wait_for_pause`/`wait_for_resume`-Mechanik in `workflow_state.py` auf Redis-Backend umgestellt. Der `interjection_service` selbst wurde **nicht** migriert. Der Audit-Eintrag suggeriert fälschlicherweise Vollständigkeit.

**Remediation:**

Option A — Redis-Pub/Sub Wake (analog Sprint 37):
```python
async def consume_blocking(self, session_id, ..., timeout=300):
    event = self._get_wake_event(session_id)
    # Subscribe to Redis channel for cross-process wake
    pubsub = await get_redis().pubsub()
    await pubsub.subscribe(f"interjection:{session_id}:wake")
    # ... event.wait() with race against pubsub.get_message
```

Option B — DB-Polling mit kürzerem Timeout (Fallback):
- `consume_blocking` pollt alle 0.5 s die DB auf neue pending rows; User-Experience nahezu identisch, ohne Redis.

Option C — Per-Worker-Routing (Load-Balancer mit Session-Sticky):
- Nicht empfohlen, da es den H1-Sinn (Worker-agnostic) zurücknimmt.

**Tradeoff:**

- Option A: Sauberste Lösung, aber Redis-Abhängigkeit (existiert bereits in `RedisWorkflowState`). Implementierungs-Aufwand: ~150 LOC, ~10 Tests.
- Option B: Pragmatisch, ~30 LOC, kein neuer Infra-Layer. Polling-Kosten 0.5 s × 4 Worker × N Sessions = irrelevant.
- Aktuell: 5-min-Timeout pro blocking call, sehr schlechte UX.

---

### F-02 — Synchronous SQLite I/O läuft im asyncio.Event-Loop, blockiert alle Coroutinen

**Severity:** HIGH
**Confidence:** 0.85
**Files:** `backend/workflow/interjection.py:341-357, 471-504, 534-548, 556-564`
**Category:** Performance / Event-Loop Starvation

**Mechanismus:**

Alle vier Public-Methoden (`submit`, `_drain_pending`, `get_pending`, `clear`) sowie `_ensure_loaded` rufen `_persist_*` auf — und alle laufen **innerhalb** des `async with self._lock` (asyncio.Lock) ab. Die `_persist_*` und `_ensure_loaded` sind **synchron**:

```python
async with self._lock:                       # asyncio.Lock — hält coroutines
    self._ensure_loaded(session_id)          # sync: conn.execute + fetchall
    self._queues.setdefault(...).append(...)
    self._get_wake_event(session_id).set()
    self._persist_insert(interjection)       # sync: conn.execute + commit
```

SQLite-Operationen blockieren den OS-Thread. Bei uvicorn-Workern läuft genau **ein** OS-Thread pro Prozess als Event-Loop. Jeder ms SQLite-I/O = eine ms in der **keine andere Coroutine** (HTTP-Request, SSE-Push, andere Workflow-Nodes) fortgesetzt werden kann.

Konkret blockierende Calls in einem `_persist_insert`:
- `mkdir` falls Pfad nicht existiert (nur erste Init, danach gecached)
- `conn.execute("INSERT …")` — ~50-200 µs bei WAL auf SSD
- `conn.commit()` — `fsync` mit `synchronous=NORMAL` ist asynchron, **mit** Default `synchronous=FULL` blockiert fsync — Größenordnung 1-10 ms auf rotierender Disk, 0.1-1 ms auf SSD, 5-50 ms auf Network-Storage (NFS, EBS)
- `logger.warning()` bei Fehler: weiterer Sync-I/O

**Failure Scenario:**

1. Workflow-Session mit ~50 Interjections, sehr aktiv.
2. Disk bekommt Latenz-Spike (z.B. EBS-Volume-Throttling, NFS-Disconnect, Backup-Window).
3. `submit()` wartet 5+ Sekunden auf `conn.commit()`.
4. Während dieser 5 s: **alle** anderen Coroutinen im selben Worker-Process hängen — inklusive:
   - Andere laufende Workflow-Nodes
   - SSE-Streams an andere User
   - Health-Checks
   - Andere `interjection_service.submit()` Calls
5. Bei 4 Workern: 1/4 der Kapazität ist im "Wedged"-Zustand. Uvicorn kann keine neuen Requests annehmen. Frontend zeigt timeouts.

`_ensure_loaded` ist beim ersten Zugriff pro Session schlimmer: `SELECT … WHERE session_id = ? AND status = 'pending' ORDER BY created_at ASC` — bei einer Session mit vielen Rows + Table-Scan (kein Index-Hint nutzbar wenn `session_id, status` Index fehlschlägt) kann das mehrere ms blockieren.

**Bemerkung:** `audit_logger` und `state_snapshot` (M10) haben exakt dasselbe Pattern — der Fehler ist also **strukturell repliziert**, nicht L6-spezifisch. L6 hat den existierenden Pattern kopiert, was die Konsistenz erhält, aber die inhärente Schwäche konserviert.

**User/Business Impact:**

- P99-Latenz von `POST /interject` ist an die Disk-Fsync-Latenz gebunden.
- Bei 4 Workern ist 1 Worker = 25 % der Kapazität, die unter Disk-Latenz leidet.
- Kein Mechanismus erkennt "Disk ist langsam" und degraded gracefully.

**Remediation:**

`asyncio.to_thread` für alle DB-Operationen, **außerhalb** des asyncio.Lock:
```python
async def submit(self, session_id, content, source="user", metadata=None):
    interjection_id = f"inj-{uuid.uuid4().hex[:12]}"
    interjection = Interjection(...)

    # Fast in-memory path — kein Lock nötig, weil asyncio ist single-threaded
    async with self._lock:
        self._ensure_loaded(session_id)  # könnte man auch rausziehen
        self._queues.setdefault(session_id, []).append(interjection)
        self._get_wake_event(session_id).set()

    # Slow DB path — offload to thread, no lock held
    if self._db_path is not None:
        asyncio.create_task(
            asyncio.to_thread(self._persist_insert_sync, interjection)
        )

    return interjection_id
```

Alternativ: `aiosqlite` statt `sqlite3` — echte async I/O, kein Thread-Block.

**Tradeoff:**

- `asyncio.to_thread`: minimal-invasiv, bremst die Event-Loop nicht. Verliert die "sofort persistiert"-Garantie (DB-Lag 1-5 ms), die aber für die L6-Zwecke (Restart-Resilienz) irrelevant ist.
- `aiosqlite`: idiomatische async-Lösung, aber neue Dep + Refactor von 3 Stores (audit, snapshot, interjection) gleichzeitig.
- Aktuell: 4× Worker = 25 %-Risiko pro Spike.

---

### F-03 — `asyncio.Lock` + `threading.RLock` verschachtelt ohne klare Lock-Order-Doku

**Severity:** MEDIUM
**Confidence:** 0.7
**Files:** `backend/workflow/interjection.py:81, 84, 173, 224, 257, 281`, `backend/workflow/audit_logger.py:46, 64-79`
**Category:** Maintainability / Future Deadlock Risk

**Mechanismus:**

Aktueller Lock-Acquire-Order in `submit()`:
1. `asyncio.Lock` (`self._lock`)
2. `threading.RLock` (`self._db_lock`) — transitiv in `_persist_insert`

Aktueller Lock-Acquire-Order in `_ensure_loaded()` (von `submit()` aufgerufen):
1. `asyncio.Lock` (`self._lock`)
2. `threading.RLock` (`self._db_lock`) — direkt in `_ensure_loaded`

Beide Wege halten den `asyncio.Lock` zuerst, dann den `threading.RLock`. Konsistent — also **aktuell** kein Deadlock-Risiko.

ABER: Beide Lock-Typen schützen unterschiedliche Ressourcen, was die mentale Modellierung erschwert:
- `asyncio.Lock` schützt `self._queues` (In-Memory-Dict)
- `threading.RLock` schützt `self._conn` (SQLite-Connection)

Diese sind **nicht disjunkt**: `self._queues` wird in `_ensure_loaded` und `_persist_*` gelesen/geschrieben, während der `threading.RLock` gehalten wird. Konkret in `_ensure_loaded` (Zeile 200):
```python
self._queues.setdefault(session_id, []).append(...)  # mutiert _queues unter threading.RLock
```

Wenn ein zukünftiger Maintainer:
- Eine Helper hinzufügt, die `threading.RLock` zuerst nimmt, dann `asyncio.Lock` → Deadlock
- Eine Helper hinzufügt, die `self._queues` aus einem **anderen** Thread mutiert (z.B. Background-Cleanup-Job) → Corruption, da `threading.RLock` die Mutation serialisiert, aber `asyncio.Lock` nicht (asyncio läuft nur im Event-Loop-Thread)

Der Code hat aktuell einen impliziten Vertrag: "asyncio.Lock wird IMMER zuerst genommen, und alle Mutationen auf `self._queues` finden unter asyncio.Lock statt." Das ist nirgends dokumentiert.

**Failure Scenario (hypothetisch):**

Ein neuer Maintainer fügt einen Sync-Cleanup-Helper hinzu:
```python
def sync_cleanup_expired_sessions(self):
    with self._db_lock:  # RLock first!
        expired = ... # query DB
    # jetzt will auf _queues zugreifen
    for sid in expired:
        async with self._lock:  # ← DEADLOCK wenn andere Coroutine asyncio.Lock hält + wartet auf db_lock
            self._queues.pop(sid)
```

Auch wenn aktuell keine solche Helper existiert, ist die Architektur eine Fußkanone.

**Remediation:**

Lock-Order explizit dokumentieren und Helper-Invarianten klar machen:
```python
class InterjectionService:
    """
    Lock ordering (must be respected by ALL helpers):
        1. self._lock     (asyncio.Lock)  — guards self._queues
        2. self._db_lock  (threading.RLock) — guards self._conn + DB schema/migrations

    Invariants:
        * self._queues is only mutated under self._lock
        * self._conn is only used under self._db_lock
        * _persist_* and _ensure_loaded are sync; never call from a thread
          other than the event-loop thread (FastAPI threadpool is OK because
          each request gets its own event loop iteration)
    """
```

Langfristig: Zwei-Klassen-Architektur (`InterjectionQueue` (in-memory, async) + `InterjectionStore` (SQLite, sync/threaded)), die über ein klares Interface kommunizieren. Das macht die Lock-Verantwortung offensichtlich.

**Tradeoff:**

- Doku-Update: trivialer Aufwand, hoher Wert für Future-Maintainer.
- Klassen-Split: größerer Refactor (vermutlich 2-3 h), macht L6-Code lesbarer und testbarer.

---

### F-04 — Best-Effort Write-Through maskiert dauerhafte DB-Fehler als "transient"

**Severity:** MEDIUM
**Confidence:** 0.8
**Files:** `backend/workflow/interjection.py:212-248, 250-272, 274-291`
**Category:** Reliability / Silent Data Loss

**Mechanismus:**

`_persist_insert`, `_persist_mark_consumed`, `_persist_delete_session` schlucken **alle** `sqlite3.DatabaseError` mit `logger.warning(..., exc_info=True)` und kehren still zurück:

```python
def _persist_insert(self, interjection):
    ...
    try:
        conn.execute("INSERT INTO interjections …")
        conn.commit()
    except sqlite3.DatabaseError:
        logger.warning("Failed to persist interjection %s to %s", ..., exc_info=True)
```

Die Methoden sind `def` (sync) und werden aus async-Kontext aufgerufen, aber ihr **Rückgabewert signalisiert keinen Fehler**. Der Caller (z.B. `submit()`) fährt fort, der `interjection_id` wird zurückgegeben, der User bekommt ein 200 OK.

Folge: Wenn die DB dauerhaft kaputt ist (Disk full, Permissions, korrupte Datei), schreibt die App **stillschweigend** in den RAM und verliert beim nächsten Restart alle Daten. Die Logs enthalten "Failed to persist" — wenn niemand Log-Alerts konfiguriert hat, fällt das nicht auf.

**Failure Scenario:**

1. Disk voll (`/var/lib/docker` quota exceeded) — `sqlite3.OperationalError: database or disk is full`.
2. 100 submits kommen in den nächsten 5 min. Jedes wird mit `logger.warning` geloggt, **alle returnen 200**.
3. User klickt "Submit" → sieht grünen Haken.
4. Server restartet (Deploy, OOM).
5. Alle 100 Interjections sind weg. User beschwert sich "ich habe doch geklickt!".

Es gibt keinen Metric-Counter, keinen Health-Check-Endpoint, keinen Alert.

**Zusätzlich:** `_persist_mark_consumed` schlägt fehl → in-memory markiert "consumed", DB noch "pending" → nach Restart sind die "consumed" items zurück im Queue. Workflow würde sie doppelt verarbeiten.

**User/Business Impact:**

- Stiller Datenverlust auf Produktion — kein Signal an Operator.
- Doppel-Verarbeitung nach Restart möglich, wenn `_persist_mark_consumed` fehlschlägt aber in-memory durchläuft.

**Remediation:**

1. **Metric exportieren** (z.B. Prometheus counter `interjection_persist_failures_total`).
2. **Optional:** bei Fehler im `_persist_insert` den `interjection_id` **nicht** zurückgeben und HTTP 503 werfen — der User weiß dann, dass es nicht persistiert ist.
3. **Empfohlen:** Periodische Background-Validation (jede Minute 1× `SELECT count(*)`) um zu prüfen, dass pending-Count in DB und in-Memory-Cache im Rahmen bleiben.
4. **Symmetrie herstellen:** Wenn `_persist_mark_consumed` fehlschlägt, sollte der in-memory Status auf `pending` zurückgesetzt werden (rollback) — sonst divergieren die beiden Welten.

**Tradeoff:**

- Option 1+2 (Fail-Loud): höhere User-Frustration bei transienten Fehlern, aber Operations sieht Probleme sofort.
- Option 1+3 (Background-Validation): bessere UX, mehr Code.
- Aktuell: 0 Sichtbarkeit — schlimmste Option für Operations.

---

### F-05 — `created_at`-Sortierung mit Microsecond-Auflösung ist nicht stabil bei identischem Timestamp

**Severity:** LOW
**Confidence:** 0.6
**Files:** `backend/workflow/interjection.py:180, 238`
**Category:** Correctness / Determinism

**Mechanismus:**

`ORDER BY created_at ASC` in `_ensure_loaded` (Zeile 180). `created_at` wird als `datetime.now(UTC).isoformat()` gesetzt. ISO 8601-Format hat Microsecond-Auflösung (`"2026-06-07T10:23:45.123456+00:00"`), aber:

- SQLite's `datetime('now')` hat nur **Sekunden**-Auflösung. `datetime.now(UTC).isoformat()` in Python hat Microsecond.
- Wenn zwei `submit()`s innerhalb derselben Microsecond aufgerufen werden (bei 4 Workern + Bursts realistisch), ist die `created_at` identisch.
- `ORDER BY created_at ASC` ohne Tie-Breaker → SQLite wählt **Reihenfolge nach Row-Insertion-Order**, was bei `SELECT` nach Restart **undefiniert** ist (RowID kann sich ändern wenn VACUUM läuft).

**Failure Scenario:**

1. Drei submits in der gleichen Microsecond: `inj-aaa`, `inj-bbb`, `inj-ccc`.
2. In-Memory: Reihenfolge ist die Insertion-Order.
3. Process restart.
4. `_ensure_loaded` liest: Reihenfolge könnte `inj-bbb, inj-aaa, inj-ccc` sein.
5. Konsument verarbeitet `inj-bbb` zuerst, obwohl der User es als letztes eingegeben hat.

Wahrscheinlichkeit: Niedrig (Microsecond-Granularität, 12-Hex-UUID unterscheidet sowieso). Aber: bei Last-Spikes (3+ parallele Interjections aus verschiedenen Frontend-Klicks) realistisch.

**User/Business Impact:**

- Reihenfolge der Interjections ist nach Restart **möglichweise** permutiert. Bei menschlichem Text-Inhalt selten semantisch relevant, aber bei strukturierten Metadaten (z.B. "approve this draft" → "actually revise" Reihenfolge) verheerend.

**Remediation:**

Sekundärer Sortierschlüssel hinzufügen:
```python
ORDER BY created_at ASC, interjection_id ASC
```

`interjection_id` ist UUID, also uniform verteilt → stabile deterministische Reihenfolge.

**Tradeoff:**

- 1 Zeile Code, 0 Performance-Impact. Sollte gefixt werden.

---

### F-06 — `clear()` löscht alle Rows der Session, aber `_loaded_sessions` discard + DELETE haben eine Lücke

**Severity:** LOW
**Confidence:** 0.65
**Files:** `backend/workflow/interjection.py:550-569`
**Category:** Correctness / Race Window

**Mechanismus:**

`clear()` macht:
```python
async with self._lock:
    self._queues.pop(session_id, None)
    self._loaded_sessions.discard(session_id)
    self._persist_delete_session(session_id)
# danach:
event = self._wake_events.get(session_id)
if event is not None:
    event.clear()
```

Szenario:
1. Thread T1: `clear("sess-1")` startet. Lock acquired. `self._queues.pop` done. `self._loaded_sessions.discard` done. Ruft `_persist_delete_session("sess-1")` auf → geht in `threading.RLock`.
2. Thread T2: `consume("sess-1")` startet. Wartet auf `asyncio.Lock` (von T1 gehalten).
3. T1: `DELETE FROM interjections WHERE session_id = ?` läuft. Commit.
4. T1: Lock released. Wake-event cleared.
5. T2: Lock acquired. `self._ensure_loaded("sess-1")` → `_loaded_sessions` ist leer für `sess-1` → `SELECT` läuft → keine Rows → returnt leer. `_drain_pending` → keine pending items → returnt leere Liste.

Soweit OK — das ist das erwartete Verhalten nach clear().

**Aber:** zwischen T1 (DELETE-Commit) und T2 (SELECT) könnte ein paralleler `submit("sess-1", ...)` reinlaufen:
- T3: `submit("sess-1", "new input")` startet. Wartet auf `asyncio.Lock`.
- T1 released lock. T2 acquired. T2's `_ensure_loaded` läuft SELECT → keine Rows.
- T2 released lock. T3 acquired. T3's `_ensure_loaded` läuft SELECT → keine Rows (T1 hat gelöscht, T3 ist neu). T3 schreibt in `_queues` und INSERT in DB.
- T2 released lock. T3 released lock. → T3's "new input" ist da.

In dieser Sequenz ist die Reihenfolge konsistent — T2 sieht "leer nach clear", T3 sieht "leer + schreibt neu". Alles OK.

**Edge Case:**

1. T1: `clear()` läuft. Acquired `asyncio.Lock`. `self._queues.pop` done. `self._loaded_sessions.discard` done.
2. T3: `submit("sess-1", "new")` wartet auf `asyncio.Lock`.
3. T1: `_persist_delete_session` macht DELETE.
4. T1: released `asyncio.Lock`. **Aber:** der `event.clear()`-Block läuft erst **nach** dem `async with` (Zeile 565-568):
   ```python
   async with self._lock:
       ...
   # Hier ist Lock released
   event = self._wake_events.get(session_id)
   if event is not None:
       event.clear()
   ```
5. T3: erwirbt `asyncio.Lock`. `self._ensure_loaded("sess-1")` → `_loaded_sessions` discarded → SELECT. T1 hat gelöscht → keine Rows. T3: `_queues.setdefault("sess-1", []).append(interjection)`. T3: `self._get_wake_event("sess-1").set()`. T3: `_persist_insert` schreibt.
6. T3: released `asyncio.Lock`.
7. T1 (jetzt nach `async with`): `event = self._wake_events.get("sess-1")` → der Event, den T3 gerade gesetzt hat! `event.clear()` — **löscht T3's Wake-Signal!**

Wenn zwischen T3's set() und T1's clear() ein Consumer wartet: der Consumer wacht auf (event war "set" durch T3), drainiert T3's Item. OK.

Wenn der Consumer erst nach T1's clear() ankommt: event ist "clear", consumer schläft. T3's Item wartet im `_queues`, aber niemand weckt den consumer → bis zum nächsten submit.

Das ist **kein Datenverlust** (T3's Item ist in `_queues` und DB), aber **verzögerte Abarbeitung** — bis zu 5 min (Timeout von `consume_blocking`).

**User/Business Impact:**

- Sehr unwahrscheinlich (Race-Window ist Mikrosekunden, T1 ist single-threaded async).
- Falls auftritt: User wartet bis zur nächsten Interaktion.
- Kein Datenverlust.

**Remediation:**

`event.clear()` **innerhalb** des `async with self._lock` verschieben:
```python
async def clear(self, session_id):
    async with self._lock:
        self._queues.pop(session_id, None)
        self._loaded_sessions.discard(session_id)
        self._persist_delete_session(session_id)
        # Wake event reset BEFORE releasing the lock to prevent
        # racing with a concurrent submit on the same session id.
        event = self._wake_events.get(session_id)
        if event is not None:
            event.clear()
    logger.info("Cleared interjection queue for session %s", session_id)
```

**Tradeoff:**

- 4 Zeilen-Umstrukturierung, klare Invariante "alle State-Mutationen unter dem Lock".
- Sollte gefixt werden — triviale Komplexität, klare Semantik-Verbesserung.

---

### F-07 — `metadata` wird als `json.dumps` ohne Sanitization persistiert — beliebige Python-Objekte möglich

**Severity:** LOW
**Confidence:** 0.7
**Files:** `backend/workflow/interjection.py:60, 236, 195, 198-199`
**Category:** Security / Input Validation (low)

**Mechanismus:**

`Interjection.metadata: dict[str, Any]` — der Type-Hint sagt `dict`, aber zur Laufzeit kann alles drin sein, was der Caller übergibt. Die Persistenz serialisiert mit `json.dumps(interjection.metadata or {})` ohne Re-Validierung.

In `agent_nodes.py:243` (Aufrufer):
```python
service_injs = await interjection_service.consume(session_id, node_id)
interjection_queue.extend(service_injs)
# → service_injs[i]["metadata"] ist das vom Caller übergebene dict
```

In `hitl/api.py:374` (Caller):
```python
await interjection_service.submit(
    session_id=session_id,
    content=body.content,
    source="hitl",
    metadata={
        "interaction_id": interaction_id,
        "debate_id": debate_id,
        "target_agent": body.target_agent,
        "priority": body.priority,
    },
)
```

`body.target_agent` und `body.priority` stammen aus Pydantic-Validierung (Request-Body) → sollten Strings sein. `body.metadata` aus `workflow_exec.py:798`:
```python
interjection_id = await interjection_service.submit(
    session_id=session_id,
    content=body.content,
    source=body.source,
    metadata=body.metadata,  # ← was ist das für ein Typ?
)
```

**Mögliche Probleme:**

1. Wenn `body.metadata` ein nicht-dict-Wert ist (z.B. eine Liste), wird `interjection.metadata or {}` Truthiness-test → die Liste ist truthy → `interjection.metadata = body.metadata` (Liste statt dict). `json.dumps` einer Liste funktioniert. Nach `_ensure_loaded`: `json.loads(row["metadata"])` → Liste. Zeile 198-199: `if not isinstance(metadata, dict): metadata = {}` — gefixt, gut.
2. Wenn `body.metadata` zirkuläre Referenzen hat → `json.dumps` raised `ValueError: Circular reference detected`. Aktuell **uncaught** in `_persist_insert` — würde `sqlite3.DatabaseError` werden? Nein, `json.dumps` raised `ValueError` (kein `DatabaseError`). Der `except sqlite3.DatabaseError` fängt das **nicht** → ValueError propagiert hoch → in `_persist_insert` kein Caller-Handler → propagiert weiter in `submit()` → dort ist auch kein `try/except` → 500 Error an Caller.

**Failure Scenario:**

```python
# Malicious or buggy client sends:
{"metadata": {"ref": some_obj_with_circular_ref}}
# OR
{"metadata": "a string instead of dict"}  # Pydantic erlaubt dies möglicherweise
```

Erstes Szenario: 500 Error, User sieht "Internal Server Error", Datenverlust (in-memory hat's genommen, DB hat's nicht).
Zweites Szenario: 200 OK, aber DB hat String serialisiert, beim Re-Load: `not isinstance(metadata, dict)` triggert `metadata = {}` — Datenverlust.

**User/Business Impact:**

- Niedrig: 500-Errors bei echten Bugs in Caller, Datenverlust bei ungewöhnlichen Input-Shapes.
- Kein Security-Exploit, eher Robustness.

**Remediation:**

1. Pydantic-Validierung auf Caller-Seite verschärfen: `metadata: dict[str, Any]` in `BodyInterjection`.
2. In `submit()` defensiv:
   ```python
   if not isinstance(interjection.metadata, dict):
       interjection.metadata = {}
   ```
3. In `_persist_insert` `json.dumps` Fehler abfangen:
   ```python
   try:
       meta_json = json.dumps(interjection.metadata or {})
   except (TypeError, ValueError):
       meta_json = "{}"
       logger.warning("Failed to serialize metadata for interjection %s", ...)
   ```

**Tradeoff:**

- 5 Zeilen Code, klar robuster.
- Sollte gefixt werden — defensive Programmierung an einer I/O-Grenze.

---

### F-08 — M3 Topo-Sort: Decision-Edges mit Self-Loop-Überspringung kann semantische Ordnung verlieren

**Severity:** LOW
**Confidence:** 0.55
**Files:** `backend/workflow/workflow_compiler.py:484-505, 528-531`
**Category:** Correctness / Topological Sort Edge Case

**Mechanismus:**

Sprint 41 (M3 fix) hat Decision-Edges in den Topo-Sort aufgenommen. Self-Loops werden explizit übersprungen:

```python
if edge.source == edge.target:
    # Self-loop (e.g. decision edge that loops back
    # to the same node on a particular condition).
    # Not a sequencing constraint.
    continue
```

Das ist semantisch korrekt — ein Self-Loop auf einem Decision-Node (z.B. "wenn revision_required, gehe zu Moderator") ist keine Sequenz-Constraint, sondern eine Laufzeit-Bedingung.

**ABER:** Was ist mit Decision-Edges, die einen Zyklus bilden?

Beispiel:
- Moderator (M) → Builder (B) via decision "approved"
- Builder (B) → Moderator (M) via decision "needs_more_review"

Self-Loop-Überspringung greift nicht (source ≠ target), beide Edges werden aufgenommen:
```python
adj["M"] = ["B"]
adj["B"] = ["M"]
in_degree = {"M": 1, "B": 1}
```

Kahn's Algorithmus: Queue leer → result = []. Dann Fallback:
```python
for nid in node_ids:
    if nid not in result:
        result.append(nid)  # ← fügt unreached nodes an
```

→ Result = ["M", "B"] (in node-iteration-Order, nicht topo).

**Failure Scenario:**

1. Workflow-Designer baut zyklischen Decision-Loop: M→B, B→M.
2. Static `node_sequence` = ["M", "B"] (ungeordnet).
3. Inspector / observability tools zeigen die falsche Reihenfolge.
4. Compile schlägt nicht fehl, kein Warning.

Wahrscheinlichkeit: Niedrig (Designer mit Absicht müsste diesen Loop bauen). Aber: das ist genau die Situation, in der Topo-Sort normalerweise fehlschlagen sollte, um den Designer zu warnen. Aktuell wird der Cycle stillschweigend akzeptiert.

**User/Business Impact:**

- `node_sequence` ist nur für statische Analyse (Inspector, Logs). Laufzeit-Graph ist OK.
- Kein Datenverlust, nur schlechte Observability.

**Remediation:**

Im Compile-Result Warning emittieren, wenn die Fallback-Pfad benutzt wurde (mindestens ein Node ist unreached):
```python
if len(result) < len(node_ids):
    undecided = [nid for nid in node_ids if nid not in result]
    warnings.append(
        f"Topological sort: {len(undecided)} node(s) not reached by Kahn's algorithm "
        f"due to decision-edge cycles: {undecided}. Falling back to insertion order."
    )
```

**Tradeoff:**

- 5 Zeilen, besserer Signalwert für Workflow-Designer.
- Niedrige Priorität, aber operativ sinnvoll.

---

### F-09 — L5 `registerWorkflowNodes.js` ROLE_TYPES: 18 Iterationen mit Strings — kein TypeScript-Constraint

**Severity:** LOW
**Confidence:** 0.5
**Files:** `frontend/src/lib/blueprint/registerWorkflowNodes.js:129-189`
**Category:** Maintainability / Type Safety

**Mechanismus:**

Die Refactoring-Lösung L5 hat 18 Agent-Rollen aus 18 expliziten `registerNode({...})` Aufrufen in einen Array `ROLE_TYPES` und einen Loop konsolidiert. Pro Eintrag: `[type, icon, labelKey, label, component]`. 5 Felder pro Eintrag, 18 Einträge.

```js
const ROLE_TYPES = [
    ['wf-strategist', '🧠', 'wfStrategist', 'Strategist', StrategistNode],
    ['wf-critic', '🔍', 'wfCritic', 'Critic', CriticNode],
    ...
];

for (const [type, icon, labelKey, label, component] of ROLE_TYPES) {
    registerNode({...});
}
```

Da `registerWorkflowNodes.js` **kein** `.ts` ist (plain JS), gibt es keine Compile-Time-Prüfung:
- Falsche Reihenfolge: `[type, icon, labelKey, label, component]` vs `[type, label, labelKey, ...]` — der Loop destrukturiert stumm, Felder sind `undefined`, `registerNode` läuft mit kaputten Defaults.
- Fehlender Eintrag: `StrategistNode` importiert, aber nicht in `ROLE_TYPES` — keine Compile-Warnung, zur Laufzeit fehlt der Node-Type im Registry.
- Falsche Anzahl: `[a, b, c]` statt 5-Tuple — `component = undefined`, runtime crash beim ersten Render.

**Failure Scenario:**

1. Designer fügt neue Rolle hinzu: importiert `MyNewAgentNode`, fügt Tuple in `ROLE_TYPES` ein.
2. Vergisst das `,` am Ende des vorherigen Tupels → Array-Format kaputt.
3. JS-Engine parst `['wf-troll', '🤡', 'wfTroll', 'Troll', TrollNode]['wf-mediator', ...]` → kaputt.
4. `registerWorkflowNodes()` wirft im Frontend → Blueprint-Canvas lädt nicht, aber Compile / Build sind grün.

**User/Business Impact:**

- Frontend-Build OK, Runtime-Crash beim Canvas-Render.
- Wird in CI nicht gefangen.

**Remediation:**

Option 1 — `.ts` + Interfaces:
```ts
type RoleEntry = [type: string, icon: string, labelKey: string, label: string, component: ComponentType];
const ROLE_TYPES: RoleEntry[] = [...]
```

Option 2 — Object-Format statt Tuple:
```js
const ROLE_TYPES = [
  { type: 'wf-strategist', icon: '🧠', labelKey: 'wfStrategist', label: 'Strategist', component: StrategistNode },
  ...
];
ROLE_TYPES.forEach(({ type, icon, labelKey, label, component }) => registerNode({...}));
```

Option 3 — Runtime-Check:
```js
for (const entry of ROLE_TYPES) {
  if (entry.length !== 5) throw new Error(`ROLE_TYPES entry malformed: ${entry}`);
  const [type, icon, labelKey, label, component] = entry;
  ...
}
```

**Tradeoff:**

- Option 1: beste Lösung, aber Refactor von JS → TS ist großes Projekt.
- Option 2: gute Lesbarkeit, Field-Namen selbsterklärend, 0 TypeScript-Aufwand.
- Option 3: minimal-invasiv, günstige Absicherung.

---

### F-10 — M11 Extension-Zone: Off-by-One-Risiko an `max_rounds + 2`-Grenze

**Severity:** LOW
**Confidence:** 0.45
**Files:** `backend/workflow/workflow_routers.py:288-312`
**Category:** Correctness / Boundary Condition

**Mechanismus:**

`route_decision` und `route_feedback` (Zeile 188) erlauben Extension bis `max_rounds + 2`. Aber:

```python
# route_decision:288-312
if current_round > effective_max:
    enable_extra = state.get("enable_extra_rounds", False)
    extension_granted = state.get("extension_granted") is True
    in_extension_zone = current_round <= effective_max + 2
    if enable_extra and extension_granted and in_extension_zone:
        # ... continue
    else:
        return "construction_deadlock"
```

`current_round > effective_max` und `current_round <= effective_max + 2` — das deckt `effective_max + 1` und `effective_max + 2` ab. Genau 2 zusätzliche Runden. OK.

**ABER:** der `route_feedback` (Zeile 188) macht:
```python
if enable_extra and current_round <= max_rounds + 2:
    extension_granted = state.get("extension_granted")
    if extension_granted is True:
        # continue
```

Hier fehlt der "current_round > max_rounds" Check. Das heißt: `route_feedback` erlaubt Extension bereits ab `current_round == 1` (wenn `enable_extra and extension_granted`). `current_round == 1` ist NICHT in der Extension-Zone (es ist regulär), aber der Code erlaubt es durch.

**Ist das ein Bug?**

Kommt drauf an. In `route_feedback`:
- `if current_round <= max_rounds:` → continue (default path)
- `if enable_extra and current_round <= max_rounds + 2:` → check extension_granted → continue

Die zwei Branches sind **nicht** exklusiv. Wenn `current_round == 1` und `enable_extra=True` und `extension_granted=True` und `current_round <= max_rounds` → erste Branch triggert, continue, OK. Die zweite Branch wird gar nicht erreicht.

Wenn `current_round == 1` und `enable_extra=True` und `extension_granted=True` und `current_round > max_rounds` (also `max_rounds == 0` oder ähnlich)? Würde zweite Branch triggern, continue — das ist **gewollt** (Extension).

Was wenn `max_rounds == 0` (Edge Case) und `current_round == 1`? `current_round > max_rounds` → True. `current_round <= max_rounds + 2` → True. → continue. → **Loop**! Bei `max_rounds == 0` würde der Workflow endlos weiterlaufen.

`max_rounds == 0` ist ein absurder Wert (Workflow mit 0 Runden = sofort terminieren?), aber:
- Settings default: `default_max_rounds: int = 3`
- `route_decision` default: `max_rounds: int = 5`
- Falls jemand `max_rounds=0` setzt → endloser Loop in `route_feedback`.

**Auch in `route_decision`:** der gleiche Check `current_round > effective_max` ist OK, aber `effective_max` ist `max_rounds or state.get("max_rounds", 5)`. Wenn `max_rounds=False` und state `max_rounds=0` → `effective_max = 0 or 0 = 0`. → `current_round > 0` → True ab Runde 1.

**Failure Scenario:**

1. Workflow mit `max_rounds=0` (Bug in Template-Config, oder explizit gesetzt für "sofort fertig").
2. Runde 1 startet, `current_round=1`, `current_round > 0` → True.
3. Extension-Zone-Check: `1 <= 0 + 2` → True, `extension_granted=True` (per default? oder per UI?), `enable_extra=True` → continue.
4. Runde 2, 3, … endlos.

Wahrscheinlichkeit: Sehr niedrig. Aber: das M11-Fix-Szenario war genau "User gewährt Extension → Decision-Router sollte das honorieren" — und der Fix hat exakt dieses Pattern an 2 Stellen kopiert. Wenn beide Stellen die gleiche Edge-Case-Schwäche haben, ist die Wahrscheinlichkeit nicht 0.

**User/Business Impact:**

- Endlos-Loop in `route_feedback` bei `max_rounds=0` + `extension_granted=True`. CPU + Memory.
- Detection: SSE-Stream zeigt endlos "debate round X" Events. Operator-Eingriff nötig.

**Remediation:**

1. Validierung in Workflow-Config: `max_rounds` muss `>= 1` sein.
2. In `route_feedback`: explizit prüfen `current_round > max_rounds` vor Extension-Branch.
3. Oder: Extension-Branch nur, wenn `current_round > max_rounds` UND `current_round <= max_rounds + 2`.

**Tradeoff:**

- 1-2 Zeilen Code in `route_feedback`, klar defensive.
- Sehr niedrige Priorität, weil `max_rounds=0` ein ungewöhnlicher Config ist.

---

## 3. Positive Beobachtungen

- **L6 Design-Entscheidung "DB als source of truth, in-memory als cache"** ist solide. Lazy Hydration via `_loaded_sessions` Set verhindert N+1-Queries.
- **L6 Tests (14 neue)** decken die kritischen Szenarien ab: Restart-Resilienz, Multi-Session-Isolation, JSON-Metadata-Roundtrip, Singleton-Konfiguration. Das ist eine gute Test-Matrix.
- **M10 Connection-Reuse-Pattern** (lazy + RLock + WAL) ist bewährt, korrekt implementiert, gut getestet. Spart den `sqlite3.connect`-Overhead pro Operation.
- **L5 RegisterAll-Split** reduziert 568 Zeilen auf 361, klar modularisiert. Idempotenz (L5 Test `test_idempotent_reregistration`) verhindert Doppel-Register-Race.
- **M3 Decision-Edges in Topo-Sort** ist semantisch korrekt für statische Analyse. Self-Loop-Skip ist explizit dokumentiert.
- **M11 Extension-Zone** ist eine echte Funktionalitäts-Erweiterung, die einen realen Bug fixt (Decision-Router ignorierte User-Extension-Grant).
- **L4 Identity-Map-Removal**: 28 redundante Key-Value-Paare entfernt, vereinfacht ohne Verhaltensänderung.

---

## 4. Architektonische Beobachtungen (Soft Recommendations)

### 4.1 Lock-Typ-Konfusion in `InterjectionService`

Die Klasse mischt `asyncio.Lock` (coroutine-isolation) und `threading.RLock` (thread-isolation) ohne klare Verantwortungs-Trennung. Empfehlung: Zwei Klassen mit klarer API (`InterjectionQueue` async + `InterjectionStore` sync/threaded), kommuniziert über ein definiertes Interface. Verbessert Testbarkeit (Queue allein ohne DB testbar) und mentale Modellierung.

### 4.2 SQLite für "fast queue" ist Overkill für L6

L6 will Restart-Resilienz — SQLite ist eine valide Wahl. ABER: jede `submit()` triggert `fsync` (mit `synchronous=NORMAL` asynchron, mit `FULL` synchron). Bei Network-Storage (EBS, NFS) kann das 10+ ms blockieren. Alternative: `aiosqlite` für echte async I/O, oder Append-Only-Log-File mit `O_APPEND` (sub-Microsecond pro Write).

### 4.3 In-Memory-Cache ist redundant mit DB als Source of Truth

Aktuell: in-memory `_queues` + DB `interjections` Tabelle. Beide werden synchron gehalten. **Warum nicht nur DB?** `consume_blocking` könnte `SELECT … WHERE session_id = ? AND status = 'pending'` periodisch machen, Wake-Event durch Notification-Mechanismus (z.B. SQLite-Trigger + Pub/Sub). Spart die Caching-Komplexität, macht Restart-Resilienz trivial. Tradeoff: DB-Last steigt, aber bei 100 submits/s bleibt das im einstelligen ms-Bereich.

### 4.4 `audit_logger` und `state_snapshot` teilen sich `data/blueprints.db` — aber kein Schema-Migrations-System

Drei Module (audit, snapshot, interjection) schreiben in dieselbe DB-Datei, jede mit eigener `CREATE TABLE IF NOT EXISTS`. Keine zentrale Schema-Version, kein Migrations-Tool. Bei Schema-Änderungen (z.B. Spalte hinzufügen) muss jeder Caller manuell migrieren. Empfehlung: Alembic oder zentraler Schema-Initializer mit Version-Tabelle.

---

## 5. Test-Coverage-Bewertung

| Bereich | Coverage | Bewertung |
|---------|----------|-----------|
| `interjection_service` happy path | ✅ Hoch (24 Tests, alle grün) | Solide |
| `interjection_service` Persistence | ✅ Hoch (14 Tests) | Solide, deckt Restart ab |
| `interjection_service` Concurrency | ⚠️ Niedrig | Race-Bugs (F-06) nicht getestet |
| `interjection_service` Failure-Modes | ❌ Keine | F-04 (DB-Fehler) nicht getestet |
| `route_decision` extension | ✅ Hoch (7 Tests Sprint 42) | Solide |
| `route_feedback` extension | ⚠️ Mittel | F-10 (max_rounds=0) nicht getestet |
| `_topological_sort` cycles | ⚠️ Mittel | Fallback-Pfad (F-08) nicht gewarnt |
| `registerWorkflowNodes` ROLE_TYPES | ⚠️ Niedrig | F-09 (Tuple-Format) nicht getestet |
| `audit_logger` connection reuse | ✅ Hoch (10 Tests Sprint 43) | Solide |
| `state_snapshot` connection reuse | ✅ Hoch (Test-Suite) | Solide |

**Lücke:** Kein Test fängt "DB write fail" als Scenario. F-04 würde durch einen Test mit `monkeypatch.setattr(conn, 'execute', mock_that_raises)` auffallen.

---

## 6. Empfohlene Priorisierung

| Prio | Finding | Aufwand | Impact |
|------|---------|---------|--------|
| 1 | F-01 (Multi-Worker Wake-Up) | 2-4 h | User-UX in Produktion, hoher Wiederherstellungs-Wert |
| 2 | F-02 (Sync I/O im asyncio.Lock) | 1-2 h | Skalierung, P99-Latenz, Worker-Stabilität |
| 3 | F-04 (Silent Data Loss) | 1-2 h | Operations-Sichtbarkeit, Reliability |
| 4 | F-06 (clear()-Race) | 15 min | Trivial, klarer Bug |
| 5 | F-05 (Sort-Stabilität) | 1 min | Trivial, deterministisch |
| 6 | F-07 (Metadata-Sanitization) | 15 min | Robustheit |
| 7 | F-03 (Lock-Order-Doku) | 30 min | Future-Maintainability |
| 8 | F-09 (Type-Safety) | 30 min (Object-Literal) | Runtime-Safety |
| 9 | F-08 (Cycle-Warning) | 10 min | Designer-Feedback |
| 10 | F-10 (max_rounds=0 Edge) | 5 min | Edge-Case-Hardening |

---

## 7. Unsicherheiten & offene Fragen

- **Wer ruft `close()` auf der `interjection_service`-Singleton auf?** Im `interjection.py` ist `close()` definiert, aber kein Caller im Production-Code. Bei Graceful-Shutdown würde die DB-Connection leaken — wenn auch nur einmal pro Worker-Restart, also kein akuter Bug.
- **Wird `data/blueprints.db` zwischen `audit_logger`, `state_snapshot` und `interjection` über Concurrency-Mechanismen koordiniert?** Aktuell: jede Instanz hat eigene `sqlite3.Connection`, WAL-Modus erlaubt parallele Reader + einen Writer. Schreibt z.B. `audit_logger` zur gleichen Zeit wie `interjection_service`, gibt es einen Writer-Lock-Contention. Bei 4 Workern: 4 Connections, alle schreiben — der SQLite-WAL-Mode handhabt das, aber mit Wartezeit. Nicht gemessen.
- **Was passiert mit dem `wake_events`-Dict bei Memory-Pressure?** Asyncio-Events werden bei `_clear()` (in `clear()`) nicht aus dem Dict entfernt. Über lange Zeit sammeln sich Events für beendete Sessions. Kein Leak im normalen Betrieb, aber bei Millionen von kurzen Sessions wäre der Dict groß. Aktuell kein Problem.
- **`interjection_id` als `f"inj-{uuid4().hex[:12]}"`** — 12 Hex-Zeichen = 48 Bit = ~281 Billionen. Birthday-Paradox: 50% Kollision bei ~16 Millionen Interjections pro Session-ID. In der Praxis: irrelevant (selbst bei 10k Interjections/s dauert es 30 Jahre bis zur 50% Kollision). Aber: technisch nicht garantiert kollisionsfrei. `AUTOINCREMENT` PK wäre strenger, aber UUID ist OK.

---

**Report Ende.** Konkrete Fixes für F-01, F-02, F-04 sollten vor dem nächsten Production-Deployment angegangen werden. F-06, F-05, F-07 sind Low-Hanging-Fruit und können in den laufenden Sprint gezogen werden.
