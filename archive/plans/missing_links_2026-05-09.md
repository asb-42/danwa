# Danwa — Missing Links Analysis

> **Date**: 2026-05-09  
> **Version**: 2.0.0  
> **Scope**: Full codebase audit — all 16 backend routers, 6 frontend API clients, 10 frontend views, and all backend services.

---

## What are "Missing Links"?

Features **fully implemented** in the backend and/or frontend API client, but **not yet accessible through the user interface**. Users cannot use these features without direct API calls.

---

## Summary of Findings

| # | Feature | Backend | API Client | UI | Risk |
|---|---------|---------|------------|-----|------|
| 1 | Async Report Generation (DOCX/PDF/ODF) | ✅ | ✅ Exists | ❌ Missing | High impact |
| 2 | Application Settings Tab | ✅ | ✅ Exists | ❌ No tab | Medium impact |
| 3 | Manual RAG Search | ✅ | ✅ Exists | ❌ Missing | High impact |
| 4 | A2A Agent Discovery | ✅ | ✅ Exists | ❌ Missing | Medium impact |
| 5 | Session Soft-Delete / Restore | ✅ | ✅ Exists | ❌ Missing | Medium impact |
| 6 | Workflow Pause/Resume/Cancel (workflow-exec) | ✅ | ✅ Exists | ❌ Missing | Medium impact |
| 7 | Workflow Interjection (workflow-exec) | ✅ | ✅ Exists | ❌ Missing | Medium impact |
| 8 | Workflow State Query | ✅ | ✅ Exists | ❌ Missing | Low impact |
| 9 | Workflow SSE Stream (workflow-exec) | ✅ | ✅ Exists | ❌ Missing | Medium impact |
| 10 | Report SSE Progress Stream | ✅ | ❌ Missing | ❌ Missing | Low impact |
| 11 | Blueprint Compile & Clone | ✅ | ✅ Exists | ❌ Missing | Medium impact |
| 12 | Canvas Layout CRUD | ✅ | ✅ Exists | ❌ Missing | Low impact |
| 13 | Role Types CRUD | ✅ | ✅ Exists | ❌ Missing | Low impact |
| 14 | Language API (get/set) | ✅ | ❌ Missing | ❌ Missing | Low impact |
| 15 | Project-Level Settings (config/settings/project) | ✅ | ❌ Missing | ❌ Missing | Low impact |
| 16 | Legacy Session History (sessions.py) | ✅ | ❌ Missing | ❌ Missing | Low impact |

---

## Detailed Findings

### 1. Async Report Generation (DOCX/PDF/ODF) — HIGH IMPACT

**Backend**: `backend/api/routers/workflow_reports.py`  
**Endpoints**:
```
POST   /api/v1/sessions/{session_id}/report   — Create async report job
GET    /api/v1/reports/{job_id}/status         — Query job status
GET    /api/v1/reports/{job_id}/download       — Download completed report
GET    /api/v1/sessions/{session_id}/report/stream — SSE progress stream
```

**API Client** (`frontend/src/lib/api.js`):
- `generateReport(sessionId, format)` — exists but **never called**
- `getReportStatus(jobId)` — exists but **never called**
- `downloadReport(jobId)` — exists but **never called**

**i18n strings** exist for report UI:
- `report.generate`, `report.status.pending`, `report.status.completed`, `report.status.failed`, `report.download`

**What's missing**:
- No "Download Report" button in `DebateView.svelte` or `ArchiveView.svelte`
- No report format selector (DOCX vs PDF vs ODF)
- No report job status indicator
- No report progress UI

**Note**: There is also a **legacy** report endpoint in `backend/api/routers/sessions.py`:
```
GET /api/v1/sessions/{session_id}/report/{fmt}  (fmt = docx|pdf)
```
This is a synchronous endpoint. The new `workflow_reports.py` router provides async job-based reports with ODF support.

---

### 2. Application Settings Tab — MEDIUM IMPACT

**Backend**: `backend/api/routers/config.py`  
**Endpoints**:
```
GET    /api/v1/config/settings                 — Get all settings
PUT    /api/v1/config/settings                 — Update settings
GET    /api/v1/config/settings/project/{id}    — Get project-overridden settings
GET    /api/v1/config/language                 — Get current language
PUT    /api/v1/config/language                 — Set language
```

**API Client** (`frontend/src/lib/api.js`):
- `getSettings()` — exists, used only in `ProjectSettings.svelte`
- `updateSettings(settings)` — exists but **never called from ConfigView**

**What's missing**:
- `ConfigView.svelte` tabs: `llm`, `agents`, `prompts`, `cost`, `system`
- **No "settings" tab** for global application settings (search, privacy, retention)
- `updateSettings()` is never called — only project config is editable

---

### 3. Manual RAG Search — HIGH IMPACT

**Backend**: `backend/api/routers/dms.py`  
**Endpoints**:
```
GET    /api/v1/dms/rag/manual                 — List manual RAG document IDs
GET    /api/v1/dms/rag/search?q={query}&k={k} — Search RAG chunks
```

