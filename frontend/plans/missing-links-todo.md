# Missing Links - Implementation TODO

This document aggregates all features that exist in the backend API or codebase but are not yet fully exposed in the UI. Each item represents a potential implementation project.

---

## Priority 1: High Impact / Low Effort

### 1. Reports Generation UI
| Attribute | Value |
|-----------|-------|
| **Status** | API Implemented, UI Not Implemented |
| **Priority** | High |
| **Effort** | Low-Medium |

**API Functions** (already exist in `src/lib/api.js` lines 385-398):
- `generateReport(sessionId, format)` - POST `/api/v1/sessions/{id}/report`
- `getReportStatus(jobId)` - GET `/api/v1/reports/{job_id}/status`
- `downloadReport(jobId)` - GET `/api/v1/reports/{job_id}/download`

**Required Work**:
- Create new view: `ReportsView.svelte`
- Add route: `#/reports`
- Add navigation entry in Sidebar
- UI components:
  - Report generation form (select session, format: JSON/PDF/CSV)
  - Job status indicator (pending/completed/failed)
  - Download button for completed reports

---

### 2. Backend Logs View (Standalone)
| Attribute | Value |
|-----------|-------|
| **Status** | API Implemented, UI Partial |
| **Priority** | High |
| **Effort** | Low |

**Current State**: Logs accessible only via Config > System tab

**Required Work**:
- Create new view: `LogsView.svelte`
- Add route: `#/logs`
- Add navigation entry in Sidebar
- Enhanced features:
  - Auto-refresh toggle
  - Log level filtering (ERROR, WARN, INFO, DEBUG)
  - Search with regex support
  - Download logs as file

---

## Priority 2: Medium Impact / Medium Effort

### 3. A2A Agent Management Page
| Attribute | Value |
|-----------|-------|
| **Status** | Component Exists, No Navigation |
| **Priority** | Medium |
| **Effort** | Medium |

**Existing Component**: `src/components/blueprint/A2ACapabilities.svelte`

**Required Work**:
- Create new view: `A2AAgentsView.svelte`
- Add route: `#/a2a-agents`
- Add navigation entry in Sidebar
- UI components:
  - List of configured external agents
  - Add/Edit/Remove agent forms
  - Agent capability display (skills, input/output modes)
  - Test connection button
  - Discovery feature (fetch `/.well-known/agent.json`)

---

### 4. Session Archive Management UI
| Attribute | Value |
|-----------|-------|
| **Status** | API Implemented, UI Partial |
| **Priority** | Medium |
| **Effort** | Medium |

**API Functions** (in `src/lib/api.js` lines 404-410):
- `softDeleteSession(sessionId)` - Soft-delete (archive)
- `restoreSession(sessionId)` - Restore archived session

**Current State**: Accessible only via Replay/Diff views

**Required Work**:
- Create new view: `ArchiveManagerView.svelte`
- Add route: `#/archive-manager`
- Add navigation entry in Sidebar
- UI components:
  - List of archived sessions with filters (date, project)
  - Restore button per session
  - Permanent delete option
  - Bulk actions (restore multiple, delete multiple)

---

### 5. Profile Hot-Reload with UI Feedback
| Attribute | Value |
|-----------|-------|
| **Status** | API Implemented, UI Partial |
| **Priority** | Medium |
| **Effort** | Low |

**API Function** (in `src/lib/api.js` line 344):
- `reloadProfiles()` - POST `/api/v1/system/reload-profiles`

**Current State**: Only accessible via Config > System tab

**Required Work**:
- Add to existing Config view or create dedicated panel
- Enhanced features:
  - Live progress indicator during reload
  - Summary of changes (profiles added/updated/removed)
  - Error reporting with details

---

## Priority 3: Lower Impact / Higher Effort

### 6. Blueprint Layout Persistence
| Attribute | Value |
|-----------|-------|
| **Status** | ELKjs Implemented, Persistence Partial |
| **Priority** | Low-Medium |
| **Effort** | Medium |

**Existing Code**: `src/lib/blueprint/layout.js`

**Required Work**:
- Implement full persistence to backend:
  - Save layout to `/api/v1/blueprints` or localStorage
  - Load layout on app start
  - Version/history support
- UI enhancements:
  - Rename layouts
  - Duplicate layouts
  - Export/import layouts as JSON

---

### 7. Multi-Profile Cost Comparison View
| Attribute | Value |
|-----------|-------|
| **Status** | API Implemented, UI Basic |
| **Priority** | Low |
| **Effort** | Medium |

**API Function** (in `src/lib/api.js` line 212):
- `estimateCost(llmProfileId, numAgents, numRounds)`

**Current State**: Basic form in Config > Cost tab, no comparison

**Required Work**:
- Enhance existing Cost tab or create new comparison view
- UI components:
  - Select multiple LLM profiles to compare
  - Fixed parameters (agents, rounds) or allow variation
  - Visual comparison chart (bar chart)
  - Summary recommendation (best cost/efficiency)

---

### 8. Standalone Workflow Execution Panel
| Attribute | Value |
|-----------|-------|
| **Status** | API + Components Implemented |
| **Priority** | Low |
| **Effort** | High |

**Existing Component**: `src/components/workflow/ExecutionPanel.svelte`

**Current State**: Only integrated into DebateView

**Required Work**:
- Extract as standalone view: `WorkflowExecutionView.svelte`
- Add route: `#/execution`
- Add navigation entry (or floating button)
- Enhanced features:
  - Multiple concurrent executions view
  - Execution queue management
  - Pause/Resume/Cancel controls
  - Execution history per workflow

---

## Implementation Order Recommendation

```
Phase 1 (Quick Wins):
├── 1. Backend Logs View (Standalone)
└── 5. Profile Hot-Reload UI

Phase 2 (Core Features):
├── 2. Reports Generation UI
├── 3. A2A Agent Management Page
└── 4. Session Archive Management UI

Phase 3 (Enhancements):
├── 6. Blueprint Layout Persistence
├── 7. Multi-Profile Cost Comparison
└── 8. Standalone Workflow Execution Panel
```

---

## Source References

- Technical Documentation: `docs/technical_documentation.md`
- User Manual: `docs/user_manual.md`
- README: `README.md`
- API Code: `src/lib/api.js`
- Blueprint Layout: `src/lib/blueprint/layout.js`
- Existing Components: `src/components/blueprint/A2ACapabilities.svelte`, `src/components/workflow/ExecutionPanel.svelte`

---

*Generated: 2025-05-09*
*Source: Aggregated from technical_documentation.md, user_manual.md, README.md*