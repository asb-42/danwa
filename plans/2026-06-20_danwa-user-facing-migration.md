# Plan: `danwa` zur reinen User-Facing-Komponente reduzieren

**Datum:** 2026-06-20
**Status:** Entwurf (zur Abstimmung)
**Vorgänger:** [`2026-06-15_danwa-studio.md`](2026-06-15_danwa-studio.md)
**Scope:** Frontend (`frontend/`) dieses Repos + **Übernahme der „Pending Fixes"** in `danwa-core` / `danwa-studio`
**Repos:** `danwa` (dieses), `danwa-core` (Backend, extern), `danwa-modules` (extern), `danwa-studio` (extern)
**Baseline-Commit:** `81f8124` (v0.3.0 pre-architecture-refactor)
**Analyse:** 38 Commits seit Baseline, davon 21 → danwa-core, 4 → danwa-studio, 5 → bleiben danwa

---

## 1. Ziel

Aus dem Repo `danwa` (Svelte-5-Frontend) alles entfernen, was nicht zur **Endbenutzer-App** gehört:

- Admin-/Dev-Views (User-Management, Server-Health, Tenant-Settings, Tag-Manager)
- Build-/Config-Views (Blueprint-Canvas, ManageView, ConfigView, ModulesView, TranslationDashboard, ProposalsView)
- Input-/Output-Composer (gehört konzeptuell zu Studio)
- Diff-/Replay-Views (Studio-only)
- Workflow-Exec-View inkl. `ExecutionPanel` (Studio-only — User startet Workflows über `DebateCreatePanel`)
- Bundle-Composer (Studio-only)

Danach soll `danwa` nur noch folgende User-Features haben:

| Bereich | Routes |
|---------|--------|
| **START** | `dashboard`, `workspace`, `case-list`, `tags` |
| **ARBEITEN** | `debate/:id`, `mvp-debate`, `documents`, `archive` |
| **ERGEBNISSE** | `audit` (Read-only Replay der eigenen Debatte) |
| **KONTO** | `profile`, `my-keys`, `login` |

**Wichtiger Vorbehalt:** Der ursprüngliche Plan sieht Phase 2 (danwa schlank machen) **erst nach Phase 3** (danwa-studio voll funktionsfähig) vor. Dieser Plan geht bewusst **einen Zwischenschritt**: Es wird **alles in diesem Repo entfernt, was nicht zur Endbenutzer-App gehört**, aber **keine** Shared-Package-Integration (`@danwa/*`) und **keine** Auth-Redirect-Logik für Admin→`/studio` vorgenommen. Beides kommt, wenn danwa-studio selbst steht.

---

## 1a. Inventur der externen Repos (Stand 2026-06-20)

| Repo | Lokal | GitHub | Inhalt | Letzter Commit |
|------|-------|--------|--------|----------------|
| `danwa-core` (Backend) | `/media/data/coding/danwa-core` | `github.com/asb-42/danwa-core` | `backend/` (api, blueprints, core, models, workflow, services, migrations, tasks), `config/`, `modules/`, `profiles/`, `scripts/`, `deploy/`, `packages/`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `Makefile` | `13f501b` "Stage all changes before filter" |
| `danwa-studio` (Admin/Dev-Frontend) | `/media/data/coding/danwa-studio` | `github.com/asb-42/danwa-studio` | Svelte 5 + Vite Setup, `src/{views,components,lib,routes}` (22 Views + Blueprint-Komponenten kopiert), `vite.config.js`, `tailwind.config.js`, `AGENTS.md`, `CLAUDE.md` | `2232daa` "Sprint 1: Workflow Templates View, LLM Profiles View + Modal, ConfirmDialog, i18n keys, all Blueprint Canvas components from danwa" |
| `danwa-modules` (Module) | `/media/data/coding/danwa-modules` | `github.com/asb-42/danwa-modules` | `agent-argumentation-patterns/`, `agent-bundles/`, `agent-cores/`, `agent-prompt-modifiers/`, `agent-tone-profiles/`, `kitsune-assistant/`, `llm-profiles/`, `ui-translations/`, `workflows/`, `schemas/`, `scripts/` | `7659b7a` "fix: replace placeholder api_key_env in 2 LLM profiles" |

### Beobachtungen aus der Inventur

1. **`danwa-studio`:** Erste Views sind bereits migriert (WorkflowTemplates, LLMProfiles, BlueprintCanvas, Modules, Translations, Replay, Diff, etc.). Die Lib-Infrastruktur (`workflowExec.js`, `workflowSession.js`, `api/module.js`) wurde kopiert.
2. **`danwa-core`:** Backend-Code ist gespiegelt, aber **ohne `tests/`-Verzeichnis** — die gesamten Pytest-Tests aus diesem Repo sind noch nicht übernommen.
3. **`danwa-modules`:** Module-Inhalte sind eigenständig, kein Bezug zur Frontend-Migration nötig.

