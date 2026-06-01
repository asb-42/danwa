# Plan: Kitsune Agent — Tool-Calling für den Danwa-Assistenten

**Datum:** 2026-05-23
**Branch:** `kitsune-agent`
**Basis:** `main` (3abdab7)

## Überblick

Kitsune ist aktuell ein reiner Q&A-Chatbot: System-Prompt + Chat-Verlauf → LLM → Text-Antwort.
Er hat explizit keine Aktionen: "You cannot start debates or upload documents", "You have no access to existing debates or projects".
Ziel ist es, Kitsune Schritt für Schritt zu einem Agenten mit Tool-Zugriff auszubauen.

## Architektur-Entscheidungen

### Kommunikationsprotokoll
- **OpenAI Function Calling** als Tool-Protokoll (wird von litellm und den meisten lokalen LLMs unterstützt)
- Tool-Definitionen als JSON-Schema-Array im `tools`-Parameter von `acompletion()`
- Response enthält entweder `content` (Text-Antwort) oder `tool_calls` (auszuführende Tools)

### Tool-Registry
- Zentrale Registry: `backend/services/assistant_tools.py`
- Jedes Tool ist eine Klasse/Funktion mit: `name`, `description`, `parameters` (JSON-Schema), `execute()`
- Tools sind **stateless** und **idempotent** — erhalten alle nötigen Parameter, geben strukturierte Ergebnisse zurück

### Sicherheit
- **Phase 1: Nur Read-Operations** — keine Änderungen am System
- **Phase 2: Write-Operations mit explizitem User-OK** — Kitsune fragt "Soll ich X tun? (Ja/Nein)"
- **Phase 3: Vertrauenswürdige Write-Operations** — nach Bestätigung durch User

---

## Phase 1: Read-Only Tools (dieser Branch)

### 1.1 LLMService: Tool-Unterstützung

**Datei:** `backend/services/llm_service.py`

#### `generate()`-Signatur erweitern:

```python
async def generate(
    self,
    prompt: str,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict] | None = None,          # NEU
) -> GenerationResult:
```

#### `GenerationResult` erweitern:

```python
@dataclass
class GenerationResult:
    content: str | None
    tool_calls: list[dict] | None = None      # NEU
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    model: str = ""
```

#### `_generate_litellm()`: Tools-Parameter übergeben

In Zeile 301 (kwargs-Dict) nach `max_tokens`:

```python
if tools:
    kwargs["tools"] = tools
```

#### `_generate_local()`: Tools-Parameter übergeben

Analog — `tools` in den JSON-Body des lokalen HTTP-Clients einfügen.

#### Response-Parsing: `tool_calls` auslesen

Nach `response.choices[0].message` (ca. Zeile 324):

```python
message = response.choices[0].message
content = message.content

# NEU: tool_calls aus der Response extrahieren
tool_calls_raw = getattr(message, "tool_calls", None)
tool_calls = None
if tool_calls_raw:
    tool_calls = []
    for tc in tool_calls_raw:
        tool_calls.append({
            "id": tc.id,
            "type": tc.type,
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        })
```

#### Rückgabe:

```python
return GenerationResult(
    content=content,
    tool_calls=tool_calls,              # NEU
    tokens_in=tokens_in,
    tokens_out=tokens_out,
    duration_ms=duration_ms,
    model=model_name,
)
```

---

### 1.2 AssistantService: Tool-Registry + Execution

**Neue Datei:** `backend/services/assistant_tools.py`

```python
"""Tool definitions for Kitsune agent."""

import json
from typing import Any

from backend.api.deps import get_project_store  # oder direkte Service-Imports

# ─── Registry ───────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict[str, Any]] = {}

def tool(name: str, description: str, parameters: dict) -> callable:
    """Decorator to register a tool."""
    def decorator(func):
        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "fn": func,
        }
        return func
    return decorator

def get_tool_definitions() -> list[dict]:
    """Return all tool definitions as OpenAI-compatible function objects."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_REGISTRY.values()
    ]

async def execute_tool(name: str, arguments: str, **ctx) -> str:
    """Execute a tool by name with parsed arguments. Returns string result."""
    if name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        args = json.loads(arguments)
        result = await TOOL_REGISTRY[name]["fn"](**args, **ctx)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
```

#### Tool: `get_system_status`

