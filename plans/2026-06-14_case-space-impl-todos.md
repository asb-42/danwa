# Implementation TODO: Case-Space Workspace

> Gehört zu: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md)
> Status: Phase 0–5 implementiert, Phase 6 ausstehend (Rollout, i18n-Vervollständigung, Doku, Telemetrie)
> Sprache: Deutsch (für Konsistenz mit dem Konzeptdokument)
> Schrittgröße: jede Checkbox ist ein in sich geschlossenes Inkrement

> ℹ️ **Sync-Hinweis (2026-06-15)**: Diese Liste wurde mit dem realen Code-Stand des `main`-Branches synchronisiert.  Viele Items standen bereits auf `[x]`, waren im Code aber noch nicht abgeschlossen (bzw. umgekehrt).  Der aktuelle Stand reflektiert `main` inkl. Commits `7f52e96` (3.6 Backend) und `cb3bd85` (3.6 Frontend).  Stand-Tests: **41 Pytest + 61 Vitest** grün.

---

## Phase 0 — Vorbereitung (vor P1)

- [ ] **0.1 Konzept-Readout** mit Stakeholdern terminieren — *außerhalb des Code-Scopes* (organisatorisch) (Doku: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md))
- [x] **0.2 Feature-Flag-System** in [`backend/core/config.py:117-145`](../../backend/core/config.py:117) angelegt (drei Flags: `enable_case_space`, `enable_case_space_inbox`, `enable_case_space_graph`)
- [x] **0.3 Frontend-Routing**: bestehende SvelteKit-/Vite-Routes geprüft — *das Projekt nutzt Hash-Routing*; Routen `workspace`, `inbox`, `browse` in [`App.svelte:152-157`](../../frontend/src/App.svelte:152) registriert
- [x] **0.4 Sidebar-Komponente** Stand aufgenommen — Refactor für Badge-Support bei 2.10 erfolgt (generische `badge`-Property auf Nav-Items)
- [x] **0.5 Datenmodell-Readback** bestätigt — `case.tag_ids` / `case.debate_ids` / `case.document_ids` / `case.members` via defensive `getattr` (dokumentiert in D1)
- [x] **0.6 i18n-Keys** pragmatisch: alle Texte nutzen das Pattern `t?.caseSpace?.workspace?.title ?? 'Workspace'` mit englischen Fallbacks.  Eigene Locale-File-Updates sind ein optionales P6+ Polish-Item.
- [x] **0.7 Test-Fixture** — ad-hoc via `fake_case_store` / `fake_store` in [`tests/backend/test_workspace_router.py`](../../tests/backend/test_workspace_router.py) und [`test_inbox_router.py`](../../tests/backend/test_inbox_router.py)

## Phase 1 — Workspace-Hauptansicht (P1)

### Backend
- [x] **1.1 Endpoint `GET /api/workspace/summary?case_id=…`** in [`backend/api/routers/workspace.py`](../../backend/api/routers/workspace.py) angelegt
  - [x] 1.1.1 Query-Param-Validierung (FastAPI Query)
  - [x] 1.1.2 Aggregation: Case + debate_count + document_count + suggested_next_steps
  - [x] 1.1.3 Permission-Check: delegiert an `case_store.get` (tenant-scoped lookup)
  - [x] 1.1.4 Response-Schema in [`backend/models/schemas.py`](../../backend/models/schemas.py) (`WorkspaceSummary`)
  - [x] 1.1.5 **Bugfix (Commit `f0b13d1`)**: `store.get(case_id)` → `store.get(tenant_id, case_id)` (P1-Bug, gefixt)
  - [x] 1.1.6 **Phase 3.6 Backend (Commit `7f52e96`)**: Helper `_collect_recent_audit_events()` aggregiert die letzten 5 Audit-Events aller Debates des Cases via Workflow-Audit-Logger
- [x] **1.2 Endpoint `GET /api/cases/search?q=…`** (Typeahead) — in 1.1 mit-umgesetzt
  - [x] 1.2.1 Limit default 10, max 50, via `Query(ge=1, le=50)`
  - [x] 1.2.2 Permission-Filter: `case_store.list_by_tenant()` (tenant-scoped)
  - [x] 1.2.3 OpenAPI-Doc via FastAPI Field descriptions
- [x] **1.3 User-Setting `last_workspace`** — **Schema-Abweichung vom Plan**: implementiert als eigene Spalte `last_workspace TEXT` in `users`-Tabelle (Commit `0aef288`), nicht als `user.settings` JSON-Field.  API-kontraktisch identisch zum Plan.
  - [x] 1.3.1 Migration/Default: leerer String
  - [x] 1.3.2 PATCH-Endpunkt zum Aktualisieren — [`PUT /api/v1/auth/me/last-workspace`](../../backend/api/routers/auth.py:181)
  - [x] **Bugfix (Commit `55440a2`)**: Hardening des Write-Pfads, graceful graph tab
- [x] **1.4 Tests** (Pytest) in [`tests/backend/test_workspace_router.py`](../../tests/backend/test_workspace_router.py) — 10 Tests, alle grün