### Was in danwa-studio NOCH FEHLT (relevant für Pending Fixes)

| Datei | In `danwa` vorhanden? | In `danwa-studio` vorhanden? |
|-------|----------------------|----------------------------|
| `src/lib/sse.js` | ✅ | ❌ |
| `src/lib/workflowPipelineAdapter.svelte.js` | ✅ | ❌ |
| `src/lib/elk-service.js` | ✅ | ❌ (relevant wenn BlueprintCanvas schon migriert — sollte da sein!) |
| `src/lib/blueprint/*` (13 Dateien) | ✅ | nur teilweise — siehe §7 |
| `src/lib/input/*` | ✅ | ❌ |
| `src/lib/api/{backup,settings,graph}.js` | ✅ | ❌ |

**Implikation:** Für die Pending Fixes, die Frontend-Libs aus `danwa` anfassen, müssen diese Libs ggf. **erst nach danwa-studio kopiert** werden, bevor der Fix dort übernommen werden kann.

---

## 1b. Pending Fixes: Commits seit v0.3.0, die nicht in die externen Repos übernommen wurden

**Baseline-Commit:** `81f8124` "chore(release): v0.3.0 -- pre-architecture-refactor baseline" (2026-06-XX)
**Analyse:** `git log 81f8124..HEAD` zeigt **38 Commits**, die inhaltlich in `danwa-core`, `danwa-studio` oder `danwa-modules` gehören.

### 1b.1 → danwa-core (Backend / Migrations / Tests)

| Commit | Geänderte Dateien (Pfad in `danwa`) | Zielpfad in `danwa-core` | Bereits in danwa-core? |
|--------|-------------------------------------|--------------------------|------------------------|
| `d5304a4` | `backend/api/routers/inbox.py` | `backend/api/routers/inbox.py` | ✅ Datei vorhanden, **Diff offen** |
| `014db4a` | `backend/api/routers/graph.py` (Style) | dito | ✅ Datei vorhanden, **Diff offen** |
| `1b0a025` | `backend/api/routers/inbox.py` (Style) | dito | ✅ Datei vorhanden, **Diff offen** |
| `4251bc9` | `backend/api/routers/inbox.py`, `backend/models/schemas.py`, `frontend/src/components/inbox/InboxItemRow.svelte` | dito + `frontend/...` → danwa-studio | **Backend-Diff offen**, Frontend-Diff offen |
| `914df02` | `tests/backend/test_tags.py` | `tests/backend/test_tags.py` | ❌ danwa-core hat kein `tests/` |
| `0312b17` | `frontend/src/views/WorkspaceView.svelte` | — (User-Facing bleibt hier) | bleibt danwa |
| `f64f997` | `backend/api/routers/tags.py` | dito | ✅ Datei vorhanden, **Diff offen** |
| `5c3abd1` | `backend/api/routers/tags.py`, `backend/models/tag.py`, `frontend/src/views/InboxView.svelte` | dito + danwa-studio | **Backend-Diff offen**, Frontend-Diff offen |
| `470e6ff` | `backend/api/routers/inbox.py`, `backend/models/schemas.py`, `frontend/src/components/inbox/InboxItemRow.svelte`, `frontend/src/lib/sse.js`, `frontend/src/views/DebateView.svelte`, `frontend/src/views/InboxView.svelte` | dito + danwa-studio | **Backend-Diff offen**, **Frontend-Libs fehlen in studio** |
| `1ed740d` | `backend/api/routers/workspace.py`, `backend/models/schemas.py` | dito | ✅ Dateien vorhanden, **Diff offen** |
| `12f2f60` | `.pre-commit-config.yaml`, `backend/services/llm_activity.py`, 2 Test-Dateien | dito + tests | **Backend-Diff offen**, Tests offen |
| `459690e` | 2 Test-Dateien (ruff-Lint) | `tests/rag_regression/` | ❌ danwa-core hat kein `tests/` |
| `d268d12` | `tests/rag_regression/test_llm_activity_end_call_on_cancel.py` | dito | ❌ |
| `6c94615` | `backend/services/llm_activity.py`, `backend/services/llm_service.py`, `backend/services/output/plugins/mimo_tts_renderer.py`, `backend/workflow/workflow_runner.py` | dito | ✅ alle Dateien vorhanden, **Diff offen** |
| `2b8bf7f` | `backend/api/routers/workflow_exec.py`, `tests/rag_regression/test_mvp_debate_passes_dms_project_id.py` | dito + tests | **Backend-Diff offen**, Tests offen |
| `aea9e74` | `backend/migrations/v024_rag_project_id_dedup.py` | `backend/migrations/v024_*.py` | ❌ **Datei fehlt komplett in danwa-core** |
| `3571c53` | `backend/services/dms/service.py`, `tests/rag_regression/test_rag_scope_id_regression.py` | dito + tests | **Backend-Diff offen**, Tests offen |
| `7876975` | `tests/backend/test_workspace_router.py` | `tests/backend/` | ❌ |
| `6c38be8` | `backend/api/routers/workspace.py`, 2 Test-Dateien | dito + tests | **Backend-Diff offen**, Tests offen |
| `3dca790` | 2 Test-Dateien | `tests/backend/` + `tests/rag_regression/` | ❌ |
| `c818b0b` | `tests/rag_regression/test_translation_service_init.py` | dito | ❌ |
| `fff6d8f` | `backend/services/translation_service.py`, `tests/rag_regression/test_translation_service_init.py` | dito + tests | **Backend-Diff offen**, Tests offen |