```python
@tool(
    name="get_system_status",
    description="Get current system status: active sessions, LLM profiles, module count, active debates",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def get_system_status(**ctx) -> dict:
    """Return a summary of system status."""
    assistant = ctx["assistant_service"]
    sessions = assistant.list_sessions()
    # Über profile_service, debate_store usw.
    return {
        "active_sessions": len(sessions),
        "llm_profiles_count": "...",
        "modules_count": "...",
        "active_debates_count": "...",
    }
```

#### Tool: `list_debates`

```python
@tool(
    name="list_debates",
    description="List all debates with their status, topic, and round count",
    parameters={
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Optional project ID to filter by",
            },
            "status": {
                "type": "string",
                "enum": ["running", "completed", "all"],
                "description": "Filter by debate status",
            },
        },
        "required": [],
    },
)
async def list_debates(project_id: str = None, status: str = "all", **ctx) -> list[dict]:
    """Return a list of debates."""
    # Zugriff auf debate_store und project_store
    ...
```

#### Tool: `get_llm_profiles`

```python
@tool(
    name="get_llm_profiles",
    description="List all configured LLM profiles with their provider, model, and status",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def get_llm_profiles(**ctx) -> list[dict]:
    """Return all LLM profiles."""
    repo = ctx["blueprint_repository"]
    profiles = repo.list_llm_profiles()
    return [
        {"id": p.id, "name": p.name, "provider": p.provider, "model": p.model,
         "service_eligible": p.service_eligible}
        for p in profiles
    ]
```

#### Tool: `get_debate_details`

```python
@tool(
    name="get_debate_details",
    description="Get detailed information about a specific debate including rounds and consensus",
    parameters={
        "type": "object",
        "properties": {
            "debate_id": {
                "type": "string",
                "description": "The debate ID to get details for",
            },
        },
        "required": ["debate_id"],
    },
)
async def get_debate_details(debate_id: str, **ctx) -> dict:
    """Return debate details."""
    ...
```

#### Tool: `get_modules`

```python
@tool(
    name="get_modules",
    description="List installed modules, optionally filtered by category",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Optional category to filter by (llm-profiles, agents, prompts, workflows, translations)",
            },
        },
        "required": [],
    },
)
async def get_modules(category: str = None, **ctx) -> list[dict]:
    """Return list of installed modules."""
    ...
```

#### Tool: `search_knowledge_base`

```python
@tool(
    name="search_knowledge_base",
    description="Search the Danwa documentation and codebase knowledge base for information",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
        },
        "required": ["query"],
    },
)
async def search_knowledge_base(query: str, **ctx) -> str:
    """Search in the knowledge base for relevant information."""
    # Volltext-Suche in der knowledge.txt / Dokumentation
    ...
```

---

### 1.3 AssistantService: Tool-Execution-Loop

**Datei:** `backend/services/assistant_service.py`

#### Neue Imports:

```python
from backend.services.assistant_tools import get_tool_definitions, execute_tool, TOOL_REGISTRY
```

#### `send_message()` ändern (ca. Zeile 346-403):

```python
async def send_message(self, session_id, user_message, profile_id=None):
    """Send a message and optionally execute tool calls."""

    # ... bestehende Session/Auth-Logik ...
    session = self._sessions.get(session_id)
    session.add_message("user", user_message)

    selected_profile = self._select_llm_profile(llm_profile_id)

    # NEU: Tool-Definitionen laden
    tool_defs = get_tool_definitions()
    has_tools = len(tool_defs) > 0

    # NEU: Tool-Execution-Loop (max 5 Iterationen)
    max_iterations = 5
    for iteration in range(max_iterations):
        # Build messages
        _messages = [
            {"role": "system", "content": self.system_prompt},
            *session.get_history(max_messages=self._max_messages - 1),
        ]

        llm_service = LLMService(...)
        result = await llm_service.generate(
            prompt=user_message if iteration == 0 else "",  # Nur beim 1. Mal
            system_prompt=self.system_prompt,
            temperature=0.7,
            max_tokens=2000,
            tools=tool_defs if has_tools else None,   # NEU
        )

        if result.tool_calls:
            # Tools ausführen
            for tc in result.tool_calls:
                fn_name = tc["function"]["name"]
                fn_args = tc["function"]["arguments"]
                ctx = {
                    "assistant_service": self,
                    "profile_service": self._profile_service,
                    "blueprint_repository": self._get_repo(),
                    "debate_store": self._get_debate_store(),
                    "project_store": self._get_project_store(),
                }
                tool_result = await execute_tool(fn_name, fn_args, **ctx)
                # Tool-Result als Message einfügen
                session.add_message("tool", json.dumps({
                    "tool_call_id": tc["id"],
                    "tool_name": fn_name,
                    "result": tool_result,
                }))
            user_message = ""  # Nächste Iteration ohne neuen User-Prompt
        else:
            # Text-Antwort — an den User ausliefern
            assistant_msg = session.add_message(
                "assistant",
                result.content,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                model=result.model,
            )
            return assistant_msg

    # Nach max_iterations: Fallback
    fallback_msg = session.add_message(
        "assistant",
        "Entschuldigung, die Anfrage konnte nicht vollständig bearbeitet werden. Bitte versuche es erneut.",
    )
    return fallback_msg
```