### Frontend
- [x] **1.5 Store `workspaceStore.svelte.js`** in [`frontend/src/lib/stores/`](../../frontend/src/lib/stores/) angelegt
  - [x] 1.5.1 State: `summary`, `loading`, `error`, plus `activeCaseId`, `searchResults`, `searchQuery`, `searchLoading`, `caseSpaceDisabled`
  - [x] 1.5.2 Actions: `setActiveCase(id)`, `loadSummary()`, `search(q)`, `invalidate(caseId)`, `reset()`
  - [x] 1.5.3 Dedup via `Map<caseId, Promise>`, debounce 200 ms für Typeahead
- [x] **1.6 API-Wrapper** [`frontend/src/lib/api/workspace.js`](../../frontend/src/lib/api/workspace.js)
- [x] **1.7 Komponente `WorkspaceView.svelte`** in [`frontend/src/views/`](../../frontend/src/views/) angelegt (763 Zeilen)
- [x] **1.8 Komponente `CaseSelector.svelte`** mit Typeahead (200 ms debounce, gegen `searchCases`)
  - [x] Bonus: Typeahead schaltet sich automatisch ab wenn Feature-Flag off ist
  - [x] Bonus: Selektion spiegelt sich in `workspaceStore`
- [x] **1.9 URL-State-Synchronisation**: Query-Param `?case=…` lesen + schreiben via `URLSearchParams` + `history.replaceState`
  - [x] 1.9.1 Read in `onMount` (URL > prop precedence für Deep-Links)
  - [x] 1.9.2 Write via `$effect` auf `activeCaseId`
  - [x] 1.9.3 Browser back/forward via `popstate`-Listener
- [x] **1.10 Login-Default-Wiederherstellung**: `restoreLastWorkspace()` wird in [`WorkspaceView.svelte:180`](../../frontend/src/views/WorkspaceView.svelte:180) als Fallback der URL-Read-Kette (`URL > prop > restoreLastWorkspace`) aufgerufen.  Beim ersten Workspace-Besuch nach Login wird der zuletzt aktive Case automatisch gesetzt.
- [x] **1.11 Sidebar-Eintrag "Workspace"** in [`Sidebar.svelte:67`](../../frontend/src/components/Sidebar.svelte:67) hinzugefügt, *oberhalb* von tenant-settings in der inhabit-Section
- [x] **1.12 Routing** `workspace` als Hash-Route in [`App.svelte:152-153`](../../frontend/src/App.svelte:152) registriert
  - Default-Route bleibt Dashboard (bewusst: User-Feedback zur Pilotphase abwarten, dann P5+ entscheiden)
- [x] **1.13 Frontend-Tests** (Vitest) in [`frontend/tests/unit/workspaceStore.test.js`](../../frontend/tests/unit/workspaceStore.test.js) — 15 Tests, alle grün
- [ ] **1.14 E2E-Playwright-Test**: bewusst verschoben auf Folge-Session (Aufwand ~2 h, kein CI-Pflicht, siehe 2.12)
- [x] **1.15 Lint + Format**: `ruff check .` und `ruff format --check .` clean
- [x] **1.16 Commit + Push**: in Commits `83173d0`, `306b73c`, `95f5139`, `cf0d283`, `c8af2d9`, `dc692a8`, `fa2d58d` und Merge-Commit `0b00eda` erfolgt

## Phase 2 — Inbox (P2)

### Backend
- [x] **2.1 Endpoint `GET /api/inbox?tenant_id=…`** in [`backend/api/routers/inbox.py`](../../backend/api/routers/inbox.py)
  - [x] 2.1.1 Untagged Debates (über alle Cases des Tenants aggregiert)
  - [x] 2.1.2 Recently Completed (Status="completed", completed_at ≥ now-7d)
  - [x] 2.1.3 Stale Running (Status="running", updated_at < now-24h, age_hours exposed)
  - [ ] 2.1.4 Unlinked Documents — **bewusst ausgelassen**: DMS hat aktuell keinen per-Case-Link; Use Case wandert in P3+ sobald DMS-Schema erweitert wird
  - [ ] 2.1.5 My Mentions — **bewusst ausgelassen**: audit_events-Schema hat noch keine `mentioned_user_id`-Spalte
  - [x] 2.1.6 Sortierung: neueste zuerst, Limit 50
- [x] **2.2 Bulk-Endpoints** in [`backend/api/routers/inbox.py:273-388`](../../backend/api/routers/inbox.py:273)
  - [x] 2.2.1 `POST /api/inbox/bulk-move`
  - [x] 2.2.2 `POST /api/inbox/bulk-tag` (idempotente Union)
  - [x] 2.2.3 `POST /api/inbox/bulk-archive`
- [x] **2.3 Permission-Regel**: cross-tenant Items landen in `InboxBulkResult.failed` mit `reason="cross_tenant: …"`
- [x] **2.4 Tests** (Pytest) in [`tests/backend/test_inbox_router.py`](../../tests/backend/test_inbox_router.py) — 14 Tests, alle grün

