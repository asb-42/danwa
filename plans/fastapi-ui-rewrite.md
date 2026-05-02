# FastAPI + HTML/JS UI Rewrite Plan

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Browser (Single Page App)                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Debate   │  │  Config  │  │   DMS    │  │Dashboard│ │
│  │   View    │  │  Panels  │  │  Views   │  │  View   │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │      │
│       └──────────────┴──────┬───────┴─────────────┘      │
│                             │                           │
│                    WebSocket / HTTP                      │
└─────────────────────────────┼───────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────┐
│  FastAPI Backend            │                           │
│  ┌──────────────────────────┴────────────────────────┐  │
│  │  API Router                                          │  │
│  │  ├── /api/debate/*    (start, stream, history)      │  │
│  │  ├── /api/config/*    (CRUD LLM/agent/prompt)       │  │
│  │  ├── /api/dms/*       (projects, documents, RAG)    │  │
│  │  ├── /api/sessions/*  (list, delete, export)        │  │
│  │  └── /ws/debate       (WebSocket streaming)         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Existing Backend (ZERO changes)                    │  │
│  │  ├── DebateEngine    (src/core/debate_engine.py)   │  │
│  │  ├── LLMRouter       (src/core/llm_router.py)      │  │
│  │  ├── ConfigManager   (src/core/config_manager.py)  │  │
│  │  ├── DMS             (src/dms/dms.py)              │  │
│  │  ├── SessionDB       (src/core/session_db.py)      │  │
│  │  ├── ReportGenerator (src/tools/report_generator)  │  │
│  │  └── DocumentParser  (src/tools/doc_parser.py)     │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 2. Backend: FastAPI Server

### File: `src/server/main.py`

```python
from fastapi import FastAPI, WebSocket, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio

app = FastAPI(title="Debate-Agent")

# Serve static frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# API routers
app.include_router(debate_router, prefix="/api/debate")
app.include_router(config_router, prefix="/api/config")
app.include_router(dms_router, prefix="/api/dms")
app.include_router(sessions_router, prefix="/api/sessions")

# WebSocket for debate streaming
@app.websocket("/ws/debate/{session_id}")
async def debate_stream(websocket: WebSocket, session_id: str):
    ...
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/debate/start` | Start debate, returns session_id |
| `GET` | `/ws/debate/{id}` | WebSocket: streams agent messages in real-time |
| `GET` | `/api/debate/{id}` | Get debate result (after completion) |
| `GET` | `/api/config/llm-profiles` | List all LLM profiles |
| `POST` | `/api/config/llm-profiles` | Create new LLM profile |
| `PUT` | `/api/config/llm-profiles/{name}` | Update existing profile |
| `DELETE` | `/api/config/llm-profiles/{name}` | Delete profile |
| `GET` | `/api/config/agent-profiles` | List all agent profiles |
| `POST` | `/api/config/agent-profiles` | Create agent profile |
| `PUT` | `/api/config/agent-profiles/{name}` | Update agent profile |
| `DELETE` | `/api/config/agent-profiles/{name}` | Delete agent profile |
| `GET` | `/api/config/settings` | Get general settings |
| `PUT` | `/api/config/settings` | Update settings |
| `GET` | `/api/dms/projects` | List projects |
| `POST` | `/api/dms/projects` | Create project |
| `DELETE` | `/api/dms/projects/{id}` | Delete project |
| `GET` | `/api/dms/projects/{id}/documents` | List documents |
| `POST` | `/api/dms/projects/{id}/documents` | Upload document |
| `DELETE` | `/api/dms/documents/{id}` | Delete document |
| `POST` | `/api/dms/documents/{id}/rag` | Add to RAG |
| `DELETE` | `/api/dms/documents/{id}/rag` | Remove from RAG |
| `GET` | `/api/sessions` | List past sessions |
| `DELETE` | `/api/sessions/{id}` | Delete session |
| `GET` | `/api/sessions/{id}/trace` | Get audit trace |
| `GET` | `/api/sessions/{id}/report/{fmt}` | Download report (docx/pdf) |

### WebSocket Protocol (Debate Streaming)

```json
// Server → Client messages:
{"type": "status", "message": "Initializing debate..."}
{"type": "round", "round": 1, "max_rounds": 3}
{"type": "agent_start", "role": "strategist"}
{"type": "agent_message", "role": "strategist", "content": "..."}
{"type": "agent_start", "role": "critic"}
{"type": "agent_message", "role": "critic", "content": "..."}
{"type": "consensus", "round": 1, "value": 0.75}
{"type": "complete", "consensus": 0.85, "output": "..."}
{"type": "error", "message": "..."}

// Client → Server messages:
{"type": "start", "context": "...", "profile": "...", "agent_profile": "chatbot", ...}
{"type": "cancel"}
```

### Debate Streaming Implementation

The key challenge: `DebateEngine.run()` uses `progress_callback` for progress updates. We adapt this to WebSocket:

```python
async def run_debate(websocket, params):
    engine = DebateEngine(...)
    
    async def progress(step, detail):
        await websocket.send_json({"type": step, "detail": detail})
    
    # Run in thread pool to not block event loop
    loop = asyncio.get_event_loop()
    state = await loop.run_in_executor(
        None, 
        lambda: asyncio.run(engine.run(params["context"], progress_callback=progress))
    )
    return state
```

**Problem**: `DebateEngine.run()` is async and uses `await` internally. We need to run it in its own event loop or refactor.

**Solution**: Create a bridge that runs the async engine in a separate thread with its own event loop:

```python
async def run_debate_ws(websocket, params):
    queue = asyncio.Queue()
    
    async def ws_progress(step, detail):
        await websocket.send_json({"type": step, "message": detail})
    
    # Run engine in thread pool
    loop = asyncio.get_event_loop()
    state = await loop.run_in_executor(
        None,
        _sync_run_debate,  # wraps asyncio.run(engine.run(...))
        params, ws_progress
    )
```

Actually, the cleanest approach: use `anyio.from_thread.run()` or simply:

```python
def _run_debate_sync(params, progress_queue):
    """Runs in a thread pool. Uses asyncio.run() internally."""
    async def _inner():
        engine = DebateEngine(...)
        async def progress(step, detail):
            await progress_queue.put({"type": step, "detail": detail})
        return await engine.run(params["context"], progress_callback=progress)
    
    return asyncio.run(_inner())
```

## 3. Frontend: Single Page App

### File Structure

```
static/
├── index.html          # Main SPA entry
├── css/
│   └── app.css         # Custom styles (or Tailwind CDN)
├── js/
│   ├── app.js          # Main app, router, state
│   ├── api.js          # API client (fetch wrapper)
│   ├── debate.js       # Debate view + WebSocket handler
│   ├── config.js       # Config panels (LLM, agents, settings)
│   ├── dms.js          # DMS views (projects, documents)
│   └── dashboard.js    # Session history view
└── assets/
    └── ...
```

### UI Layout

```
┌────────────────────────────────────────────────────────────┐
│  🤝 Debate-Agent                    [🏠] [💬] [⚙️] [📁]  │
├──────────┬─────────────────────────────────────────────────┤
│          │                                                 │
│ Sidebar  │  Main Content Area                              │
│          │                                                 │
│ • Home   │  (changes based on navigation)                  │
│ • Debate │                                                 │
│ • Config │                                                 │
│ • DMS    │                                                 │
│ • History│                                                 │
│          │                                                 │
└──────────┴─────────────────────────────────────────────────┘
```

### Debate View

```
┌────────────────────────────────────────────────────────────┐
│  Settings Bar: [Profile ▼] [Agent Profile ▼] [Rounds: 3]  │
│                [☑ Web Validation] [☑ Memory] [Start]       │
├────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  │
│  │  💬 Enter your question or topic:                    │  │
│  │  ┌────────────────────────────────┐ ┌──────┐        │  │
│  │  │ What are the pros and cons...  │ │ Send │        │  │
│  │  └────────────────────────────────┘ └──────┘        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ Round 1 ────────────────────────────────────────────┐  │
│  │  🧠 Strategist                                      │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ The key advantages are...                      │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                                                      │  │
│  │  🔍 Critic                                          │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ However, there are concerns about...           │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                                                      │  │
│  │  📊 Consensus: 0.65                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ Round 2 ────────────────────────────────────────────┐  │
│  │  ...                                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ Result ─────────────────────────────────────────────┐  │
│  │  ✅ Final Consensus: 0.85                           │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ [Final output text...]                         │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │  [📄 Download DOCX] [📄 Download PDF] [📋 Trace]   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### Config View

```
┌────────────────────────────────────────────────────────────┐
│  ⚙️ Configuration                                          │
├──────────┬─────────────────────────────────────────────────┤
│ Tabs:    │                                                 │
│ • LLM    │  🧠 LLM Profiles                               │
│ • Agents │  ┌───────────────────────────────────────────┐  │
│ • Prompts│  │ Name      │ Model    │ URL    │ Actions   │  │
│ • General│  │───────────┼──────────┼────────┼───────────│  │
│ • Lang   │  │ local_qwen│ qwen2.5  │ local  │ ✏️ 🗑️    │  │
│          │  │ cloud_or  │ claude   │ openr  │ ✏️ 🗑️    │  │
│          │  └───────────────────────────────────────────┘  │
│          │  [+ Add Profile]                                │
│          │                                                 │
│          │  ┌─ Add/Edit Profile Modal ───────────────────┐  │
│          │  │ Name:     [________________]                │  │
│          │  │ Model:    [________________]                │  │
│          │  │ Base URL: [________________]                │  │
│          │  │ API Key:  [________________]                │  │
│          │  │ Temperature: [●───────○] 0.4               │  │
│          │  │           [Cancel] [Save]                   │  │
│          │  └────────────────────────────────────────────┘  │
└──────────┴─────────────────────────────────────────────────┘
```

### DMS View

```
┌────────────────────────────────────────────────────────────┐
│  📁 Document Management                                    │
├──────────┬─────────────────────────────────────────────────┤
│ Projects │                                                 │
│          │  📁 Project: Research                           │
│ • Resrch │  ┌───────────────────────────────────────────┐  │
│ • Legal  │  │ Filename    │ Type │ Date     │ Actions   │  │
│ • Tech   │  │─────────────┼──────┼──────────┼───────────│  │
│          │  │ report.pdf  │ PDF  │ 2026-05  │ 📥 🗑️ 📚 │  │
│ [+ New]  │  │ notes.md    │ MD   │ 2026-05  │ 📥 🗑️ 📚 │  │
│          │  └───────────────────────────────────────────┘  │
│          │  [+ Upload Document]                            │
│          │                                                 │
│          │  📚 RAG Context:                                │
│          │  ┌───────────────────────────────────────────┐  │
│          │  │ report.pdf (Chunk 0): The main finding... │  │
│          │  │ report.pdf (Chunk 1): Further analysis... │  │
│          │  └───────────────────────────────────────────┘  │
└──────────┴─────────────────────────────────────────────────┘
```

## 4. Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend | FastAPI | Async-native, WebSocket support, auto-docs |
| Frontend | Vanilla JS + HTML | No build step, no npm, no bundler |
| CSS | Tailwind CDN | Quick styling, no build step |
| Icons | Unicode emoji | No external dependency |
| Tables | Vanilla JS | Simple enough for our needs |
| File upload | Native `<input type="file">` | Works everywhere |

## 5. Migration Strategy

### Phase 1: Backend API (no UI changes yet)
1. Create `src/server/main.py` with FastAPI app
2. Create API routers that wrap `ConfigManager`, `DMS`, `SessionDB`
3. Create WebSocket endpoint for debate streaming
4. Test with `curl` / browser fetch

### Phase 2: Frontend SPA
1. Create `static/index.html` with layout
2. Implement Debate view with WebSocket
3. Implement Config views with forms
4. Implement DMS views with file upload
5. Implement Dashboard/Session history

### Phase 3: Integration & Polish
1. Wire up all API endpoints
2. Error handling and loading states
3. Report download links
4. Trace viewer

### Phase 4: Cleanup
1. Remove Chainlit dependency from `pyproject.toml`
2. Remove `src/ui/chainlit_app.py`, `src/ui/dms_dashboard.py`, `src/ui/dashboard.py`
3. Update `scripts/start.sh` to run FastAPI instead of Chainlit
4. Update README

## 6. Key Design Decisions

### No Build Step
The entire frontend is vanilla HTML/CSS/JS. No npm, no webpack, no React. This keeps the project simple and maintainable. Tailwind CDN provides styling without a build pipeline.

### WebSocket for Debate Only
Only the debate view uses WebSocket (for real-time agent streaming). Everything else uses standard REST API calls. This keeps the architecture simple.

### Stateless API
The FastAPI server is stateless. Session state lives in:
- `SessionDB` (SQLite) for debate history
- `DMS` (SQLite + ChromaDB) for documents
- Config files (YAML) for settings

The frontend maintains UI state only (current tab, form values, etc.).

### Reuse All Backend Code
`DebateEngine`, `LLMRouter`, `ConfigManager`, `DMS`, `SessionDB`, `ReportGenerator`, `DocumentParser` — all reused as-is. The only new code is the API layer and frontend.

## 7. Estimated File Changes

| File | Action | Lines (est.) |
|------|--------|-------------|
| `src/server/main.py` | Create | ~50 |
| `src/server/routers/debate.py` | Create | ~120 |
| `src/server/routers/config.py` | Create | ~150 |
| `src/server/routers/dms.py` | Create | ~120 |
| `src/server/routers/sessions.py` | Create | ~80 |
| `static/index.html` | Create | ~150 |
| `static/js/app.js` | Create | ~100 |
| `static/js/api.js` | Create | ~80 |
| `static/js/debate.js` | Create | ~200 |
| `static/js/config.js` | Create | ~250 |
| `static/js/dms.js` | Create | ~200 |
| `static/js/dashboard.js` | Create | ~100 |
| `static/css/app.css` | Create | ~50 |
| `pyproject.toml` | Modify | +2 deps |
| `scripts/start.sh` | Modify | change launch cmd |
| `src/ui/chainlit_app.py` | Delete | -1000 |
| `src/ui/dms_dashboard.py` | Delete | -300 |
| `src/ui/dashboard.py` | Delete | -100 |
| **Total new code** | | **~1500** |
| **Total removed** | | **~1400** |