---

### 1.4 System-Prompt aktualisieren

**Datei:** `config/prompts/kitsune/kitsune.md`

#### Zeilen 43-49 ersetzen (Boundaries):

```markdown
## Your capabilities

You have access to tools that let you interact with Danwa:

- **get_system_status** — Get current system status
- **list_debates** — List debates with status
- **get_debate_details** — Get detailed information about a specific debate
- **get_llm_profiles** — List configured LLM profiles
- **get_modules** — List installed modules by category
- **search_knowledge_base** — Search in documentation

Use these tools when users ask about their debates, profiles, modules, or system status.
You currently have read-only access. You cannot start debates, change settings, or modify data.
You have a **Reference: Codebase Knowledge Base** section appended to this prompt — use it
for technical questions about API endpoints, configuration, and architecture.
```

---

### 1.5 Frontend: Tool-Execution im Chat anzeigen

**Datei:** `frontend/src/components/AssistantChat.svelte`

#### Neue Message-Render-Logik (ca. Zeile 170):

```svelte
{#each messages as msg}
  {#if msg.role === 'assistant'}
    <!-- Bestehende Markdown-Render-Logik -->
  {:else if msg.role === 'tool'}
    <div class="tool-call">
      <span class="tool-icon">🔧</span>
      <span class="tool-name">{msg.tool_name || 'Tool'}</span>
      {#if msg.tool_name === 'list_debates'}
        <!-- Tabelle der Debatten anzeigen -->
      {:else}
        <pre>{msg.content}</pre>
      {/if}
    </div>
  {/if}
{/each}
```

#### API-Response erweitern (Message-Format):

```javascript
// Bisher:
{ role: 'assistant', content: '...' }

// Neu — auch möglich:
{ role: 'assistant', content: '...', tool_calls: [...] }
{ role: 'tool', content: '{...}', tool_call_id: '...', tool_name: '...' }
```

**Anpassung in `sendAssistantMessage()`** (api.js, Zeile 955):

Keine Änderung nötig, solange die API weiterhin eine einheitliche Message-Liste zurückgibt.
Alternativ: Nachricht-für-Nachricht-Streaming (siehe Phase 4 unten).

---

### 1.6 API-Response-Format erweitern

**Datei:** `backend/api/routers/assistant.py`, Zeile 128 (`send_message`)

Die Response enthielt bisher nur `{role, content, timestamp, tokens_in, tokens_out, model}`.
Neu kommen Tool-Call-Nachrichten dazu. Das Format bleibt konsistent — der Frontend-Chat
bekommt die gesamte Message-History inklusive Tool-Calls.

Der `/chat`-Endpunkt gibt weiterhin die letzte Assistant-Message zurück. Der Frontend-Client
ruft dann `GET /api/v1/assistant/sessions/{session_id}` auf, um die vollständige History
mit Tool-Call-Nachrichten zu laden.

**Alternative:** Der `/chat`-Endpunkt gibt ein Array aller neuen Messages zurück (einfacher fürs Frontend):

```json
{
  "session_id": "...",
  "messages": [
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "content": "{...}", "tool_name": "list_debates"},
    {"role": "assistant", "content": "Hier sind deine Debatten: ..."}
  ]
}
```

---

### 1.7 GenerationResult-Tool-Calls in der API serialisieren

**Datei:** `backend/services/llm_service.py`

`GenerationResult` muss `tool_calls` als `list[dict]` führen (statt eines komplexen Typs),
damit es direkt als JSON serialisierbar ist. Alternativ: Pydantic-Modell für die API-Response.

---

## Phase 2: Write-Operations mit Bestätigung

(Nicht in diesem Branch — nur Konzept)

- `start_debate(topic, rounds, lang, llm_profiles)` → Kitsune antwortet:
  "Soll ich eine Debatte starten mit: Thema X, 5 Runden, EN? (Ja/Nein)"
  Bei "Ja" → `execute_tool()` führt die Aktion aus