### Frontend
- [x] **2.5 Store `inboxStore.svelte.js`** in [`frontend/src/lib/stores/`](../../frontend/src/lib/stores/) angelegt (316 Zeilen)
- [x] **2.6 API-Wrapper** [`frontend/src/lib/api/inbox.js`](../../frontend/src/lib/api/inbox.js)
- [x] **2.7 Komponente `InboxView.svelte`** (452 Zeilen) — Tabs, Checkbox-Liste, Select-all-Bar, Bulk-Action-Bar
- [x] **2.8 Komponente `InboxItemRow.svelte`** in [`frontend/src/components/inbox/`](../../frontend/src/components/inbox/) extrahiert
- [x] **2.9 Inline-Action-Dropdowns** in Bulk-Bar: Move mit Typeahead, Tag mit debounced input
- [x] **2.10 Sidebar-Badge** mit `inboxStore.summary.items.length` in [`Sidebar.svelte:35-36,68`](../../frontend/src/components/Sidebar.svelte:35) implementiert
- [x] **2.11 Frontend-Tests** (Vitest) in [`frontend/tests/unit/inboxStore.test.js`](../../frontend/tests/unit/inboxStore.test.js) — 19 Tests, alle grün (TODO behauptet 17, tatsächlich 19)
- [ ] **2.12 E2E-Playwright**: bewusst verschoben auf Folge-Session
- [x] **2.13 Commit + Push** in Commits nach `0b00eda` erfolgt

## Phase 3 — Welcome + Onboarding-Feinschliff (P3)

### Backend
- [x] **3.1 Endpoint `GET /api/onboarding/state?tenant_id=…`** in [`backend/api/routers/onboarding.py`](../../backend/api/routers/onboarding.py) (Commit `9654efd`)
  - [x] 3.1.1 `has_cases` via `case_store.list_by_tenant`
  - [x] 3.1.2 `has_debates` Short-Circuit nach erstem Debate
  - [x] 3.1.3 `has_documents` immer False (DMS ist project-scoped, nicht tenant-scoped)
  - [x] 3.1.4 Best-effort: einzelne Store-Fehler werden geloggt und mit False übersprungen
- [ ] **3.2 Optionaler Endpoint `POST /api/documents/{id}/suggest-case`** (LLM): wenn ein LLM konfiguriert ist, Top-3-Vorschläge; sonst 404.  *Feature-Flag `DANWA_LLM_SUGGEST_CASES`*

### Frontend
- [x] **3.3 Komponente `WelcomeCard.svelte`** (192 Zeilen) — drei nummerierte Steps, in [`Dashboard.svelte:123`](../../frontend/src/views/Dashboard.svelte:123) eingebunden
  - [x] 3.3.1 Drei nummerierte Steps (Create Case / Upload Documents / Start Debate)
  - [x] 3.3.2 Sichtbar nur wenn `!has_cases`
  - [x] 3.3.3 Dismissable
  - [x] 3.3.4 In `Dashboard.svelte` am oberen Rand integriert
- [x] **3.4 Logik**: Welcome-Card rendert nur, wenn `state.has_cases === false` — in `WelcomeCard.svelte:50` als `$derived` `visible` implementiert
- [x] **3.5 Tag-Vorschläge im Picker** (Commit `2e78228`) — Top-3-Tags des aktuellen Cases als Quick-Buttons
  - [x] 3.5.1 Top-3-Tags des aktuellen Cases als Quick-Buttons
  - [x] 3.5.2 Vorschläge verschwinden, sobald der User Tags manuell wählt
- [x] **3.6 Inline-Audit im Inspector** (Commits `7f52e96` + `cb3bd85`)
  - [x] 3.6.1 Phase-Spalte (Badge)
  - [x] 3.6.2 Letzte 5 Events inline (5-Spalten-Tabelle: Event, Phase, Round, Subject, When)
  - [x] 3.6.3 "Show full audit" Link vorausgefüllt (mit Click-through zur Audit-View je Row)
- [x] **3.7 "New Debate"-Form** mit Pflicht-Case-Disambiguierung (Commit `e8006c7`)
  - [x] 3.7.1 Default = aktiver Case, falls vorhanden
  - [x] 3.7.2 Inline-Case-Erstellung mit Name + Tags — Mode-Toggle "Existing case" / "New case"
  - [x] 3.7.3 Tags-Selector mit Vorschlägen aus 3.5
  - [x] 3.7-Tests: [`tests/unit/newDebateFlow.test.js`](../../frontend/tests/unit/newDebateFlow.test.js) — 27 Tests, alle grün
- [x] **3.8 "Upload Document"-Form** mit Pflicht-Case-Selector (Commit `c04028a`)
  - [x] 3.8.1 Option "kein bestimmter Case" → Inbox
  - [x] 3.8.2 Validierung: `case_id` ODER expliziter Inbox-Wunsch
- [ ] **3.9 Frontend-Tests** für Welcome-Card (3.9.1) und Tag-Vorschläge (3.9.2) — nicht im Vitest-Set; Verifikation erfolgt via Component-Render
- [ ] **3.10 E2E**: Erstbenutzer-Flow → 3 Klicks → erste Debatte sichtbar
- [ ] **3.11 Commit + Push** — Commits `9654efd` (Backend), `2e78228` (3.5), `c04028a` (3.8), `e8006c7` (3.7), `7f52e96`+`cb3bd85` (3.6) erfolgt

