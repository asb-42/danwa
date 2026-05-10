# Danwa Technical Documentation

## Overview

Danwa is a multi-agent debate platform built with Svelte 5, TailwindCSS, and @xyflow/svelte. It provides a visual interface for managing debates, configuring agents, and visualizing workflow execution.

## Architecture

### Technology Stack

- **Frontend Framework**: Svelte 5 (using Svelte 5 runes: `$state`, `$derived`, `$effect`)
- **Styling**: TailwindCSS 3.4 with @tailwindcss/typography
- **Flow Visualization**: @xyflow/svelte 1.5.2 (SvelteFlow)
- **State Management**: Svelte writable stores with localStorage persistence
- **Internationalization**: Custom i18n solution with EN/DE support
- **Testing**: Vitest (unit) + Playwright (e2e, visual, a11y, i18n)
- **Build Tool**: Vite 5

### Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── blueprint/       # Blueprint canvas components
│   │   ├── nodes/      # Node type components
│   │   ├── edges/      # Edge type components
│   │   ├── forms/      # Node configuration forms
│   │   └── Palette.svelte, BlueprintCanvas.svelte, Inspector.svelte
│   ├── workflow/       # Workflow execution components
│   │   ├── nodes/      # Runtime workflow nodes
│   │   ├── edges/      # Runtime workflow edges
│   │   └── panels/     # Timeline, NodeDetail panels
│   ├── hitl/           # Human-in-the-loop components
│   └── Layout.svelte, Sidebar.svelte, Header.svelte
├── views/               # Page-level components (routes)
│   ├── Dashboard.svelte
│   ├── DebateView.svelte
│   ├── BlueprintCanvasView.svelte
│   ├── ConfigView.svelte
│   ├── ArchiveView.svelte
│   ├── AuditView.svelte
│   ├── ProjectsView.svelte
│   ├── DocumentsView.svelte
│   ├── ReplayView.svelte
│   └── DiffView.svelte
├── lib/                 # Core libraries
│   ├── api.js          # API client (all backend communication)
│   ├── stores.js       # Svelte stores (global state)
│   ├── sse.js          # Server-Sent Events handler
│   ├── workflowSSE.js  # Workflow SSE handler
│   ├── workflowExec.js # Workflow execution utilities
│   ├── blueprint/      # Blueprint registry & utilities
│   │   ├── registry.js       # Central node/edge type registry
│   │   ├── registerAll.js    # Register all node/edge types
│   │   ├── store.svelte.js  # Blueprint canvas state
│   │   ├── api.js           # Blueprint persistence API
│   │   ├── dnd.js           # Drag-and-drop utilities
│   │   ├── layout.js        # Auto-layout (ELKjs)
│   │   └── validation.js    # Blueprint validation
│   └── i18n/
│       ├── index.js    # i18n store & utilities
│       └── loaders/
│           ├── en.js   # English translations
│           └── de.js   # German translations
└── App.svelte          # Root component with hash-based routing
```

## Core Features

### 1. Debate System

The core feature is a multi-agent debate system with four agent roles:

- **Strategist**: Initial analysis and argument formation
- **Critic**: Evaluates and challenges arguments
- **Optimizer**: Refines and improves responses
- **Moderator**: Guides discussion toward consensus

**State Management**: `currentDebate`, `debates`, `auditEvents` stores

**API Endpoints** (`lib/api.js`):
- `GET /api/v1/debate` - List debates
- `POST /api/v1/debate` - Create debate
- `GET /api/v1/debate/{id}` - Get debate details
- `POST /api/v1/debate/{id}/start` - Start debate
- `POST /api/v1/debate/{id}/cancel` - Cancel debate
- `DELETE /api/v1/debate/{id}` - Delete debate

### 2. Blueprint Canvas (Visual Workflow Builder)

A visual node-based editor for creating and managing workflow blueprints.

**Node Types** (registered in `registerAll.js`):

**Asset Nodes** (Category: `asset`):
| Type | Component | Description |
|------|-----------|-------------|
| `agent-blueprint` | AgentBlueprintNode | Agent definition with LLM, role, prompt |
| `llm-profile` | LLMProfileNode | LLM provider & model configuration |
| `role-definition` | RoleDefinitionNode | Agent behavior & constraints |
| `prompt-template` | PromptTemplateNode | Reusable prompt with variables |
| `role-type` | RoleTypeNode | Configurable role category |

**Workflow Nodes** (Category: `workflow`):
| Type | Component | Description |
|------|-----------|-------------|
| `wf-input` | InputNode | Case input |
| `wf-initialize` | InitializeNode | Workflow initialization |
| `wf-strategist` | StrategistNode | Strategist agent |
| `wf-critic` | CriticNode | Critic agent |
| `wf-optimizer` | OptimizerNode | Optimizer agent |
| `wf-moderator` | ModeratorNode | Moderator agent |
| `wf-user-injection` | UserInjectionNode | Human input injection point |
| `wf-gate` | GateNode | Conditional gate |

**Edge Types**:
- **Semantic** (`semantic`): `uses_llm`, `implements_role`, `prompted_by`, `overrides_prompt`, `defines_role`
- **Control Flow** (`control_flow`): `sequential`, `conditional`, `interjection`, `feedback`

**Registry System** (`lib/blueprint/registry.js`):
- `registerNode(config)` / `registerEdge(config)` - Register types
- `getNodeRegistration(type)` / `getEdgeRegistration(type)` - Lookup
- `getNodesByCategory(category)` / `getEdgesByCategory(category)` - Filter by category
- `getNodeTypes()` / `getEdgeTypes()` - Build SvelteFlow maps
- `getAllRegisteredNodes()` / `getAllRegisteredEdges()` - List all

**Mode Switcher**: Blueprint mode vs Workflow mode (visual editing vs execution view)

### 3. Configuration System

Centralized profile management for LLM profiles, agent personas, and prompt variants.

**LLM Profiles** (`GET/POST/PUT/DELETE /api/v1/profiles/llm`):
- Provider support: OpenRouter, OpenAI, Anthropic, Ollama, Opencode Zen, Opencode Go, Xiaomi, Local
- Configuration: model, API base, API key env var, temperature, max tokens, context window, timeout, pricing

**Agent Personas** (`GET/POST/PUT/DELETE /api/v1/profiles/agents`):
- Roles: strategist, critic, optimizer, moderator
- Per-role configuration: system prompt, LLM profile, max rounds, consensus threshold

**Prompt Variants** (`GET /api/v1/profiles/prompts`):
- Preview per agent role
- Delete non-default variants

**Cost Estimation** (`GET /api/v1/profiles/cost-estimate`):
- Input: LLM profile, number of agents, number of rounds
- Output: Estimated cost in USD

**System Functions**:
- `POST /api/v1/system/reload-profiles` - Reload YAML profiles from disk
- `GET /api/v1/system/logs` - View backend logs

### 4. Document Management (DMS/RAG)

Document upload and RAG (Retrieval-Augmented Generation) integration.

**API Endpoints**:
- `GET/POST/DELETE /api/v1/dms/documents` - CRUD operations
- `POST /api/v1/dms/documents/{id}/rag` - Add to RAG index
- `DELETE /api/v1/dms/documents/{id}/rag` - Remove from RAG
- `GET /api/v1/dms/rag/manual` - List RAG-enabled documents
- `GET /api/v1/dms/rag/search` - Search RAG context
- `PUT /api/v1/debate/{id}/documents` - Assign documents to debate

**Features**:
- Drag-and-drop upload
- Supported formats: PDF, DOCX, ODT, TXT, MD, images (OCR)
- RAG auto-retrieve option per debate

### 5. Project Management

Multi-tenant project system with project-scoped configuration.

**API Endpoints**:
- `GET/POST /api/v1/projects` - List/create projects
- `GET/PUT/DELETE /api/v1/projects/{id}` - CRUD operations
- `GET/PUT /api/v1/projects/{id}/config` - Project-specific config

**Project Settings**:
- Language preference
- Default max rounds
- Default consensus threshold
- Search mode (SearXNG configuration)

### 6. Human-in-the-Loop (HITL)

OOB (Out-of-Band) input injection during debate execution.

**API Endpoint**: `POST /api/v1/debate/{id}/oob`

**Target Options**:
- `next` - Next agent in sequence
- `strategist` / `critic` / `optimizer` / `moderator` - Specific role
- `current` - Currently active agent
- Round-based targeting (`round`, `from_round`)

**Urgency Modes**:
- `append` - Append to context queue
- `inject` - Inject immediately

**UI Components**:
- `OOBInputPanel.svelte` - Input form in DebateView
- `InjectPanel.svelte` - Side panel for injection history

### 7. A2A Protocol (Agent-to-Agent)

Integration with external A2A-capable agents.

**Features**:
- Add external agents as debate participants
- Agent URL configuration
- Role and position assignment
- A2A protocol vs LiteLLM fallback
- Capability discovery (`GET /.well-known/agent.json`)
- Timeout and fallback profile configuration

**UI Component**: `A2ACapabilities.svelte` - Agent capability display

### 8. Audit & Replay System

Comprehensive event tracking and session replay.

**Audit API** (`GET /api/v1/workflow-exec/{session_id}/audit-log`):
- Filter by event type, date range
- Pagination support

**Session Management**:
- `GET /api/v1/workflow-exec/sessions` - List sessions for replay/diff
- `DELETE /api/v1/workflow-exec/{id}` - Soft-delete (archive)
- `POST /api/v1/workflow-exec/{id}/restore` - Restore archived session

**UI Views**:
- `ReplayView.svelte` - Step-through replay with playback controls
- `DiffView.svelte` - Compare two session executions

### 9. Reports Generation

Generate exportable reports from debate sessions.

**API Endpoints**:
- `POST /api/v1/sessions/{id}/report` - Generate report (JSON, PDF, CSV)
- `GET /api/v1/reports/{job_id}/status` - Check generation status
- `GET /api/v1/reports/{job_id}/download` - Download completed report

### 10. Internationalization (i18n)

Full i18n support with EN/DE locales.

**Implementation** (`lib/i18n/`):
- `index.js` - Store with `setLocale()`, `t()`, `formatNumber()`, `formatDate()`
- `loaders/en.js` - 623 English translations
- `loaders/de.js` - German translations

**Language Switching**:
- URL parameter: `?lang=en`
- localStorage key: `locale`
- Default: German

## State Management

### Global Stores (`lib/stores.js`)

| Store | Type | Description |
|-------|------|-------------|
| `route` | writable | Current hash-based route |
| `routeParams` | writable | Route parameters array |
| `healthStatus` | writable | Backend health status |
| `currentDebate` | writable | Active debate state |
| `debates` | writable | List of recent debates |
| `auditEvents` | writable | Current debate audit events |
| `sseConnected` | writable | SSE connection status |
| `error` | writable | Global error message |
| `loading` | writable | Global loading state |
| `activeProject` | persisted | Current project (localStorage) |
| `selectedLLMProfile` | persisted | Selected LLM profile ID |
| `selectedPromptVariant` | persisted | Selected prompt variant ID |
| `selectedPersonas` | persisted | Per-role persona selection |

### Blueprint Store (`lib/blueprint/store.svelte.js`)

Svelte 5 rune-based state management for canvas:
- `nodes` / `edges` - Current graph state
- `selectedNode` / `selectedEdge` - Selection state
- `mode` - 'blueprint' or 'workflow'
- `panelOpen` / `panelTab` - UI state

## API Client (`lib/api.js`)

**Features**:
- Automatic `X-Project-Id` header injection
- Error translation using i18n
- FastAPI validation error formatting
- File upload support (FormData)

**Error Mapping**:
```javascript
{
  'Debate not found': 'error.debateNotFound',
  'Invalid input': 'error.invalidInput',
  'Backend connection lost': 'error.backendDisconnected'
}
```

## Testing

### Unit Tests (Vitest)
```bash
npm run test:unit
npm run test:unit:watch
```

### E2E Tests (Playwright)
```bash
npm run test:e2e                # All e2e tests
npm run test:e2e:headed          # Run with browser visible
npm run test:e2e:ui             # Playwright UI mode
npm run test:contracts          # Contract tests
npm run test:visual             # Visual regression tests
npm run test:a11y               # Accessibility tests
npm run test:i18n               # i18n tests
npm run test:i18n:de            # German i18n tests
npm run test:i18n:en            # English i18n tests
```

## Environment Variables

Create `.env` from `.env.example`:
```bash
VITE_API_URL=http://localhost:8000  # Backend API base URL
```

## Build & Run

```bash
# Development
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