**API Client** (`frontend/src/lib/api.js`):
- `getManualRAGDocuments()` — exists but **never called**
- `searchRAG(query, limit)` — exists but **never called**

**What's missing**:
- `DocumentsView.svelte` has RAG toggle (add/remove) but **no search UI**
- Users cannot run custom RAG queries or view search results with relevance scores

---

### 4. A2A Agent Discovery — MEDIUM IMPACT

**Backend**: `backend/api/routers/a2a_discovery.py`  
**Endpoints**:
```
POST   /api/v1/a2a/discover                   — Discover A2A agent capabilities
POST   /api/v1/a2a/capabilities/{profile_id}  — Store discovered capabilities
```

**API Client** (`frontend/src/lib/a2aApi.js`):
- `discoverA2A(endpointUrl)` — exists but **never called**
- `saveA2ACapabilities(profileId, capabilities)` — exists but **never called**

**i18n strings** exist for discovery UI:
- `a2a.discover.button`, `a2a.discover.loading`, `a2a.discover.success`, `a2a.discover.error`
- `a2a.capabilities.title`, `a2a.capabilities.skills`, `a2a.capabilities.inputModes`, `a2a.capabilities.outputModes`

**Component** exists but is orphaned:
- `frontend/src/components/blueprint/A2ACapabilities.svelte` — displays capabilities but is **never imported** by any view

**What's missing**:
- No "Discover" button in the A2A section of `DebateView.svelte`
- No capability display panel anywhere in the UI
- `A2ACapabilities.svelte` component is dead code

---

### 5. Session Soft-Delete / Restore — MEDIUM IMPACT

**Backend**: `backend/api/routers/workflow_exec.py`  
**Endpoints**:
```
DELETE /api/v1/workflow-exec/{session_id}              — Soft-delete (archive)
POST   /api/v1/workflow-exec/{session_id}/restore       — Restore archived session
```

**API Client** (`frontend/src/lib/api.js`):
- `softDeleteSession(sessionId)` — exists but **never called**
- `restoreSession(sessionId)` — exists but **never called**

**i18n strings** exist:
- `session.softDelete`, `session.restore`, `session.archived`

**What's missing**:
- No "Archive" button in `ArchiveView.svelte`
- No "Restore" functionality for archived sessions
- No visual indication of archived vs. active sessions

---

### 6. Workflow Pause/Resume/Cancel (workflow-exec) — MEDIUM IMPACT

**Backend**: `backend/api/routers/workflow_exec.py`  
**Endpoints**:
```
POST   /api/v1/workflow-exec/{session_id}/pause        — Pause workflow
POST   /api/v1/workflow-exec/{session_id}/resume       — Resume workflow
POST   /api/v1/workflow-exec/{session_id}/cancel       — Cancel workflow
```

**API Client** (`frontend/src/lib/workflowExec.js`):
- `pauseWorkflow(sessionId)` — exists but **never called**
- `resumeWorkflow(sessionId)` — exists but **never called**
- `cancelWorkflow(sessionId)` — exists but **never called**

**Note**: The HITL system (`/api/v1/debate/{id}/pause`) provides pause/resume for the debate workflow, but the workflow-exec endpoints are for the **blueprint workflow engine** — a separate system.

**What's missing**:
- No pause/resume/cancel controls in `BlueprintCanvasView.svelte` or `ExecutionPanel.svelte`
- `ExecutionPanel.svelte` imports these functions but they may not be wired to UI buttons

---

### 7. Workflow Interjection (workflow-exec) — MEDIUM IMPACT

**Backend**: `backend/api/routers/workflow_exec.py`  
**Endpoint**:
```
POST   /api/v1/workflow-exec/{session_id}/interject     — Submit interjection
```

**API Client** (`frontend/src/lib/workflowExec.js`):
- `submitInterjection(sessionId, content, source)` — exists, **used in ExecutionPanel.svelte**

**Status**: Partially exposed through `ExecutionPanel.svelte`. However, the SSE stream for workflow-exec events is not consumed by any view.

---

### 8. Workflow State Query — LOW IMPACT

**Backend**: `backend/api/routers/workflow_exec.py`  
**Endpoint**:
```
GET    /api/v1/workflow-exec/{session_id}/state          — Get execution state
```

**API Client** (`frontend/src/lib/workflowExec.js`):
- `getWorkflowState(sessionId)` — exists but **never called**

**What's missing**:
- No state inspection panel for running workflow sessions

---

### 9. Workflow SSE Stream (workflow-exec) — MEDIUM IMPACT

**Backend**: `backend/api/routers/workflow_exec.py`  
**Endpoint**:
```
GET    /api/v1/workflow-exec/{session_id}/stream          — SSE event stream
```

**API Client** (`frontend/src/lib/workflowSSE.js`):
- `createWorkflowSSE(sessionId)` — exists but **never called**

**What's missing**:
- No real-time event stream consumption for workflow-exec sessions
- The `BlueprintCanvasView.svelte` does not connect to the workflow-exec SSE stream

---

### 10. Report SSE Progress Stream — LOW IMPACT