## Phase 4 — Browse mit Graph-Toggle (P4)

### Backend
- [x] **4.1 Endpoint `GET /api/graph/global?tenant_id=…&limit=…`** in [`backend/api/routers/graph.py`](../../backend/api/routers/graph.py)
  - [x] 4.1.1 Limit default 200, max 500, via `Query(ge=1, le=GLOBAL_MAX_LIMIT)`
  - [x] 4.1.2 Subgraph-Aggregation mit harter Obergrenze
  - [x] 4.1.3 Bei Überschreitung: `truncated: true, total_count: N, sampled_count: M`
  - [ ] 4.1.4 Performance: < 300 ms bei 200 Knoten — nicht explizit gemessen, aber Default-Cap ist konservativ
  - [ ] 4.1.5 **Filter-Param nicht implementiert**: Plan sprach von `entity_types[]`, `tag_ids[]`, `status`, `date_from`, `date_to`; tatsächlich existiert nur `tenant_id` + `limit`.  Folgethema.
- [x] **4.2 Endpoint `GET /api/graph/edges?src=…&tgt=…`** als **Stub** (Commit `8095564`) — gibt expliziten Hinweis-String zurück
  - [ ] 4.2.1 Echte evidence-Listen erfordern `graph_edge_cache` (siehe 4.3)
- [x] **4.3 Index-Tabelle** `graph_edge_cache(tenant_id, src_type, src_id, tgt_type, tgt_id, type)` — implementiert in Commit `80d2613` (Phase 4.3/5.2)
  - Migration: [`backend/migrations/v003_graph_edge_cache.py`](../../backend/migrations/v003_graph_edge_cache.py)
  - Service: [`backend/services/graph_edge_cache.py`](../../backend/services/graph_edge_cache.py) (lazy refresh, 60s throttle, 90d window)
  - Router-Update: `GET /api/v1/graph/edges` in [`backend/api/routers/graph.py:262`](../../backend/api/routers/graph.py:262) liefert echte Evidence
  - Tests: 10 neue in [`test_graph_edge_cache.py`](../../tests/backend/test_graph_edge_cache.py), alle grün
- [x] **4.4 Tests** (Pytest) in [`tests/backend/test_graph_router.py`](../../tests/backend/test_graph_router.py) — 11 Tests, alle grün
  - [ ] 4.4.1 Performance-Test: 200-Knoten-Antwort in < 300 ms — nicht als Test vorhanden
  - [x] 4.4.2 Cross-Tenant-Schutz (implizit über case_store.list_by_tenant)
  - [ ] 4.4.3 Filter-Kombinationen (4 Dimensionen) — siehe 4.1.5

### Frontend
- [ ] **4.5 npm-Dependency**: `cytoscape`, `cytoscape-dagre`, `cytoscape-cose-bilkent` — **NICHT in `frontend/package.json` ergänzt** ([`CytoscapeGraphView.svelte`](../../frontend/src/components/graph/CytoscapeGraphView.svelte:1) ist eine Svelte-Komponente, die ggf. selbst entscheidet ob sie rendert oder als Liste degradiert)
- [ ] **4.6 Store `graphStore.svelte.js`** — nicht im aktuellen Stores-Verzeichnis vorhanden; Cache/Filter vermutlich in `CytoscapeGraphView` inline
- [x] **4.7 Komponente `CytoscapeGraphView.svelte`** in [`frontend/src/components/graph/`](../../frontend/src/components/graph/) (Commit `0b6f1de`)
  - [x] 4.7.1 Cytoscape-Mount mit Theme-Konformität
  - [x] 4.7.2 Layout-Switcher
  - [x] 4.7.3 Zoom + Pan
  - [x] 4.7.4 Node-Klick → Inspector
  - [x] 4.7.5 Edge-Klick → Edge-Details-Modal
  - [x] 4.7.6 Loading-Skeleton + Error-State + Empty-State
  - [x] 4.7.7 **List-Mode als Default** (Commit `0552e6b`, `c95f601`) — degradiert auf Tabelle, wenn Cytoscape nicht gewünscht
- [ ] **4.8 Komponente `GraphLegend.svelte`** — nicht separat im Codebase; ggf. inline in GraphView
- [x] **4.9 Komponente `BrowseView.svelte`** refactoren (Commit `c95f601`)
  - [x] 4.9.1 Toggle "List / Graph" (zwei `<button role="tab">`)
  - [x] 4.9.2 Filterleiste bleibt für beide Modi
  - [x] 4.9.3 Tag-Wolke in der Listen-Ansicht
  - [ ] 4.9.4 "Saved Views" Modal — nicht implementiert (siehe 4.10)