- `archive_debate(debate_id)` → Gleiches Muster
- `export_module(module_id)` → Bestätigung vor Export

### Frontend: Confirmation-Bubble

```
┌──────────────────────────────────┐
│ Kitsune                          │
│ "Soll ich eine Debatte starten   │
│  mit Thema 'KI-Regulierung',     │
│  5 Runden, EN?"                  │
│                                  │
│  [Ja, starten]  [Nein, abbrechen] │
└──────────────────────────────────┘
```

---

## Phase 3: Vertrauenswürdige Write-Operations

(Nicht in diesem Branch — nur Konzept)

- `enable_module(module_id)` / `disable_module(module_id)`
- `switch_llm_profile(agent_role, profile_id)`
- `duplicate_module(module_id, new_name)`
- Confirmation wird optional → User kann in den Einstellungen "Auto-execute trusted tools" aktivieren

---

## Phase 4: Streaming

(Nicht in diesem Branch — nur Konzept)

- Tool-Call-Responses werden per SSE gestreamt
- Frontend zeigt "Kitsune denkt nach..." → "🔧 Debatten werden geladen..." → "Fertig! Hier sind..."
- Erfordert Umstellung von blockierenden Requests auf EventStream

---

## Feinteilige Todo-Liste

### Phase 1 — Backend: LLMService

- [ ] `1.1.1` `backend/services/llm_service.py` — `GenerationResult.tool_calls`-Feld hinzufügen
- [ ] `1.1.2` `backend/services/llm_service.py` — `generate()`-Signatur um `tools: list[dict] | None` erweitern
- [ ] `1.1.3` `backend/services/llm_service.py` — `_generate_litellm()`: `tools`-Parameter in `kwargs` übergeben
- [ ] `1.1.4` `backend/services/llm_service.py` — `_generate_litellm()`: `tool_calls` aus Response parsen
- [ ] `1.1.5` `backend/services/llm_service.py` — `_generate_local()`: `tools` in den Request-Body einfügen
- [ ] `1.1.6` `backend/services/llm_service.py` — `_generate_local()`: `tool_calls` aus Response parsen
- [ ] `1.1.7` `backend/services/llm_service.py` — Tests: `test_generate_with_tools_litellm`, `test_generate_with_tools_local`

### Phase 1 — Backend: Tool-Registry

- [ ] `1.2.1` `backend/services/assistant_tools.py` neu anlegen — `TOOL_REGISTRY`, `@tool`-Decorator, `get_tool_definitions()`, `execute_tool()`
- [ ] `1.2.2` `backend/services/assistant_tools.py` — Tool `get_system_status` implementieren
- [ ] `1.2.3` `backend/services/assistant_tools.py` — Tool `list_debates` implementieren
- [ ] `1.2.4` `backend/services/assistant_tools.py` — Tool `get_debate_details` implementieren
- [ ] `1.2.5` `backend/services/assistant_tools.py` — Tool `get_llm_profiles` implementieren
- [ ] `1.2.6` `backend/services/assistant_tools.py` — Tool `get_modules` implementieren
- [ ] `1.2.7` `backend/services/assistant_tools.py` — Tool `search_knowledge_base` implementieren
- [ ] `1.2.8` Tests für alle Tools schreiben (`tests/backend/test_assistant_tools.py`)

### Phase 1 — Backend: AssistantService

- [ ] `1.3.1` `backend/services/assistant_service.py` — `send_message()` um Tool-Execution-Loop erweitern (max 5 Iterationen)
- [ ] `1.3.2` `backend/services/assistant_service.py` — Tool-Context bereitstellen (BlueprintRepository, DebateStore, ProjectStore)
- [ ] `1.3.3` `backend/services/assistant_service.py` — Tool-Call-Nachrichten in Session-History speichern (neue `ChatMessage.role = "tool"`)
- [ ] `1.3.4` Tests: `test_send_message_with_tool_call`, `test_tool_execution_loop_max_iterations`, `test_tool_error_handling`

### Phase 1 — Backend: API

- [ ] `1.4.1` `backend/api/routers/assistant.py` — `/chat`-Response um `messages: []` (alle neuen Messages inkl. Tool-Calls) erweitern
- [ ] `1.4.2` Tool-Call-Messages in Session-Serialisierung inkludieren (`get_session`/`list_sessions`)
- [ ] `1.4.3` Tests: API-Tests für `/chat` mit Tool-Calls

### Phase 1 — Frontend