**Zusammenfassung danwa-core:** 21 Backend-Commits zu übernehmen, davon:
- **10 Commits reiner Backend-Code** → `git cherry-pick` direkt in `danwa-core`
- **9 Commits mit Tests** → Tests-Verzeichnis fehlt in `danwa-core`, muss **zuerst** komplett migriert werden (separater Task)
- **1 Commit mit Migration** (`aea9e74`) → `v024_rag_project_id_dedup.py` existiert noch gar nicht in danwa-core → Migration komplett übernehmen
- **1 Commit pyproject/version/changelog** → wird bei Release-Schritt in danwa-core übernommen

### 1b.2 → danwa-studio (Frontend-Libs)

| Commit | Geänderte Dateien | Zielpfad | Bereits in studio? |
|--------|-------------------|----------|--------------------|
| `4130867` | `frontend/src/lib/sse.js`, `frontend/src/lib/workflowPipelineAdapter.svelte.js`, `frontend/src/views/InboxView.svelte` | `src/lib/sse.js`, `src/lib/workflowPipelineAdapter.svelte.js`, `src/views/InboxView.svelte` | ❌ Libs fehlen, View fehlt |
| `470e6ff` | `frontend/src/components/inbox/InboxItemRow.svelte`, `frontend/src/lib/sse.js`, `frontend/src/views/DebateView.svelte`, `frontend/src/views/InboxView.svelte` | dito | ❌ alles fehlt (außer evtl. `InboxItemRow`) |
| `4251bc9`, `5c3abd1` | Frontend-Anteile davon | dito | ❌ |