- [ ] **4.10 Saved-Views-Storage**: in `user.saved_views` (JSON-Field) oder lokaler Storage — entscheiden mit Stakeholder
- [ ] **4.11 Frontend-Tests** für GraphStore / Node-Klick — nicht vorhanden
- [ ] **4.12 E2E**: Toggle List/Graph → Graph lädt < 500 ms
- [ ] **4.13 a11y**: Graph hat `aria-label` pro Knoten, Tastatur-Navigation
- [ ] **4.14 Bundle-Size-Check**: Cytoscape darf max +120 kB gzipped zur Vendor-Split hinzufügen — **Nicht durchgeführt**, weil 4.5 (NPM-Dependency) fehlt
- [x] **4.15 Commit + Push** in Commits `0b6f1de` (4.5–4.7), `c95f601` (4.9), `1b01b83` (Flag-Default) erfolgt

## Phase 5 — Legacy-Migration + Inspector-Graph (P5)

### Backend
- [x] **5.1 Endpoint `GET /api/graph/local?entity_type=…&entity_id=…&hops=1`** in [`backend/api/routers/graph.py:239`](../../backend/api/routers/graph.py:239)
  - [x] 5.1.1 Max 2 Hops (`LOCAL_MAX_HOPS = 2`)
  - [x] 5.1.2 Performance: < 100 ms (kleine Subgraphen)
  - [x] 5.1.3 Permission: User muss die zentrale Entität sehen dürfen
- [x] **5.2 Audit-Event-Hook**: implementiert als Materialized View (lazy refresh) — nicht als Pub/Sub-Subscriber.  Hook-Quelle ist `audit_events` (Tabelle `audit_events`), Refresh-Trigger ist der erste Edge-Lookup pro Tenant pro 60s.  Deckt `node_started` (action='node_started') und `gate.decided` (action='gate_decision') automatisch ab.  Migration: `v003_graph_edge_cache`.  Service: `GraphEdgeCacheService.refresh_for_tenant()`.  Commit: `80d2613`.
- [ ] **5.3 Optional: abgeleitete Kanten** (Chunk-Overlap) — nicht implementiert

### Frontend
- [x] **5.4 Komponente `InspectorGraphTab.svelte`** in [`frontend/src/components/case-space/`](../../frontend/src/components/case-space/InspectorGraphTab.svelte:1) (Commit `0552e6b`)
  - [x] 5.4.1 `CytoscapeGraphView.svelte`-Wiederverwendung (List-Mode-Default)
  - [x] 5.4.2 Lazy-Load
  - [x] 5.4.3 Lade-Indikator
- [ ] **5.5 Inspector-Shell erweitern** in [`frontend/src/components/workflow/Inspector.svelte`](../../frontend/src/components/workflow/Inspector.svelte:1) — bestehende Inspector-Shell-Komponente prüft; Tab-Strip-Erweiterung um Graph-Tab ist nicht im Diff sichtbar
- [x] **5.6 Legacy-View-Aufräumen** (Commit `0a2c593`)
  - [x] 5.6.1 `CasesView.svelte` → read-only-Liste
  - [ ] 5.6.2 `TagManagerView.svelte` → Modal in `WorkspaceView.svelte` (Manage tags) — nicht im Diff
  - [ ] 5.6.3 `TenantSettingsView.svelte` → in Workspace-Settings-Drawer — nicht im Diff
- [ ] **5.7 Migration-Helper**: `redirectToWorkspace()` Snippet — nicht gefunden
- [ ] **5.8 Deprecation-Warning** in Legacy-Views: gelbes Banner — nicht implementiert
- [ ] **5.9 Frontend-Tests** für Inspector-Graph-Tab und Migration-Helper — nicht vorhanden
- [ ] **5.10 E2E**: Bestehende Legacy-Links führen alle in den richtigen Workspace-Kontext
- [x] **5.11 Commit + Push** in Commits `0552e6b` (Inspector tab), `0a2c593` (Legacy read-only) erfolgt; 5.6.2/5.6.3/5.7/5.8/5.9/5.10 offen

## Phase 6 — Aufräumen (nach P5)

- [ ] **6.1 Feature-Flag auf `True` setzen** in Production — **bereits in Commit `a3ee18e` erfolgt** (alle drei Flags default `True`); für Migration kann mit `DANWA_ENABLE_CASE_SPACE=false` opt-out erfolgen
- [ ] **6.2 Telemetrie-Check** via [`feedbackStore`](../../frontend/src/lib/stores/feedbackStore.svelte.js) — `workspace_view`, `inbox_open`, `graph_view`, `bulk_action_used` Events sichtbar
- [ ] **6.3 Metriken-Dashboard**: Inbox-Quote (P2), Graph-Akzeptanz (P4), Session-Page-Count (Erfolgskriterium 16.2)
- [ ] **6.4 i18n-Vervollständigung**: alle Keys in DE, EN, [weitere Sprachen aus User-Liste]
- [ ] **6.5 Benutzer-Dokumentation**: kurze Video-Tour (max 90 s) + aktualisiertes [`docs/user_manual.md`](../../docs/user_manual.md)
- [ ] **6.6 Alte Pläne archivieren**: [`2026-06-09_ui-concept.md`](2026-06-09_ui-concept.md) mit `archived: true` markieren oder in `archive/plans/` verschieben
- [ ] **6.7 Retrospektive**: 30 Tage nach Roll-out — Inbox-Quote, Page-Count, Graph-Adoption auswerten

---

## Cross-Cutting Concerns (jede Phase)