**Backend**: `backend/api/routers/workflow_reports.py`  
**Endpoint**:
```
GET    /api/v1/sessions/{session_id}/report/stream        — SSE progress stream
```

**API Client**: No corresponding function in any frontend API module.

**What's missing**:
- No SSE consumption for report generation progress

---

### 11. Blueprint Compile & Clone — MEDIUM IMPACT

**Backend**: `backend/api/routers/blueprints.py`  
**Endpoints**:
```
POST   /api/v1/blueprints/workflows/{wf_id}/compile      — Compile workflow
POST   /api/v1/blueprints/workflows/{wf_id}/clone         — Clone workflow
```

**API Client** (`frontend/src/lib/blueprint/api.js`):
- `compileWorkflow(wfId)` — exists but **never called**
- `cloneWorkflow(wfId)` — exists but **never called**

**What's missing**:
- No "Compile" button in `BlueprintCanvasView.svelte` or `Inspector.svelte`
- No "Clone" button for workflow definitions
- No compilation error display in the UI

---

### 12. Canvas Layout CRUD — LOW IMPACT

**Backend**: `backend/api/routers/canvas.py`  
**Endpoints**:
```
GET    /api/v1/canvas/layouts                            — List layouts
GET    /api/v1/canvas/layouts/{layout_id}                — Get layout
POST   /api/v1/canvas/layouts                            — Create layout
PUT    /api/v1/canvas/layouts/{layout_id}                — Update layout
DELETE /api/v1/canvas/layouts/{layout_id}                — Delete layout
```

**API Client** (`frontend/src/lib/blueprint/api.js`):
- `listCanvasLayouts()`, `getCanvasLayout()`, `createCanvasLayout()`, `updateCanvasLayout()`, `deleteCanvasLayout()` — all exist

**What's missing**:
- Layout management is partially used in `BlueprintCanvasView.svelte` but there's no layout list/selector UI
- No "Save As" or "Load Layout" functionality exposed to users

---

### 13. Role Types CRUD — LOW IMPACT

**Backend**: `backend/api/routers/blueprints.py`  
**Endpoints**:
```
GET    /api/v1/blueprints/role-types                     — List role types
POST   /api/v1/blueprints/role-types                     — Create role type
PUT    /api/v1/blueprints/role-types/{id}                — Update role type
DELETE /api/v1/blueprints/role-types/{id}                — Delete role type
```

**API Client** (`frontend/src/lib/blueprint/api.js`):
- `listRoleTypes()`, `getRoleType()`, `createRoleType()`, `updateRoleType()`, `deleteRoleType()` — all exist but **never called**

**What's missing**:
- No role type management UI anywhere

---

### 14. Language API — LOW IMPACT

**Backend**: `backend/api/routers/config.py`  
**Endpoints**:
```
GET    /api/v1/config/language                 — Get current language + supported list
PUT    /api/v1/config/language                 — Set language
```

**API Client**: No corresponding functions in any frontend API module.

**What's missing**:
- Language switching is done via `i18n.setLocale()` in `App.svelte` but does not persist to backend
- The backend language endpoint is never called

---

### 15. Project-Level Settings Override — LOW IMPACT

**Backend**: `backend/api/routers/config.py`  
**Endpoint**:
```
GET    /api/v1/config/settings/project/{project_id}       — Get merged project settings
```

**API Client**: No corresponding function in any frontend API module.

**What's missing**:
- `ProjectSettings.svelte` uses `getSettings()` (global) but never calls the project-specific endpoint

---

### 16. Legacy Session History — LOW IMPACT

**Backend**: `backend/api/routers/sessions.py`  
**Endpoints**:
```
GET    /api/v1/sessions/                                 — List sessions
GET    /api/v1/sessions/{session_id}                     — Get session
DELETE /api/v1/sessions/{session_id}                     — Delete session
GET    /api/v1/sessions/{session_id}/trace               — Get trace
GET    /api/v1/sessions/{session_id}/report/{fmt}        — Download report
```

**API Client**: No corresponding functions in any frontend API module.

**Note**: This is a **legacy** router. The newer `workflow_exec.py` and `workflow_reports.py` routers supersede most of these endpoints. However, the trace endpoint (`/trace`) is still useful and not exposed.

---

## Recommendations (Priority Order)

1. **Report Generation UI** — Add download buttons to DebateView/ArchiveView. This is the highest-impact missing feature.
2. **Application Settings Tab** — Add a "Settings" tab to ConfigView. The API is ready; only the UI tab is missing.
3. **Manual RAG Search** — Add a search panel to DocumentsView. The API is ready; only the UI is missing.
4. **A2A Discovery UI** — Wire up the `A2ACapabilities.svelte` component and add a discover button.
5. **Session Archive/Restore** — Add archive/restore buttons to ArchiveView.
6. **Blueprint Compile/Clone** — Add compile and clone buttons to the blueprint canvas.
7. **Workflow-Exec Controls** — Wire up pause/resume/cancel in the ExecutionPanel.
8. **Language API Integration** — Persist language preference to backend.
