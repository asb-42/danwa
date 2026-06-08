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
- [ ] Delete `frontend/src/components/ProjectSelector.svelte`
- [ ] Remove all imports of `ProjectSelector`
- [ ] Verify: no build errors

### 3b — Remove `activeProject` store
- [ ] Remove `activeProject` from `frontend/src/lib/stores.js`
- [ ] Remove all `$activeProject` references across all files (core.js, sse.js, TenantSelector)
- [ ] Remove `getProjects` import where no longer needed
- [ ] Verify: no build errors

### 3c — Remove ProjectsView + ProjectSettings
- [ ] Archive or delete `frontend/src/views/ProjectsView.svelte`
- [ ] Archive or delete `frontend/src/components/ProjectSettings.svelte`
- [ ] Remove from router/sidebar
- [ ] Remove `projects.*` i18n keys
- [ ] Verify: no build errors, no broken routes

---

## Phase 4: Backend — Deprecate Legacy Routers

### 4a — Add tenant/case-scoped audit endpoint
- [x] `GET /tenants/{tid}/cases/{cid}/audit/{debate_id}` already exists in case_scoped.py
- [ ] Verify AuditView uses it

### 4b — Add tenant/case-scoped input/output composer endpoints
- [ ] Verify input composer endpoints exist in case_scoped.py or create them
- [ ] Verify output composer endpoints exist in case_scoped.py or create them

### 4c — Add deprecation headers
- [ ] Add `X-Deprecation` header to `backend/api/routers/dms.py`
- [ ] Add `X-Deprecation` header to `backend/api/routers/audit.py`
- [ ] Add `X-Deprecation` header to `backend/api/routers/input_composer.py`
- [ ] Add `X-Deprecation` header to `backend/api/routers/output_composer.py`

### 4d — Remove `get_project_id` dependency
- [ ] Verify no frontend code sends `X-Project-Id` anymore
- [ ] Remove `X-Project-Id` header reading from `get_project_id()`
- [ ] Rename to `get_case_id()` or remove entirely
- [ ] Verify all backend tests pass

---

## Phase 5: Cleanup

### 5a — Remove ProjectStore
- [ ] Verify no backend code imports `ProjectStore`
- [ ] Archive or delete `backend/persistence/project_store.py`
- [ ] Verify backend starts

### 5b — Remove Project model
- [ ] Verify no backend code imports `Project` model
- [ ] Archive or delete `backend/models/project.py`
- [ ] Verify backend starts

### 5c — Remove legacy debate.py router
- [ ] Verify no frontend code calls `/api/v1/debate` (legacy)
- [ ] Archive or delete `backend/api/routers/debate.py`
- [ ] Verify backend starts

### 5d — Final verification
- [ ] Full frontend build passes
- [ ] Full backend test suite passes
- [ ] No remaining references to `activeProject` in frontend
- [ ] No remaining references to `X-Project-Id` in frontend
- [ ] No remaining imports of `ProjectStore` in backend