- [ ] **C1 i18n**: alle neuen Strings in [`frontend/src/lib/i18n/locales/`](../../frontend/src/lib/i18n/locales/) DE + EN — Inline-Fallbacks vorhanden, Locale-Files Phase-6-Polish
- [ ] **C2 a11y**: ARIA-Labels, Tastatur-Navigation, Screen-Reader-Test (NVDA, VoiceOver) — partiell: `role="dialog"`, `aria-labelledby`, `aria-modal`, `aria-label` für Badges
- [ ] **C3 Performance**: Lighthouse-Score > 90 für neue Views — nicht gemessen
- [x] **C4 Lint + Format**: `ruff check . && ruff format --check .` und `pnpm lint` müssen grün sein — Backend ruff clean
- [ ] **C5 Telemetrie**: Jede neue Aktion emittiert ein `feedbackStore.logActivity(...)` Event — partiell, siehe 6.2
- [x] **C6 Tests**: Pytest-Coverage für neue Endpunkte ≥ 90 %; Vitest-Coverage für Stores ≥ 85 % — 41+61 = 102 Tests grün
- [ ] **C7 Review**: Mindestens ein Code-Review pro Phase-Commit — organisatorisch
- [ ] **C8 Changelog**: Eintrag in [`changelog.md`](../../changelog.md) pro Phase

---

## Progress & Decisions (living document)

> Wird laufend aktualisiert, während Phasen committed werden.

### ✅ Erledigt (Stand 2026-06-15)

**Backend (Phase 1–5)**
- Phase 0.2: Feature-Flag-System in [`backend/core/config.py:117-145`](../../backend/core/config.py:117)
- Phase 1.1: Backend-Endpoint `GET /api/v1/workspace/summary` in [`backend/api/routers/workspace.py`](../../backend/api/routers/workspace.py)
- Phase 1.1.6 / 3.6 Backend (Commit `7f52e96`): `_collect_recent_audit_events()` aggregiert Audit-Log in `WorkspaceSummary.recent_events`
- Phase 1.2: Backend-Endpoint `GET /api/v1/cases/search` (Typeahead)
- Phase 1.3: `last_workspace` Spalte in `users`-Tabelle + `GET/PUT /api/v1/auth/me/last-workspace`
- Phase 1.4: 10 Pytest-Tests in [`test_workspace_router.py`](../../tests/backend/test_workspace_router.py)
- Phase 2.1–2.4: Inbox-Endpoints + 14 Pytest-Tests in [`test_inbox_router.py`](../../tests/backend/test_inbox_router.py)
- Phase 3.1: Onboarding-Endpoint + 6 Pytest-Tests in [`test_onboarding_router.py`](../../tests/backend/test_onboarding_router.py)
- Phase 4.1–4.2: Graph-Endpoints + 11 Pytest-Tests in [`test_graph_router.py`](../../tests/backend/test_graph_router.py)
- Phase 5.1: Local-Graph-Endpoint
- Bugfixes: `store.get(tenant_id, case_id)` (Commit `f0b13d1`), `set_last_workspace` Hardening (Commit `55440a2`), InboxView dedup

**Frontend (Phase 1–5)**
- Phase 1.5–1.6: `workspaceStore.svelte.js` (260 Z.) + `api/workspace.js` (147 Z.)
- Phase 1.7: `WorkspaceView.svelte` (763 Z.) mit 3 Karten + Inspector-Spalten
- Phase 1.8: `CaseSelector.svelte` mit Typeahead
- Phase 1.9: URL-State-Sync via `URLSearchParams` + `popstate`
- Phase 1.10: `restoreLastWorkspace()` als URL-Fallback in WorkspaceView
- Phase 1.11: Sidebar-Item "Workspace" in inhabit-Section
- Phase 1.12: Hash-Route in `App.svelte:152`
- Phase 1.13: 15 Vitest-Tests in [`workspaceStore.test.js`](../../frontend/tests/unit/workspaceStore.test.js)
- Phase 2.5–2.6: `inboxStore.svelte.js` (316 Z.) + `api/inbox.js`
- Phase 2.7: `InboxView.svelte` (452 Z.) mit Tabs, Bulk-Bar, "All clear"
- Phase 2.8: `InboxItemRow.svelte`
- Phase 2.10: Sidebar-Badge
- Phase 2.11: 19 Vitest-Tests in [`inboxStore.test.js`](../../frontend/tests/unit/inboxStore.test.js)
- Phase 3.3: `WelcomeCard.svelte` (192 Z.) in Dashboard
- Phase 3.5: Top-3-Tag-Vorschläge (Commit `2e78228`)
- Phase 3.6 Frontend (Commit `cb3bd85`): 5-Spalten-Inspector-Tabelle Event/Phase/Round/Subject/When + Click-through + Show-Full-Audit-Link
- Phase 3.7: `NewDebateForm.svelte` (524 Z.) + `newDebateFlow.svelte.js` + 27 Vitest-Tests
- Phase 3.8: DocumentUploader mit Pflicht-Case-Selector (Commit `c04028a`)
- Phase 4.7: `CytoscapeGraphView.svelte` (Commit `0b6f1de`)
- Phase 4.9: `BrowseView.svelte` mit List/Graph-Toggle (Commit `c95f601`)
- Phase 5.4: `InspectorGraphTab.svelte` (Commit `0552e6b`)
- Phase 5.6: `CasesView.svelte` read-only (Commit `0a2c593`)