## Missing Links (Features in Code but Not Fully in UI)

This section documents features that exist in the backend API or codebase but are not yet fully exposed in the UI.

### 1. Reports UI
- **API Status**: Implemented (`generateReport`, `getReportStatus`, `downloadReport`)
- **UI Status**: Not implemented - no dedicated Reports view
- **Location**: API functions exist in `lib/api.js` lines 385-398

### 2. A2A Agent Management Page
- **API Status**: Partially implemented
- **UI Status**: Partial - `A2ACapabilities.svelte` component exists but no dedicated navigation entry
- **Location**: `components/blueprint/A2ACapabilities.svelte`

### 3. Workflow Execution Panel (Standalone)
- **API Status**: Implemented via SSE and OOB endpoints
- **UI Status**: Integrated into DebateView, not a separate page
- **Location**: `components/workflow/ExecutionPanel.svelte`

### 4. Blueprint Auto-Layout
- **Implementation Status**: ELKjs integration exists in `lib/blueprint/layout.js`
- **UI Status**: Button exists in canvas toolbar, but save/load layouts not fully persistent

### 5. Session Archive/Restore UI
- **API Status**: Implemented (`softDeleteSession`, `restoreSession`)
- **UI Status**: Partial - accessible via Replay/Diff but no dedicated archive management UI
- **Location**: API functions in `lib/api.js` lines 404-410

