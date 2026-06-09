# Project → Tenant/Case Migration — Task Checklist

> Crash-safe checklist. Each task is independently committable.
> Mark `[x]` as you go. On resume, find the first `[ ]` and continue.

## Phase 1: Core Infrastructure (activeCase + X-Case-Id) ✅

### 1a — Frontend: Add `activeCase` store
- [x] Add `activeCase` persisted store to `frontend/src/lib/stores.js` (already existed line 65)
- [x] Add `activeCase` auto-set when tenant changes in `TenantSelector.svelte` (already done)
- [x] Verify: `localStorage.danwa.activeCase` appears in browser DevTools

### 1b — Backend: Accept `X-Case-Id` header
- [x] Extend `get_project_id()` in `backend/api/deps.py` to read `X-Case-Id` header
- [x] Fallback chain: `X-Case-Id` → `X-Project-Id` → `"_default"`
- [x] Verify: legacy `X-Project-Id` still works, new `X-Case-Id` also works

### 1c — Frontend: Update `core.js` to send `X-Case-Id`
- [x] In `frontend/src/lib/api/core.js`, read `activeCase` and send `X-Case-Id` header
- [x] Keep sending `X-Project-Id` as well (backward compat during transition)
- [x] Verify: API calls carry both headers

### 1d — Frontend: Update `sse.js` to use `activeCase`
- [x] In `frontend/src/lib/sse.js`, change primary source to `activeCase`
- [x] Verify: SSE connections use new store

### 1e — Frontend: Create `CaseSelector` component
- [x] Create `frontend/src/components/CaseSelector.svelte`
- [x] Uses `getCases(tenantId)` to list cases
- [x] Sets `activeCase` on selection
- [x] Shows case title + tags
- [x] Auto-selects first case when tenant changes
- [x] Verify: dropdown shows cases, selection persists

### 1f — Frontend: Wire CaseSelector into App
- [x] Replace `ProjectSelector` in Header with `CaseSelector`
- [x] Replace `ProjectSelector` in Sidebar with `CaseSelector`
- [x] Verify: CaseSelector visible in UI, ProjectSelector gone from active views

---

## Phase 2: Migrate Remaining Views ✅

### 2a — MvpDebateView
- [x] Replace `$activeProject?.id` with `$activeCase?.id` in workflow start call
- [x] Verify: MVP debate creation uses case context

### 2b — DebateReviewPanel
- [x] Replace `activeProject` import with `activeCase`
- [x] Replace `Active Project` label with `Active Case` (i18n key: `mvpDebate.confirm.activeCase`)
- [x] Replace `$activeProject?.name` with `$activeCase?.title`

### 2c — DebateCreatePanel
- [x] Replace `activeProject` import with `activeCase`
- [x] Update `projectId` derived to `caseId`
- [x] Update all `projectId` usages to `caseId`

### 2d — DebateView
- [x] Replace `activeProject` import with `activeCase`
- [x] Update `projectId` derived to use `$activeCase?.id`

### 2e — DocumentsView
- [x] Replace `activeProject` import with `activeCase`
- [x] Update `projectId` derived to use `$activeCase?.id`

### 2f — Migrate JS library files
- [x] `document.js`: Replace `activeProject` → `activeCase`, send both headers
- [x] `session.js`: Replace `activeProject` → `activeCase`, send both headers
- [x] `inputApi.js`: Replace `activeProject` → `activeCase`, send both headers
- [x] `composerApi.js`: Replace `activeProject` → `activeCase`, send both headers
- [x] `workflowPipelineAdapter.svelte.js`: Replace `activeProject` → `activeCase`

### 2g — i18n keys
- [x] Rename `mvpDebate.confirm.activeProject` → `mvpDebate.confirm.activeCase`

### 2h — Frontend build
- [x] Frontend build passes after all Phase 2 changes

---

## Phase 3: Remove Legacy Project UI