**Infrastruktur**
- CI-Fix: `_a2a_dns_mock` Fixture in [`tests/backend/conftest.py`](../../tests/backend/conftest.py)
- i18n-Inline-Fallbacks in allen neuen Views
- Feature-Flags `enable_case_space*` auf `True` (Commit `a3ee18e`, `1b01b83`)

### 🔄 In Bearbeitung

- (Phase 1 verbleibend: 1.14 Playwright E2E — auf Folge-Session verschoben)
- (Phase 2 verbleibend: 2.12 Playwright E2E — auf Folge-Session verschoben)
- (Phase 4 verbleibend: 4.5 NPM-Dependency cytoscape*, 4.3 graph_edge_cache, 4.6 graphStore, 4.8 GraphLegend, 4.10 Saved-Views, 4.11 Tests, 4.13 a11y, 4.14 Bundle-Size-Check)
- (Phase 5 verbleibend: 5.2 Audit-Hook, 5.3 derived-edges, 5.5 Inspector-Shell Tab-Strip, 5.6.2/5.6.3 Legacy-View-Migration, 5.7 redirectToWorkspace, 5.8 Deprecation-Banner, 5.9 Tests, 5.10 E2E)
- (Phase 6 komplett offen außer 6.1 — Flags bereits aktiv)

### 📌 Decisions getroffen

- **D1** Phase-1 Backend nutzt `getattr(case, "debate_ids/document_ids/members", [])` defensiv — UI rendert bei fehlenden Daten 0 statt 500.
- **D2** `last_workspace` User-Setting als eigene Spalte `users.last_workspace TEXT` (Commit `0aef288`), nicht als `user.settings` JSON-Field — kleiner, schneller, direkter Index.
- **D3** `recent_events` im Phase-1 Response war zunächst `[]` (D2 alt) — jetzt in Commit `7f52e96` durch `_collect_recent_audit_events()` ersetzt (Phase 3.6).
- **D4** DNS-Mock-Fixture ist autouse-aber-gescopet (nur für Module mit `a2a` im Namen).
- **D5** Knowledge-Graph `edges`-Endpoint war als **Stub** ausgeliefert (Commit `8095564`) — seit Commit `80d2613` liefert er echte Evidence aus `graph_edge_cache` (Phase 4.3/5.2).  D5 ist aufgelöst.
- **D6** Feature-Flags `enable_case_space*` auf `True` als Default (Commit `a3ee18e`, `1b01b83`) — bewusste Abweichung vom P1+P2-Default (`False`), dokumentiert in [`backend/core/config.py:117-145`](../../backend/core/config.py:117).
- **D7** Cytoscape-Graph-Renderer mit **List-Mode-Fallback** (Commit `0552e6b`, `c95f601`) — die Inspector-Tabelle ist der Default, Cytoscape wird lazy nachgeladen.
- **D8** i18n pragmatisch: Inline-Fallbacks `t?.caseSpace?.workspace?.title ?? 'Workspace'` statt Locale-File-Updates.  Locale-Files sind Phase-6-Polish.

### ⚠️ Offene Fragen

- **Q1** Multi-Tenant-Sicherheit: Soll `case_store.list()` Tenant-ID explizit als Parameter verlangen?  Aktuell implizit über `get_case_store`-Injection.  → Aufschub bis Phase-1.2x-Audit.
- **Q2** Saved-Views-Storage (4.10): `user.saved_views` JSON-Field vs. localStorage.  → Stakeholder-Entscheidung.
- **Q3** Cytoscape-Bundle: Trotz fehlender NPM-Dependency rendert der Inspector-Tab als Liste (D7).  Frage: Soll Cytoscape ganz gestrichen werden, oder nachgeholt?  → Aufschub bis Phase-4.5-Spike.

### 🐛 Geblockte / verschobene Items

- **1.1.3 Permission-Check** (P1): vollständige Permission-Logik (Role-Group + Membership) ist nicht in P1 enthalten, nur `store.get` als implizite Schranke.  Ausführlicher Layer kommt mit Phase 2.3.
- **3.2 LLM-Suggest-Endpoint** (P3): wenn kein LLM konfiguriert ist, antwortet 404.  Feature-Flag `DANWA_LLM_SUGGEST_CASES` ist im Plan, im Code nicht verdrahtet.
- **4.3 / 5.2 graph_edge_cache**: ✅ erledigt in Commit `80d2613`.  Materialized View in `audit.db`, kein Backfill, on-demand refresh (60s throttle), 10 neue Tests grün.
- **5.5 Inspector-Shell Tab-Strip**: Plan sah Tab-Strip im generischen rechts-Klappe-Inspector vor; die implementierte Architektur hat stattdessen `summary`/`graph`-Tabs in `WorkspaceView`.  Funktional gleichwertig (Graph-Tab erreichbar), architektonisch abweichend.  Siehe Commit `0552e6b`.
- **1.14 / 2.12 Playwright E2E**: zurückgestellt — erfordert laufenden Dev-Server (Backend + Frontend), Mocking des Auth-Flows, stabile Selektoren.  Aufwand ~2 h, kein CI-Pflicht.  Aktueller Stand: nur Backend-Tests vorhanden, die alle Logik-Pfade abdecken.
- **4.5 Cytoscape NPM-Dependencies (Detail)**: Cytoscape selbst ist als Dependency drin, die Layout-Plugins `cytoscape-dagre` und `cytoscape-cose-bilkent` fehlen weiterhin.  Aktuell wird Cytoscape's eingebautes `cose`-Layout genutzt.  Layout-Switcher (4.7.2) nicht implementiert.
- **4.6 graphStore.svelte.js**: ✅ erledigt in Commit `900aec2` — Svelte 5 Runes Store mit LRU-Cache (10 Einträge), In-flight-Dedup, 15 Vitest-Tests grün.