### 6. Backend Logs Viewer
- **API Status**: Implemented (`getBackendLogs`)
- **UI Status**: Partial - only accessible via Config > System tab
- **Expected**: Dedicated System/Logs view

### 7. Profile Hot-Reload UI
- **API Status**: Implemented (`reloadProfiles`)
- **UI Status**: Partial - only accessible via Config > System tab
- **Expected**: Dedicated profile management with live reload button

### 8. Cost Estimation Comparison
- **API Status**: Implemented (`estimateCost`)
- **UI Status**: Partial - basic form in Config > Cost tab
- **Expected**: Comparison view between multiple LLM profiles

## Routes Summary

| Route | View Component | Description |
|-------|----------------|-------------|
| `#/dashboard` | Dashboard | Overview with stats |
| `#/debate` | DebateView | Debate list (new debate form) |
| `#/debate/{id}` | DebateView | Active/running debate |
| `#/documents` | DocumentsView | Document management & RAG |
| `#/archive` | ArchiveView | Archived debates |
| `#/audit` | AuditView | Audit trail viewer |
| `#/projects` | ProjectsView | Project management |
| `#/projects/{id}/settings` | ProjectSettings | Project configuration |
| `#/config` | ConfigView | LLM profiles, agents, prompts |
| `#/blueprint` | BlueprintCanvasView | Visual workflow builder |
| `#/replay` | ReplayView | Session replay player |
| `#/diff` | DiffView | Session comparison |

## Version History

- **v2.0.0** (current): Svelte 5 rewrite, Blueprint Canvas, Workflow mode, A2A protocol support
- **v1.x**: Legacy version (deprecated)