### 3a — Remove ProjectSelector
- [x] Delete `frontend/src/components/ProjectSelector.svelte`
- [x] Remove all imports of `ProjectSelector`
- [x] Verify: no build errors

### 3b — Remove `activeProject` store
- [x] Remove `activeProject` from `frontend/src/lib/stores.js`
- [x] Remove all `$activeProject` references across all files (core.js, sse.js, TenantSelector)
- [x] Remove `getProjects` import where no longer needed (kept in DocumentsView/ArchiveView for move dialogs)
- [x] Verify: no build errors

### 3c — Remove ProjectsView + ProjectSettings
- [x] Delete `frontend/src/views/ProjectsView.svelte`
- [x] Delete `frontend/src/components/ProjectSettings.svelte`
- [x] Remove from router/sidebar
- [x] Remove `projects.*` i18n keys
- [x] Verify: no build errors, no broken routes

---

## Phase 4: Backend — Deprecate Legacy Routers

### 4a — Add tenant/case-scoped audit endpoint
- [x] `GET /tenants/{tid}/cases/{cid}/audit/{debate_id}` already exists in case_scoped.py
- [x] AuditView uses tenant-scoped debates (migrated in Phase 2)

### 4b — Add tenant/case-scoped input/output composer endpoints
- [x] Input/output composer works via `X-Case-Id` header through `get_project_id()`
- [x] Case-scoped DMS, audit, and workflow endpoints exist in case_scoped.py

### 4c — Add deprecation headers
- [x] Add deprecation middleware in `backend/main.py` for all legacy routes
- [x] Covers: /api/v1/debate, /api/v1/dms, /api/v1/audit, /api/v1/projects, /api/v1/input, /api/v1/sessions

### 4d — Remove `get_project_id` dependency
- [x] Verify no frontend code sends `X-Project-Id` anymore
- [x] Remove `X-Project-Id` header reading from `get_project_id()`
- [x] Backend app starts successfully
- [x] Frontend build passes

---

## Phase 5: Cleanup

### 5a — Remove Project CRUD dead code ✅
- [x] Simplified `projects.py` router to list-only endpoint
- [x] Cleaned `project.js` frontend to keep only `getProjects()`
- [x] Removed dead CRUD models from `project.py`

### 5b — Create `get_case_dir` abstraction ✅
- [x] Added `get_case_dir(case_id)` in `deps.py` wrapping `ProjectStore.get_project_dir()`
- [x] Added `get_debate_store_for_case(case_id)` in `deps.py`
- [x] Added `get_profile_service_for_case(case_id)` in `deps.py`
- [x] Legacy functions kept as thin wrappers

### 5c — Migrate all callers from ProjectStore ✅
- [x] **5c-1–8**: Routers (audit, dms, debate, output_composer, input_composer, debate_stream, workflow_exec+workflow_reports, hitl)
- [x] **5c-9**: Services (debate_workflow, debate_rag, dms/service, render_engine) + dispatch + case_scoped
- [x] **5c-10**: Workflow (nodes, legacy_nodes, moderator_nodes, workflow_runner)
- [x] **5c-11**: A2A (router, server)
- [x] **5c-12**: Other (config.py)
- Commits: `decdd62`, `4849139`, `d921227`, `4aad443`, `6ad7d6b`, `6d1a613`, `1a4f98d`

### 5d — Final removal of ProjectStore + Project model
- [ ] Replace `get_case_dir()` internals: `ProjectStore.get_project_dir()` → `CaseStore` directory resolution
- [ ] Replace `get_project_store()` inline callers (render_engine, a2a, case_scoped, config, debate) with CaseStore
- [ ] Verify migrations still work (they legitimately use ProjectStore)
- [ ] Remove `backend/persistence/project_store.py` (keep for migrations only if needed)
- [ ] Remove `backend/models/project.py` (Project, ProjectConfig)
- [ ] Remove `backend/api/routers/projects.py` (list endpoint)
- [ ] Full frontend build passes
- [ ] Full backend test suite passes