**Zusammenfassung danwa-studio:** 4 Frontend-Commits mit Lib-Anteilen zu übernehmen. **Voraussetzung:** Die betroffenen Lib-Dateien müssen zuerst ins studio-Repo kopiert werden (siehe §1a Tabelle „Was fehlt").

### 1b.3 → danwa (User-Facing bleibt)

| Commit | Datei | Anmerkung |
|--------|-------|-----------|
| `cd7f4a0` | `frontend/src/views/BrowseView.svelte` | Reines User-Facing-Routing-Fix |
| `4f71d10` | `frontend/src/views/BrowseView.svelte` | dito |
| `0312b17` | `frontend/src/views/WorkspaceView.svelte` | Cross-Tenant-Fix, User-Facing |
| `6d753d3` | `frontend/src/components/Header.svelte`, `frontend/src/components/debate/DebateActivityLog.svelte`, `frontend/src/views/MvpDebateView.svelte` | UI-Cleanup, User-Facing |
| `b5838f8` | `frontend/vite.config.js`, `tests/frontend/test_vite_optimizedeps_regression.py` | vite-Optimierung, bleibt danwa; Test bleibt danwa |

### 1b.4 Reihenfolge der Pending-Fix-Übernahme

1. **Vor jeder danwa-Migration (Phase 2):** Pending Fixes übernehmen, sonst gehen sie verloren, wenn z.B. `InboxView.svelte` aus danwa gelöscht wird.
2. **Empfohlene Reihenfolge:**
   1. `danwa-core` Backend-Diffs übernehmen (10 Commits via Cherry-Pick oder Diff-Patch)
   2. `danwa-core` `tests/`-Verzeichnis von danwa migrieren (separater Task, siehe §1b.5)
   3. `aea9e74` (v024-Migration) sicherstellen — diese muss **vor** jedem Datenbank-Update in danwa-core aktiv sein
   4. `danwa-studio`: fehlende Lib-Dateien aus danwa kopieren (`sse.js`, `workflowPipelineAdapter.svelte.js`, ggf. `elk-service.js`, `blueprint/*`)
   5. `danwa-studio`: Frontend-Diffs der 4 Commits übernehmen
   6. Erst **danach** in `danwa` die User-Facing-Migration beginnen

### 1b.5 Offene Frage: Tests in danwa-core

`danwa-core` hat **kein** `tests/`-Verzeichnis. Das bedeutet:
- Entweder werden Tests **nie** in danwa-core migriert (CI läuft weiter in `danwa`)
- Oder die Tests müssen komplett als **eigener Commit** nach danwa-core überführt werden, bevor Backend-Cherry-Picks mit Test-Änderungen sinnvoll sind

**Empfehlung:** Separater Plan + Commit für „Tests nach danwa-core migrieren" — nicht Teil dieses Migrationsplans.

---

## 2. Vorgehen

- **Branch:** `feat/phase2-user-facing-only` (alles auf einem Branch)
- **Commit-Strategie:** Ein Commit pro logischer Migrationseinheit (Liste unten in §6)
- **Kein Push/Merge ohne User-Freigabe**

---

## 3. Mapping: Aktuelle Route → Zielzustand

Quelle: [`frontend/src/App.svelte`](../../frontend/src/App.svelte) Z. 102–160, [`frontend/src/components/Sidebar.svelte`](../../frontend/src/components/Sidebar.svelte) Z. 62–138.

| Aktuelle Route | Aktueller View | Aktion | Begründung |
|----------------|----------------|--------|------------|
| `dashboard` | `views/Dashboard.svelte` | **Behalten** | User-Facing: Projektübersicht, letzte Debatten |
| `debate` | `views/DebateView.svelte` | **Behalten** | Kern-Feature |
| `documents` | `views/DocumentsView.svelte` | **Behalten** | User-Facing: Dokumente pro Case |
| `archive` | `views/ArchiveView.svelte` | **Behalten** | User-Facing: Eigene vergangene Debatten |
| `audit` | `views/AuditView.svelte` | **Behalten** (Read-only) | User darf eigene Debatte nachvollziehen |
| `mvp-debate` | `views/MvpDebateView.svelte` | **Behalten** | MVP-Debatte ist User-Facing |
| `workspace` | `views/WorkspaceView.svelte` | **Behalten** | Startscreen für User |
| `case-list` | `views/CasesView.svelte` | **Behalten** | User wählt Case |
| `tags` | `views/TagManagerView.svelte` | **Behalten** | User-Tag-Verwaltung (eigene Tags) |
| `profile` | `views/ProfileView.svelte` | **Behalten** | User-Profil |
| `my-keys` | `views/BYOKManager.svelte` | **Behalten** | BYOK pro User |
| `login` | `views/LoginView.svelte` | **Behalten** | Auth-Flow |
| `browse` | `views/BrowseView.svelte` | **Behalten** | User-Facing: Browse Cases? (siehe §7 offene Punkte) |
| `inbox` | `views/InboxView.svelte` | **Behalten** | User-Inbox für HITL-Requests etc. |
| `config` | `views/ConfigView.svelte` | **Entfernen** | Nur Studio (LLM-Profile, Agents, Prompts) |
| `manage` | `views/ManageView.svelte` | **Entfernen** | Nur Studio (LLM-Profile, Workflow-Templates-Editor) |
| `blueprint` | `views/BlueprintCanvasView.svelte` | **Entfernen** | Visueller Workflow-Editor → Studio |
| `bundle-composer` | `views/BundleComposerView.svelte` | **Entfernen** | Bundle-Erstellung → Studio |
| `replay` | `views/ReplayView.svelte` | **Entfernen** | Replay mit Timeline → Studio |
| `diff` | `views/DiffView.svelte` | **Entfernen** | Debate-Vergleich → Studio |
| `output` | `views/OutputComposerView.svelte` | **Entfernen** | Output-Composer → Studio |
| `input` | `views/InputComposerView.svelte` | **Entfernen** | Input-Composer → Studio |
| `translation` | `views/TranslationDashboard.svelte` | **Entfernen** | i18n-Management → Studio |
| `modules` | `views/ModulesView.svelte` | **Entfernen** | Module-Registry → Studio |
| `proposals` | `views/ProposalsView.svelte` | **Entfernen** | HITL-Vorschläge → Studio |
| `users` | `views/UserManagement.svelte` | **Entfernen** | Admin-only |
| `tenant-settings` | `views/TenantSettingsView.svelte` | **Entfernen** | Admin-only |
| `server-health` | `views/ServerHealthView.svelte` | **Entfernen** | Admin-only |
| `execution` | `views/WorkflowExecutionView.svelte` | **Entfernen** | Workflow-Exec-Panel → Studio. **Wichtig:** `DebateView` muss die aktive Session selbst anzeigen können — siehe §5.3 |

---

## 4. Komponenten-Mapping (`frontend/src/components/`)

### 4.1 Komplett entfernen (Studio-only oder mit Views gelöscht)

```
components/blueprint/                    # Blueprint-Editor + Workflow-Canvas
components/config/                       # LLM-/Agent-/Prompt-Konfig
components/hitl/                         # HITL-Editor-Panels
components/inbox/                        # InboxItemRow — prüfen ob von InboxView genutzt
components/input/                        # Input-Plugins
components/manage/                       # LLM-/Persona-/Workflow-Listen
components/output/                       # Output-Plugins
components/workflow/                     # Workflow-Canvas (Exec)
components/AuditTrailVisualization.svelte # gehört zu Audit/Studio
components/ModuleManager.svelte          # Module-Liste
```

**Vor jedem Löschen:** Suche alle `import`-Statements der Komponente und prüfe, ob sie noch in einem der behaltenen Views verwendet wird. Siehe §5 für die Impact-Analyse.

### 4.2 Behalten

```
components/AssistantChat.svelte
components/assistant/                    # Assistant-Chat (User-Facing)
components/AuditTrail.svelte
components/CaseNavigator.svelte
components/CaseSelector.svelte
components/ConfirmDialog.svelte
components/ConsensusPanel.svelte
components/DebateTimeline.svelte
components/DocumentUploader.svelte
components/Header.svelte
components/LanguageSwitcher.svelte
components/Layout.svelte
components/MarkdownRenderer.svelte
components/QuotaIndicator.svelte
components/Sidebar.svelte                # Wird INHALTlich entschlackt (siehe §5.4)
components/TagPicker.svelte
components/TenantSelector.svelte
components/ToastContainer.svelte
components/WorkflowGraph.svelte          # Nur Read-only, kein Edit
components/case-space/                   # Cytoscape-Graph — User-Facing
components/debate/                       # Debate-UI-Komponenten (alle behalten)
components/feedback/                     # StatusBar, ErrorPanel, ActivityLogPanel
components/onboarding/WelcomeCard.svelte
```

**Kandidaten für `case-space/`:** Siehe §7 — prüfen, ob alle Sub-Komponenten noch gebraucht werden.

### 4.3 Genauer zu prüfen

- `components/case-space/InspectorGraphTab.svelte` — nutzt das Case-Inspector etwas, das nur in Studio lebt?
- `components/debate/DebateCreatePanel.svelte` — nutzt `workflowExec` + `blueprint/api.listWorkflowDefinitions` → bleibt drin (Startet Workflows)

---

## 5. Lib-Mapping (`frontend/src/lib/`) — Impact-Analyse

### 5.1 Klar Studio-only (komplett entfernbar)

| Pfad | Verwendet von | Aktion |
|------|---------------|--------|
| `lib/blueprint/*` (alle 13 Dateien) | nur `BlueprintCanvasView`, `BundleComposerView`, `InputComposerView` (nur `listWorkflowTemplates`), `ManageView`, `ModulesView` | **Entfernen** |
| `lib/input/*` (3 Dateien) | nur `InputComposerView` | **Entfernen** |
| `lib/hitl.js` | Hits via grep — keine View importiert (vermutlich dead code) | **Entfernen** |
| `lib/stores/hitl.svelte.js` | Hits via grep — keine View importiert (vermutlich dead code) | **Entfernen** |
| `lib/api/backup.js` | nur `lib/api.js` Re-Export — kein direkter Import in Views | **Entfernen** |
| `lib/api/settings.js` | nur `lib/api.js` Re-Export — kein direkter Import in Views | **Entfernen** |
| `lib/api/graph.js` | nur `lib/stores/graphStore.svelte.js` — der wiederum von keiner View importiert wird (prüfen) | **Entfernen, wenn graphStore tot** |
| `lib/stores/graphStore.svelte.js` | Hits via grep prüfen | **Entfernen, wenn tot** |

### 5.2 Bleibt drin (User-Facing)

| Pfad | Verwendet von |
|------|---------------|
| `lib/api.js` | sehr viele Views (Re-Export-Fassade) |
| `lib/api/auth.js`, `debate.js`, `document.js`, `case.js`, `i18n.js`, `inbox.js`, `module.js`, `onboarding.js`, `profile.js`, `project.js`, `session.js`, `tag.js`, `workspace.js` | direkte Imports in Views/Komponenten — **vor Entfernen jedes Moduls prüfen** |
| `lib/auth.js` | Auth-Flow (LoginView, App.svelte) |
| `lib/sse.js` | SSE für Debatten |
| `lib/stores.js` | Globaler State (App.svelte, viele Views) |
| `lib/stores/auth.svelte.js` | Auth |
| `lib/stores/feedback.svelte.js` | `DebateView` |
| `lib/stores/inboxStore.svelte.js` | `Sidebar`, `InboxView` |
| `lib/stores/newDebateFlow.svelte.js` | `DebateCreatePanel`? — prüfen |
| `lib/stores/phaseSnapshotsStore.svelte.js` | `DebateView`? — prüfen |
| `lib/stores/workspaceStore.svelte.js` | `WorkspaceView` |
| `lib/transcriptNormalizer.js` | `components/workflow/...` und `components/blueprint/...` — User-Versionen müssen bleiben, Blueprint-Versionen weg |
| `lib/elk-service.js` | nur `BlueprintCanvasView` → **Entfernen** |
| `lib/a2aApi.js` | A2A-Plugin in User-Flows? — prüfen |
| `lib/workflowPipelineAdapter.svelte.js` | `Dashboard.svelte`, `WorkflowGraph.svelte` → **Behalten** |

### 5.3 Grauzone: `lib/workflow/`, `lib/workflowExec.js`, `lib/workflowSession.js`, `lib/workflowSSE.js`

Diese werden **auch** von User-Views genutzt:

- `Dashboard.svelte` → `workflowPipelineAdapter` (letzter Pipeline-View)
- `DebateView.svelte` → `workflow/mapper.js` (SSE-Eventmapping), `workflow/store.svelte.js`
- `WorkflowGraph.svelte` → `workflowPipelineAdapter`
- `Sidebar.svelte` → `workflowSession.js` (für Badge "Live Execution")
- `DebateCreatePanel.svelte` → `workflowExec.startWorkflow`
- `MvpDebateView.svelte` → `workflowExec`, `workflowSSE`

**Konsequenz:** Diese Lib-Files werden **nicht** entfernt. Sie sind User-Facing-Infrastruktur für Workflow-Visualisierung und -Start.

### 5.4 Sidebar (`components/Sidebar.svelte`) entschlacken

Aktuell 5 Sektionen + Admin-Sektion. Neu:

```js
// navSections — nur User-Facing
[
  {
    id: 'start',
    label: t('nav.section.start'),
    items: [
      { route: 'workspace' },
      { route: 'case-list' },
      { route: 'tags' },
    ],
  },
  {
    id: 'work',
    label: t('nav.section.work'),
    items: [
      // aktive Debatte (conditional)
      // aktive Execution (conditional)
      { route: 'mvp-debate' },
      { route: 'documents' },
      { route: 'archive' },
    ],
  },
  {
    id: 'results',
    label: t('nav.section.results'),
    items: [
      { route: 'audit' },
    ],
  },
  {
    id: 'account',
    label: t('nav.section.account'),
    items: [
      { route: 'profile' },
      { route: 'my-keys' },
      { route: 'inbox' },
      { route: 'browse' },
    ],
  },
]
```

**Hinweis:** Die `inhabit`-Sektion in der aktuellen Sidebar enthält auch `tenant-settings` → wird für Admin-User ausgeblendet, weil Admin→`/studio` (in einer späteren Phase). Für jetzt: `tenant-settings` einfach aus der Sidebar entfernen.

---

## 6. Commit-Reihenfolge

### Phase 0a — Pending Fixes in externe Repos übernehmen (VOR Phase 0/1)

Diese Commits sichern, dass keine Backend- oder Studio-relevanten Fixes verloren gehen, wenn danwa später ausgemistet wird. Reihenfolge wie in §1b.4.

| # | Repo | Aktion | Commit-Nachricht-Vorschlag |
|---|------|--------|----------------------------|
| 0a.1 | `danwa-core` | Tests-Verzeichnis `tests/{backend,rag_regression}` komplett kopieren (separater Plan) | `chore: migrate tests/ from danwa monorepo` |
| 0a.2 | `danwa-core` | Backend-Diffs der 10 reinen Backend-Commits cherry-picken / patchen | `fix: cherry-pick inbox/tags/workspace/graph/llm_activity fixes from danwa` |
| 0a.3 | `danwa-core` | `aea9e74` Migration `v024_rag_project_id_dedup.py` übernehmen | `fix(migration): v024 also rewrites SQLite documents table` |
| 0a.4 | `danwa-core` | pyproject.toml + version + CHANGELOG bump für die Übernahmen | `chore(release): v0.3.1-post-baseline` |
| 0a.5 | `danwa-studio` | Fehlende Libs kopieren: `sse.js`, `workflowPipelineAdapter.svelte.js`, ggf. `elk-service.js`, `blueprint/*` aus `danwa/frontend/src/lib/` | `chore: copy missing frontend libs from danwa` |
| 0a.6 | `danwa-studio` | Frontend-Diffs der 4 Commits (`4130867`, `470e6ff`, `4251bc9` Frontend-Anteil, `5c3abd1` Frontend-Anteil) cherry-picken | `fix: cherry-pick inbox/sse/workflow-pipeline fixes from danwa` |

**Verifikation nach Phase 0a:** `danwa-core` `uv run pytest tests/` grün; `danwa-studio` `npm run build` grün; manueller Smoke-Test des Studio-Workflow-Exec.

### Phase 1–11 — danwa User-Facing-Migration

Jeder Commit ist **eigenständig lauffähig** (`npm run build` + `npm run dev` funktionieren nach jedem Commit). Reihenfolge nach Risiko (niedrig → hoch):

| # | Commit | Inhalt | Risiko |
|---|--------|--------|--------|
| 1 | `chore(frontend): remove input composer views and components` | `views/InputComposerView.svelte`, `components/input/` | niedrig |
| 2 | `chore(frontend): remove output composer views and components` | `views/OutputComposerView.svelte`, `components/output/` | niedrig |
| 3 | `chore(frontend): remove blueprint canvas view and components` | `views/BlueprintCanvasView.svelte`, `components/blueprint/`, `lib/blueprint/`, `lib/elk-service.js` | mittel (Touches viele Imports) |
| 4 | `chore(frontend): remove bundle composer` | `views/BundleComposerView.svelte` | niedrig |
| 5 | `chore(frontend): remove modules view and translation dashboard` | `views/ModulesView.svelte`, `views/TranslationDashboard.svelte`, `components/ModuleManager.svelte` | niedrig |
| 6 | `chore(frontend): remove config, manage and proposals views` | `views/ConfigView.svelte`, `views/ManageView.svelte`, `views/ProposalsView.svelte`, `components/config/`, `components/manage/` | mittel |
| 7 | `chore(frontend): remove diff, replay and execution views` | `views/DiffView.svelte`, `views/ReplayView.svelte`, `views/WorkflowExecutionView.svelte`, `components/workflow/` | mittel — **Workaround**: `DebateView` muss aktive Execution selbst darstellen, sonst hat der User keinen Live-View. **Alternative:** `ExecutionPanel` und `DebateExecutionDisplay` bleiben, aber `WorkflowExecutionView` wird entfernt und die Execution wird inline in `DebateView` gemountet (siehe §7 offene Punkte). |
| 8 | `chore(frontend): remove admin views` | `views/UserManagement.svelte`, `views/TenantSettingsView.svelte`, `views/ServerHealthView.svelte` | niedrig |
| 9 | `chore(frontend): reduce sidebar to user-facing items` | `components/Sidebar.svelte` (Sektionen-Array), zugehörige i18n-Keys | mittel (UI-regression-Risiko) |
| 10 | `chore(frontend): cleanup routing in App.svelte` | `App.svelte` (entfernte Routes raus), `lib/stores.js` (Stores für entfernte Features), `lib/api.js` (Re-Exports) | mittel — Endgültige Konsolidierung |
| 11 | `docs(frontend): update README/CLAUDE.md for slimmed app` | User-Facing-Beschreibung, Sidebar-Doku, "In Studio öffnen"-Hinweis ergänzen (statisch, ohne Redirect-Logik) | niedrig |

**Test:** Nach jedem Commit `npm run build` und manueller Smoke-Test der Sidebar.

---

## 7. Offene Punkte (vor Beginn zu klären)

| # | Frage | Optionen | Empfehlung |
|---|-------|----------|------------|
| A | **`AuditTrailVisualization.svelte`** — wo wird sie genutzt? | Bleibt in `components/`, möglicherweise in `AuditView`. | Suche prüfen. Wenn nur in `AuditView` → behalten. |
| B | **`case-space/CytoscapeGraphView.svelte`** und **`InspectorGraphTab.svelte`** — nutzt eine User-View das? | Bleiben drin oder weg, je nach View-Nutzung. | Vor Commit 11 prüfen. |
| C | **Workflow-Exec-Anzeige:** Was passiert mit "Live Execution"-Badge in Sidebar und der Anzeige während einer laufenden Debatte, wenn `ExecutionPanel` weg ist? | (a) `ExecutionPanel` + `DebateExecutionDisplay` nach `components/debate/` verschieben und in `DebateView` einbetten. (b) Nur Badge in Sidebar behalten, aber keine separate Exec-View — `DebateView` zeigt stattdessen den Standard-Transcript. | (a), weil der User aktuell Live-Updates gewohnt ist. |
| D | **`InboxView`** — bleibt sie in danwa oder wandert sie nach Studio? | Plan §3.1 zeigt `Inbox` nicht in danwa-Sidebar. Aber `components/debate/` nutzen HITL → User braucht Inbox. | **In danwa behalten** als User-Facing-Konto-Feature. |
| E | **`BrowseView`** — was tut sie? | Unklar, Name deutet auf globale Browse-Suche. | Vor Commit 9 prüfen, ob sie in User-Sidebar Sinn ergibt. |
| F | **`components/workflow/`** komplett weg oder nur der Exec-Teil? | Es enthält `WorkflowCanvas`, `DiffNodeDetail`, `ReplayNodeDetail`, `ReplayControls`, `PhasesTab`, `SessionAuditTab` etc. | Nur die Exec/Edit-Komponenten weg (`WorkflowCanvas`, `Pipeline*`, `*Edge*`). `SessionAuditTab` eventuell behalten für `AuditView`. |
| G | **`lib/stores/graphStore.svelte.js`** und **`lib/api/graph.js`** — tot oder lebendig? | Aus den Grep-Ergebnissen nicht klar. | Vor Commit 10 prüfen. |
| H | **`TenantSelector`** — User wählt Tenant? Eigentlich Admin-Feature. | Bleibt drin, solange Single-Tenant-Setup nicht erzwungen wird. | Behalten, kein Plan-Impact. |
| I | **Test-Suite:** `frontend/tests/` — gibt es E2E-Tests, die entfernte Routen testen? | Vermutlich ja (Playwright-Snapshots). | Vor Commit 1 grep auf Test-Dateien, die entfernte Views importieren. |

---

## 8. Was bewusst NICHT in diesem Plan enthalten ist

- **Shared-Package-Integration** (`@danwa/api-client`, `@danwa/ui-core`, `@danwa/i18n`) — Phase 0/1 des Originalplans, gehört zu danwa-studio-Aufbau.
- **Auth-Guard mit Rolle→Redirect** (`admin` → `/studio`) — kommt mit Shared Packages.
- **Auth-Token-Migration** zu Studio — Phase 4.
- **Entfernen der Core-i18n-Loader für 14 Sprachen** (`profiles/argumentation-patterns/*/DEPRECATED.txt`) — Backend/Daten-Migration, nicht Frontend.
- **Backend-Code in `src/`, `backend/`, `scripts/`** — bleibt unverändert. gehört zu `danwa-core`.
- **`profiles/`-Verzeichnis** — gehört zu `danwa-modules`.
- **`modules/`-Verzeichnis** — gehört zu `danwa-modules`.
- **`deploy/`-Config** — wird in Phase 4 (Deployment) angefasst.
- **Tests-Migration von `danwa/tests/` nach `danwa-core/tests/`** — erwähnt in §1b.5 als separater Task, nicht Teil dieser Phase-0a-Commits.

---

## 9. Risiken & Gegenmaßnahmen

| Risiko | Wahrscheinlichkeit | Impact | Gegenmaßnahme |
|--------|-------------------|--------|----------------|
| **Versteckter Cross-Import** — eine als User-Feature eingestufte View importiert versehentlich aus zu entfernendem Lib-Code | mittel | Build bricht | Nach jedem Commit `npm run build`. Bei Fehler: Import prüfen, entweder View → Studio verschieben oder Lib-Funktion in verbleibende Lib übernehmen. |
| **i18n-Keys fehlen** für neue Sidebar-Sektionen | mittel | UI zeigt Fallback-Text | Vor Commit 9: neue Keys (`nav.section.start`, `nav.section.work`, `nav.section.results`, `nav.section.account`) in `lib/i18n/loaders/en.js` ergänzen. |
| **Tests brechen** | hoch | CI rot | Vor Commit 1: `frontend/tests/` scannen, betroffene Tests löschen oder in `.skip` setzen. |
| **Bundle-Size schrumpft nicht wie erhofft** (`< 200 KB gzipped`) | mittel | Plan-Erfolgskriterium verfehlt | Erwartung: Schon das Entfernen von Blueprint (≈ 30 Nodes, 12 Edges, 12 Forms, viele Panels) reduziert Bundle deutlich. Verifikation per `vite build --mode analyze` (rollup-plugin-visualizer). |
| **`DebateView` verliert Live-Visualisierung** wenn `ExecutionPanel` weg | mittel | UX-Regression | §7 Punkt C: `ExecutionPanel` als interne Komponente von `DebateView` einbetten, nicht löschen. |
| **Local-Dev-Bruch** weil API-Endpoints aus den zu entfernenden Libs (`/api/v1/modules/...`) vom Backend erwartet werden | niedrig | Frontend-Build ok, aber Runtime-Fehler | `vite.config.js` Proxy unverändert lassen — Backend (`danwa-core`) bleibt erreichbar. Endpoints einfach nicht mehr aufrufen. |

---

## 10. Erfolgskriterien

### Phase 0a (Pending Fixes)

| Kriterium | Messbar |
|-----------|---------|
| Alle 21 Backend-Commits nach `danwa-core` übernommen | `git log danwa-core` zeigt Commits oder Diff-Anwendung verifiziert |
| `aea9e74`-Migration `v024_rag_project_id_dedup.py` in danwa-core vorhanden | `find danwa-core -name "v024_rag*"` findet die Datei |
| `danwa-studio` hat `sse.js` + `workflowPipelineAdapter.svelte.js` | `ls danwa-studio/src/lib/` |
| `danwa-studio` `npm run build` grün | ✅ |
| `danwa-core` `uv run pytest tests/` grün (nach separater Test-Migration) | ✅ |

### Phase 1–11 (danwa User-Facing)

| Kriterium | Messbar |
|-----------|---------|
| `npm run build` erfolgreich nach jedem Commit | ✅ |
| Sidebar zeigt nur noch 4 Sektionen (START, ARBEITEN, ERGEBNISSE, KONTO) | ✅ |
| `git grep "from.*lib/blueprint"` → keine Treffer im Frontend | ✅ |
| `git grep "from.*lib/input"` → keine Treffer im Frontend | ✅ |
| `git grep "from.*lib/hitl"` → keine Treffer im Frontend | ✅ |
| Bundle-Size messbar reduziert (vorher vs. nachher) | ✅ via `vite build` Output |
| Bestehende User-Workflows (Login → Dashboard → Debatte starten → Audit ansehen) weiterhin funktional | ✅ manueller Smoke-Test |

---

## 11. Nicht-Ziele

- Refactoring der verbleibenden Lib-Struktur
- Styling-Cleanup
- Performance-Optimierung
- Neue Features
- Backend-Änderungen