- [ ] `1.5.1` `frontend/src/lib/api.js` — `sendAssistantMessage()` an neues Response-Format anpassen (Array von Messages)
- [ ] `1.5.2` `frontend/src/components/AssistantChat.svelte` — Tool-Call-Message-Typ im Chat-Rendering behandeln
- [ ] `1.5.3` `frontend/src/components/AssistantChat.svelte` — Tool-Ergebnisse visuell darstellen (Tabelle für Debatten, Liste für Profile)
- [ ] `1.5.4` `frontend/src/components/AssistantChat.svelte` — Test mit vollständigem Chat-Flow

### Phase 1 — Prompt

- [ ] `1.6.1` `config/prompts/kitsune/kitsune.md` — Boundaries durch Capabilities ersetzen
- [ ] `1.6.2` `config/prompts/kitsune/kitsune.md` — Tool-Beschreibungen in den Prompt aufnehmen
- [ ] `1.6.3` Deutsche Übersetzung des neuen Prompts prüfen (oder generieren)

### Phase 1 — Wissen / Knowledge Base

- [ ] `1.7.1` `scripts/generate_kitsune_knowledge.py` — Wissensbasis muss auch Router-Pfade + Parameter parsen (für Tool-Kontext)
- [ ] `1.7.2` `config/prompts/kitsune/knowledge.txt` neu generieren

### Phase 1 — Tests

- [ ] `1.8.1` `tests/backend/test_assistant_tools.py` — Unit-Tests für alle Read-Only Tools
- [ ] `1.8.2` `tests/backend/test_assistant_tools.py` — Test für Tool-Execution mit Fehlern
- [ ] `1.8.3` `tests/backend/test_llm_service.py` — Test für `generate()` mit `tools`-Parameter
- [ ] `1.8.4` Integrationstest: vollständiger Chat mit Tool-Call → Execution → Antwort

### Phase 1 — CI / Ruff

- [ ] `1.9.1` `ruff check . && ruff format --check .` — bestehen alle Checks?
- [ ] `1.9.2` Tests laufen durch

### Phase 2 & 3 (spätere Branches)

- [ ] Write-Tools mit Confirmation-Mechanismus
- [ ] Frontend-Confirmation-Bubbles
- [ ] Auto-Execute-Einstellung
- [ ] SSE-Streaming für Tool-Execution

---

## Datei-Übersicht

| Aktion | Datei | Änderung |
|--------|-------|----------|
| ✏️ | `backend/services/llm_service.py` | `generate()` + `tools`-Parameter; `GenerationResult.tool_calls` |
| ✏️ | `backend/services/llm_service.py` | `_generate_litellm()`: Tools übergeben + parsen |
| ✏️ | `backend/services/llm_service.py` | `_generate_local()`: Tools übergeben + parsen |
| 🆕 | `backend/services/assistant_tools.py` | Tool-Registry, Decorator, 6 Tools, `execute_tool()` |
| ✏️ | `backend/services/assistant_service.py` | `send_message()`: Tool-Execution-Loop |
| ✏️ | `backend/services/assistant_service.py` | `ChatMessage.role`: `"tool"` unterstützen |
| ✏️ | `backend/api/routers/assistant.py` | Response-Format: Array aller Messages |
| ✏️ | `config/prompts/kitsune/kitsune.md` | Boundaries → Capabilities |
| ✏️ | `frontend/src/components/AssistantChat.svelte` | Tool-Call-Messages rendern |
| ✏️ | `frontend/src/lib/api.js` | Response-Parsing für neues Format |
| 🆕 | `tests/backend/test_assistant_tools.py` | Tool-Tests |
| ✏️ | `tests/backend/test_llm_service.py` | generate_with_tools-Tests |

---

## Risiken & Offene Punkte

| Risiko | Betroffen | Mitigation |
|--------|-----------|------------|
| **Lokale LLMs unterstützen kein Function Calling** | Phase 1 | `_generate_local()` fängt fehlende Tool-Unterstützung ab und gibt `tool_calls: None` zurück — Kitsune fällt auf reinen Text zurück |
| **Tool-Call-Loop blockiert (zu viele Iterationen)** | Phase 1 | `max_iterations = 5` mit Timeout pro Iteration |
| **Tool-Ergebnisse sind zu groß (>4000 Tokens)** | Phase 1 | Ergebnisse kürzen auf `max_result_tokens = 2000` |
| **Session-History wächst durch Tool-Calls** | Phase 1 | `max_messages` berücksichtigt auch Tool-Nachrichten |
| **Litellm-Version unterstützt Tools nicht** | Phase 1 | Fallback: `kwargs.pop("tools", None)` bei `TypeError` |