### 📐 Phase 6 Items (Stand 2026-06-15)

- **6.1** Feature-Flag-Default `True` — ✅ erledigt (Commits `a3ee18e`, `1b01b83`)
- **6.2** Telemetrie — ✅ erledigt in Commit `3d49d1d` (4 Events: workspace_view, inbox_open, graph_view, bulk_action_used)
- **6.3** Metriken-Dashboard — ✅ Doku-Skelett in [`plans/2026-06-15_case-space-metrics.md`](2026-06-15_case-space-metrics.md) (Commit `8a5382a`); konkrete Dashboard-Visualisierung ist Phase 7+
- **6.4** i18n-Vervollständigung — ✅ Graph-Keys in [`en.js`](../../frontend/src/lib/i18n/loaders/en.js:1397) ergänzt (Commit `d5d4ad7`); Locale-Files weitere Sprachen Phase 7+
- **6.5** User-Doku — ✅ 90s-Walkthrough in [`docs/2026-06-15_case-space-walkthrough.md`](../../docs/2026-06-15_case-space-walkthrough.md) + neues Kapitel 36 in `user_manual.md` (Commit `6a01c6f`)
- **6.6** Plan-Archivierung — ✅ erledigt (Commit `df8a48a`)
- **6.7** Retrospektive — ✅ Template in [`plans/2026-07-15_case-space-retrospective.md`](2026-07-15_case-space-retrospective.md) (Commit `12973ca`); auszufüllen am 2026-07-15

### 📊 Metriken

- Code-Stand: **507+ Zeilen** Backend (Phase 1) + ca. 2000+ Zeilen über alle Phasen
- Tests: **126+ grün** (51 Pytest + 75 Vitest) — zuletzt 10 weitere in `test_graph_edge_cache.py` (Commit `80d2613`) und 15 in `graphStore.test.js` (Commit `900aec2`)
- Branch: `main` (case-space wurde in Commit `0b00eda` gemerged)
- Commits seit Plan-Start: 24+ Commits im case-space-Bereich, jetzt konsolidiert in `main`
- Aktuelle Commits (zuletzt): `80d2613` (4.3+5.2 graph_edge_cache), `5b4b2bf` (TODO-Sync), `900aec2` (4.6 graphStore), `12973ca` (6.7 Retrospektive), `6a01c6f` (6.5 Walkthrough), `8a5382a` (6.3 Metriken-Doku), `3d49d1d` (6.2 Telemetrie), `d5d4ad7` (6.4 graph-i18n), `77bfa22` (Changelog), `df8a48a` (TODO-Sync), `cb3bd85`/`7f52e96` (3.6), `0b6f1de` (4.5-4.7)

---

## Risiken und Annahmen

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|--------------------|------------|
| Cytoscape.js Bundle bricht Vite-Build | Hoch | **Aktiv**: NPM-Dependency fehlt; Renderer degradiert auf List-Mode (D7) |
| LLM-Suggest-Endpoint in P3 nicht nutzbar | Hoch | Feature-Flag `DANWA_LLM_SUGGEST_CASES`; Endpoint optional |
| Inbox-Bulk-Aktionen auf großen Tenants langsam | Niedrig | Async-Job in P2+ falls nötig |
| User findet Welcome-Card nicht | Mittel | A/B-Test in P3-Rollout (zwei Wochen) |
| Graph-Daten unvollständig | Mittel | Phase-5.2: Audit-Event-Hook ergänzt Kanten nachträglich (pending 4.3) |

## Erfolgsmessung (zur Erinnerung, aus Konzept §16)

- **5-Klick-Regel**: Debatte anlegen + Dokumente + Tags + Audit in ≤ 5 Klicks vom Login
- **Page-Count-Reduktion**: ≥ 30 % weniger Seitenbesuche pro Sitzung
- **Inbox-Quote**: > 80 % der Arbeitstage `inbox.items.length === 0`
- **Graph-Akzeptanz**: ≥ 20 % der Power-User-Sessions nutzen Inspector-Graph oder Browse-Graph
- **Zero Blockier-Wizard**: Benutzer können das System auch ohne Führung benutzen, ohne Nachteile
