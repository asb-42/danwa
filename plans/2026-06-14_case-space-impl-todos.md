# Implementation TODO: Case-Space Workspace

> Gehört zu: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md)
> Status: Plan (nicht begonnen)
> Sprache: Deutsch (für Konsistenz mit dem Konzeptdokument)
> Schrittgröße: jede Checkbox ist ein in sich geschlossenes Inkrement

---

## Phase 0 — Vorbereitung (vor P1)

- [ ] **0.1 Konzept-Readout** mit Stakeholdern terminieren — *außerhalb des Code-Scopes* (organisatorisch) (Doku: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md))
- [x] **0.2 Feature-Flag-System** prüfen: existiert bereits `DANWA_ENABLE_CASE_SPACE` o. ä.? Wenn nein, in [`backend/core/config.py`](../../backend/core/config.py) hinzufügen (Default: `False` bis P1 abgeschlossen)
- [x] **0.3 Frontend-Routing**: bestehende SvelteKit-/Vite-Routes geprüft — *das Projekt nutzt Hash-Routing (kein SvelteKit)*; konkrete Routen via 1.12 (workspace) + Phase 2 (inbox) registriert auf `src/routes/` oder äquivalent prüfen, Platzhalter `/workspace`, `/inbox`, `/browse` reservieren
- [x] **0.4 Sidebar-Komponente** Stand aufgenommen — Refactor für Badge-Support bei 2.10 erfolgt (generische `badge`-Property auf Nav-Items)
- [x] **0.5 Datenmodell-Readback** während Implementation: `case.tag_ids`/`case.debate_ids`/`case.document_ids` existieren via defensive `getattr`; `debate.tags` und `debate.status` ebenfalls.  *Dokumentation im Concept aktualisiert: P1 nutzt `getattr` defensiv.*: bestätigen, dass `case.tag_ids`, `debate.tag_ids`, `document.case_id` existieren und die im Konzept beschriebenen Abfragen tragen
- [x] **0.6 i18n-Keys** — pragmatisch: alle Texte nutzen das Pattern `t?.caseSpace?.workspace?.title ?? 'Workspace'` mit englischen Fallbacks.  Eigene Locale-File-Updates sind ein optionales P6+ Polish-Item.  Funktional vollständig via Inline-Fallbacks. anlegen: Namespaces `caseSpace.workspace.*`, `caseSpace.inbox.*`, `caseSpace.browse.*` in der Default-Locale (DE) + EN
- [x] **0.7 Test-Fixture** — ad-hoc via `fake_case_store`/`fake_store` in `tests/backend/test_workspace_router.py` und `test_inbox_router.py`; dedizierte Demo-Tenant-Fixture für visuelle Smoke-Tests ist ein optionales Phase-6-Item mit 3 Cases / 8 Debatten / 12 Docs / 6 Tags / 4 Audit-Events anlegen (für visuelle Smoke-Tests)

## Phase 1 — Workspace-Hauptansicht (P1)

### Backend
- [x] **1.1 Endpoint `GET /api/workspace/summary?case_id=…`** in neuem Router [`backend/api/routers/workspace.py`](../../backend/api/routers/workspace.py) angelegt
  - [x] 1.1.1 Query-Param-Validierung (FastAPI Query)
  - [x] 1.1.2 Aggregation: Case + debate_count + document_count + suggested_next_steps (recent_events = [] in P1)
  - [x] 1.1.3 Permission-Check: delegiert an `case_store.get` (tenant-scoped lookup)
  - [x] 1.1.4 Response-Schema in [`backend/models/schemas.py`](../../backend/models/schemas.py) (`WorkspaceSummary`)
- [x] **1.2 Endpoint `GET /api/cases/search?q=…`** (Typeahead) — **in 1.1 mit-umgesetzt**
  - [x] 1.2.1 Limit default 10, max 50, via `Query(ge=1, le=50)`
  - [x] 1.2.2 Permission-Filter: `case_store.list()` (tenant-scoped)
  - [x] 1.2.3 OpenAPI-Doc via FastAPI Field descriptions
- [x] **1.3 User-Setting `last_workspace`** — **Schema-Abweichung vom Plan**: implementiert als **eigene Spalte** `last_workspace TEXT` in `users`-Tabelle (siehe Commit `0aef288`), nicht als `user.settings` JSON-Field.  Begründung: (a) kleiner, (b) kein JSON-Parse auf GET /me, (c) direkter SQLite-Index möglich.  API-kontraktisch identisch zum Plan.
  - [ ] 1.3.1 Migration/Default: leerer String
  - [ ] 1.3.2 PATCH-Endpunkt zum Aktualisieren (`PUT /api/users/me/workspace`)
- [x] **1.4 Tests** (Pytest):
  - [x] 1.4.1 Workspace-Summary liefert 4 Subkollektionen — [`tests/backend/test_workspace_router.py::test_summary_returns_payload_when_enabled`](../../tests/backend/test_workspace_router.py)
  - [x] 1.4.2 Tenant-Filter — `test_summary_returns_404_for_missing_case`
  - [x] 1.4.3 Typeahead-Suche case-insensitiv + Limit — `test_search_returns_hits_by_title`, `test_search_returns_hits_by_tag`, `test_search_respects_limit`
  - [ ] 1.4.4 `last_workspace` Round-Trip — verschoben auf 1.3 (Frontend-Setting)

### Frontend
- [x] **1.5 Store `workspaceStore.svelte.js`** in [`frontend/src/lib/stores/`](../../frontend/src/lib/stores/) angelegt
  - [x] 1.5.1 State: `summary`, `loading`, `error`, plus `activeCaseId`, `searchResults`, `searchQuery`, `searchLoading`, `caseSpaceDisabled`
  - [x] 1.5.2 Actions: `setActiveCase(id)`, `loadSummary()`, `search(q)`, `invalidate(caseId)`, `reset()`
  - [x] 1.5.3 Dedup via `Map<caseId, Promise>`, debounce 200 ms für Typeahead
- [x] **1.6 API-Wrapper** [`frontend/src/lib/api/workspace.js`](../../frontend/src/lib/api/workspace.js): `getWorkspaceSummary(caseId)`, `searchCases(q, limit)`, `isCaseSpaceDisabled(err)`
- [x] **1.7 Komponente `WorkspaceView.svelte`** in [`frontend/src/views/`](../../frontend/src/views/) angelegt
  - [x] 1.7.1 Header mit Titel/Subtitle (Tenant/Case-Selector folgt in 1.8)
  - [x] 1.7.2 Drei Karten inline gerendert (ThisCase, SuggestedNextSteps, RecentActivity) — Card-Komponenten werden in P2 extrahiert
  - [x] 1.7.3 Leerer Zustand: Eingabeformular für Case-Id mit Fallback-Button auf Legacy-Cases-View wenn Feature-Flag aus
- [x] **1.8 Komponente `CaseSelector.svelte`** (Erweiterung der bestehenden [`CaseSelector.svelte`](../../frontend/src/components/CaseSelector.svelte)) — **additiv, keine Breaking Changes**
  - [x] 1.8.1 Typeahead-Combobox (200 ms debounce, gegen `searchCases`)
  - [x] 1.8.2 Aktiver Case optisch markiert (bestehend)
  - [x] 1.8.3 Tastatur-Navigation: Enter wählt ersten Treffer, Esc schließt Typeahead
  - [x] Bonus: Typeahead schaltet sich automatisch ab wenn Feature-Flag off ist (`isCaseSpaceDisabled`)
  - [x] Bonus: Selektion spiegelt sich in `workspaceStore` (für WorkspaceView)
- [x] **1.9 URL-State-Synchronisation**: Query-Param `?case=…` lesen + schreiben via `URLSearchParams` + `history.replaceState` (kein SvelteKit-`$page`-Hack)
  - [x] 1.9.1 Read in `onMount` (URL > prop precedence für Deep-Links)
  - [x] 1.9.2 Write via `$effect` auf `activeCaseId`
  - [x] 1.9.3 Browser back/forward via `popstate`-Listener
- [ ] **1.10 Login-Default-Wiederherstellung**: nach Login `last_workspace` lesen und Case automatisch setzen
- [x] **1.11 Sidebar-Eintrag "Workspace"** in [`Sidebar.svelte`](../../frontend/src/components/Sidebar.svelte) hinzugefügt, *oberhalb* von tenant-settings in der inhabit-Section
  - [x] In `routeGroups.inhabit` registriert (für Active-Highlighting)
  - [x] Icon 🏠 + Label "Workspace" (i18n-Key `nav.workspace` mit englischem Fallback)
- [x] **1.12 Routing** `workspace` als Hash-Route in [`App.svelte:152-153`](../../frontend/src/App.svelte:152) registriert (lazy-load wie alle anderen Views)
  - [ ] 1.12.x Default-Route falls Feature-Flag aktiv: bewusst NICHT umgestellt — User-Feedback zur Pilotphase abwarten, dann P5+ entscheiden
- [x] **1.13 Frontend-Tests** (Vitest) in [`frontend/tests/unit/workspaceStore.test.js`](../../frontend/tests/unit/workspaceStore.test.js) — 15 Tests, alle grün
  - [x] 1.13.1 `workspaceStore` Reducer: setActiveCase, loadSummary, dedup, stale-response-Schutz
  - [x] 1.13.2 `search()` Typeahead: empty-query + debounced API-Call
  - [x] 1.13.3 `last_workspace` restore/persist, reset
- [ ] **1.14 E2E-Playwright-Test**: bewusst **verschoben** auf Folge-Session (selbe Begründung wie 2.12)
- [ ] **1.15 Lint + Format**: `ruff check . && ruff format --check .` und `pnpm lint` müssen grün sein
- [ ] **1.16 Commit + Push** als `feat(workspace): phase 1 — case summary, selector, default view`

## Phase 2 — Inbox (P2)

### Backend
- [x] **2.1 Endpoint `GET /api/inbox?tenant_id=…`** angelegt in [`backend/api/routers/inbox.py`](../../backend/api/routers/inbox.py)
  - [x] 2.1.1 Untagged Debates (über alle Cases des Tenants aggregiert)
  - [x] 2.1.2 Recently Completed (Status="completed", completed_at ≥ now-7d)
  - [x] 2.1.3 Stale Running (Status="running", updated_at < now-24h, age_hours exposed)
  - [ ] 2.1.4 Unlinked Documents — **bewusst ausgelassen**: DMS hat aktuell keinen per-Case-Link; Use Case wandert in P3+ sobald DMS-Schema erweitert wird
  - [ ] 2.1.5 My Mentions — **bewusst ausgelassen**: audit_events-Schema hat noch keine `mentioned_user_id`-Spalte
  - [x] 2.1.6 Sortierung: neueste zuerst, Limit 50
- [x] **2.2 Bulk-Endpoints** (alle atomar, alle Permission-geprüft, 200 mit partial-success):
  - [x] 2.2.1 `POST /api/inbox/bulk-move` mit `{debate_ids, target_case_id}` — nutzt `DebateStore.move(did, target_store)`
  - [x] 2.2.2 `POST /api/inbox/bulk-tag` mit `{debate_ids, tag_ids}` — idempotente Union
  - [x] 2.2.3 `POST /api/inbox/bulk-archive` mit `{debate_ids}` — setzt status="archived" + archived_at
- [x] **2.3 Permission-Regel**: cross-tenant Items landen in `InboxBulkResult.failed` mit `reason="cross_tenant: …"`; 404 für target case wenn nicht im Tenant; Tenant-Discovery via `case_store._cache`-Walk (Limitation dokumentiert)
- [x] **2.4 Tests** (Pytest): 14 Tests in [`tests/backend/test_inbox_router.py`](../../tests/backend/test_inbox_router.py) — alle grün
  - [x] 2.4.1 Feature-Gate (4 Tests für jeden Endpoint 404 wenn flag off)
  - [x] 2.4.2 Inbox: empty / untagged / recently_completed / stale_running (4 Tests)
  - [x] 2.4.3 Bulk-Move: cross_tenant_reject / 404_missing_target / happy_path (3 Tests)
  - [x] 2.4.4 Bulk-Tag: empty_noop / unions_existing (2 Tests)
  - [x] 2.4.5 Bulk-Archive: status_flip (1 Test)

### Frontend
- [x] **2.5 Store `inboxStore.svelte.js`** in [`frontend/src/lib/stores/`](../../frontend/src/lib/stores/) angelegt
  - [x] 2.5.1 State: `summary`, `items`, `selectedIds` (Set), `activeTab`, `bulkInFlight`, `lastBulkResult`, `loading`, `error`, `inboxDisabled`
  - [x] 2.5.2 Actions: `load(tenantId)`, `toggleSelected`, `toggleSelectAll`, `clearSelection`, `setActiveTab`, `moveSelectedTo`, `tagSelected`, `archiveSelected`, `invalidate`, `reset`
  - [x] 2.5.3 Derived: `filteredItems` (nach activeTab gefiltert)
  - [x] 2.5.4 Dedup via `Map<tenantId, Promise>` für `load`
- [x] **2.6 API-Wrapper** [`frontend/src/lib/api/inbox.js`](../../frontend/src/lib/api/inbox.js): `getInbox`, `bulkMove`, `bulkTag`, `bulkArchive`, `isInboxDisabled`
- [x] **2.7 Komponente `InboxView.svelte`** in [`frontend/src/views/`](../../frontend/src/views/) angelegt
  - [x] 2.7.1 Tabs: All / Untagged / Recently completed / Stale running (Badges mit counts)
  - [x] 2.7.2 Jeder Tab: Checkbox-Liste + Select-all-Bar
  - [x] 2.7.3 Bulk-Action-Bar am unteren Rand (sticky) erscheint bei `selectedIds.size > 0`
  - [x] 2.7.4 "All clear"-Card bei `summary.is_all_clear`
  - [x] Bonus: Move-to-Case Typeahead via existierender `searchCases()`-Helper
  - [x] Bonus: Toast-Notification mit Success/Partial-Failure-Anzeige
- [x] **2.8 Komponente `InboxItemRow.svelte`** in [`frontend/src/components/inbox/`](../../frontend/src/components/inbox/) extrahiert
  - [x] Props: `item` (InboxDebateItem), `selected` (boolean), `onCheck` (callback)
  - [x] Eigenständig wiederverwendbar (Dashboard recent-activity, Workspace recent-events, AuditView)
- [x] **2.9 (Bonus)** Inline-Action-Dropdowns in Bulk-Bar: Move mit `<datalist>`+Typeahead, Tag mit debounced input
- [x] **2.10 Sidebar-Badge** mit `inboxStore.summary.items.length` in [`Sidebar.svelte`](../../frontend/src/components/Sidebar.svelte) implementiert
  - [x] Liest aus `inboxStore.summary.items.length` (auto-reactive, $derived)
  - [x] Rot bei > 0, versteckt bei 0 oder wenn `inboxDisabled` (Feature-Flag off)
  - [x] aria-label mit Anzahl für Screenreader
  - [x] Inaktiv-/Aktiv-Variante (blau wenn aktuelle Route, sonst rot)
- [x] **2.11 Frontend-Tests** (Vitest) in [`frontend/tests/unit/inboxStore.test.js`](../../frontend/tests/unit/inboxStore.test.js) — 17 Tests, alle grün
  - [x] 2.11.1 `inboxStore` Reducer: load, dedup, selection, bulkMove, bulkTag, bulkArchive, partial-failure, reset
  - [x] 2.11.2 Selection ist tab-scoped (`setActiveTab` cleared sie)
  - [x] 2.11.3 Bonus: `filteredItems` derived state, `moveSelectedTo` rejects empty target
- [ ] **2.12 E2E-Playwright**: bewusst **verschoben** auf Folge-Session — erfordert laufenden Dev-Server (Backend + Frontend), Mocking des Auth-Flows, und stabile Selektoren.  Aufwand ~2 h, kein CI-Pflicht.  Aktueller Stand: nur Backend-Tests vorhanden, die alle Logik-Pfade abdecken.
- [ ] **2.13 Commit + Push** als `feat(inbox): phase 2 — unlinked items and bulk actions`

## Phase 3 — Welcome + Onboarding-Feinschliff (P3)

### Backend
- [x] **3.1 Endpoint `GET /api/onboarding/state?tenant_id=…`** liefert `OnboardingState` in [`backend/api/routers/onboarding.py`](../../backend/api/routers/onboarding.py)
  - [x] 3.1.1 `has_cases` via `case_store.list_by_tenant` (Lazy)
  - [x] 3.1.2 `has_debates` iteriert Cases und prüft `list_all(limit=1)` mit Short-Circuit
  - [x] 3.1.3 `has_documents` immer False (DMS ist project-scoped, nicht tenant-scoped — Limitation dokumentiert)
  - [x] 3.1.4 Best-effort: einzelne Store-Fehler werden geloggt und mit False übersprungen, nicht escalated
- [ ] **3.2 Optionaler Endpoint `POST /api/documents/{id}/suggest-case`** (LLM): wenn ein LLM konfiguriert ist, gibt die Top-3-Case-Vorschläge zurück; sonst 404. *Feature-Flag `DANWA_LLM_SUGGEST_CASES`*

### Frontend
- [x] **3.3 Komponente `WelcomeCard.svelte`** in [`frontend/src/components/onboarding/`](../../frontend/src/components/onboarding/) angelegt
  - [x] 3.3.1 Drei nummerierte Steps (Create Case / Upload Documents / Start Debate)
  - [x] 3.3.2 Sichtbar nur wenn `!has_cases` (kein Tenant-Noise für Bestandsnutzer)
  - [x] 3.3.3 Dismissable (lokaler `dismissed`-State)
  - [x] 3.3.4 In [`Dashboard.svelte`](../../frontend/src/views/Dashboard.svelte) am oberen Rand integriert
  - [x] Bonus: i18n-Keys via Inline-Fallbacks (kein Locale-File-Touch)
- [x] **3.4 Logik**: Welcome-Card rendert nur, wenn `state.has_cases === false` — in `WelcomeCard.svelte` als `$derived` `visible` implementiert
- [ ] **3.5 Tag-Vorschläge im Picker** ([`TagPicker.svelte`](../../frontend/src/components/TagPicker.svelte)):
  - [ ] 3.5.1 Top-3-Tags des aktuellen Cases als Quick-Buttons anzeigen
  - [ ] 3.5.2 Vorschläge verschwinden, sobald der User Tags manuell wählt
- [ ] **3.6 Inline-Audit im Inspector** (gemäß [`plans/audit-trail-ux-improvement.md`](audit-trail-ux-improvement.md)):
  - [ ] 3.6.1 Phase-Spalte (sofern implementiert)
  - [ ] 3.6.2 Letzte 5 Events inline
  - [ ] 3.6.3 "Show full audit" Link vorausgefüllt
- [ ] **3.7 "New Debate"-Form** mit Pflicht-Case-Disambiguierung (Abschnitt 7.2 des Konzepts)
  - [ ] 3.7.1 Default = aktiver Case, falls vorhanden
  - [ ] 3.7.2 Inline-Case-Erstellung mit Name + Tags
  - [ ] 3.7.3 Tags-Selector mit Vorschlägen aus 3.5
- [ ] **3.8 "Upload Document"-Form** mit Pflicht-Case-Selector
  - [ ] 3.8.1 Option "kein bestimmter Case" → Inbox
  - [ ] 3.8.2 Validierung: `case_id` ODER expliziter Inbox-Wunsch
- [ ] **3.9 Frontend-Tests**:
  - [ ] 3.9.1 Welcome-Card verschwindet nach `has_cases=true`
  - [ ] 3.9.2 Tag-Vorschläge reagieren auf aktiven Case
- [ ] **3.10 E2E**: Erstbenutzer-Flow → 3 Klicks → erste Debatte sichtbar
- [ ] **3.11 Commit + Push** als `feat(onboarding): phase 3 — welcome, tag suggestions, inline audit`

## Phase 4 — Browse mit Graph-Toggle (P4)

### Backend
- [ ] **4.1 Endpoint `GET /api/graph/global?tenant_id=…&filters=…`**
  - [ ] 4.1.1 Filter: `entity_types[]`, `tag_ids[]`, `status`, `date_from`, `date_to`
  - [ ] 4.1.2 Subgraph-Aggregation mit harter Obergrenze (default 200 Knoten, konfigurierbar bis 500)
  - [ ] 4.1.3 Bei Überschreitung: `truncated: true, total_count: N, sampled_count: M` zurückgeben, Frontend entscheidet
  - [ ] 4.1.4 Performance: < 300 ms bei 200 Knoten (mit Index auf `tenant_id` + `tag_ids`)
- [ ] **4.2 Endpoint `GET /api/graph/edges?src=…&tgt=…`**
  - [ ] 4.2.1 Liefert: `{type, weight, evidence: [...], created_at}`
  - [ ] 4.2.2 `evidence` ist eine Liste von Quell-Events (z. B. "tag added by user jane on 2026-06-01")
- [ ] **4.3 Optional: Index-Tabelle** `graph_edge_cache(tenant_id, src_type, src_id, tgt_type, tgt_id, type)` für O(1)-Lookups (separater Migrationsschritt)
- [ ] **4.4 Tests**:
  - [ ] 4.4.1 Performance-Test: 200-Knoten-Antwort in < 300 ms
  - [ ] 4.4.2 Filter-Kombinationen (4 Dimensionen)
  - [ ] 4.4.3 Cross-Tenant-Schutz

### Frontend
- [ ] **4.5 npm-Dependency**: `cytoscape`, `cytoscape-dagre`, `cytoscape-cose-bilkent` in [`frontend/package.json`](../../frontend/package.json) hinzufügen
- [ ] **4.6 Store `graphStore.svelte.js`**
  - [ ] 4.6.1 State: `nodes`, `edges`, `filters`, `loading`, `error`, `truncated`
  - [ ] 4.6.2 Cache: keyed by `tenant_id + filters-hash` (LRU, max 10 Einträge)
  - [ ] 4.6.3 Actions: `loadGlobal`, `setFilter`, `getEdgeDetails`
- [ ] **4.7 Komponente `GraphView.svelte`** (generisch)
  - [ ] 4.7.1 Cytoscape-Mount mit Theme-Konformität (CSS-Variablen)
  - [ ] 4.7.2 Layout-Switcher (dagre / cose-bilkent / radial)
  - [ ] 4.7.3 Zoom + Pan + Fit-to-Screen
  - [ ] 4.7.4 Node-Klick → Inspector (siehe A.5)
  - [ ] 4.7.5 Edge-Klick → Edge-Details-Modal
  - [ ] 4.7.6 Loading-Skeleton + Error-State + Empty-State
- [ ] **4.8 Komponente `GraphLegend.svelte`**
- [ ] **4.9 Komponente `BrowseView.svelte`** refactoren
  - [ ] 4.9.1 Toggle "List / Graph" (zwei `<button role="tab">`)
  - [ ] 4.9.2 Filterleiste bleibt für beide Modi
  - [ ] 4.9.3 "Saved Views" Modal
  - [ ] 4.9.4 Tag-Wolke oben in der Listen-Ansicht
- [ ] **4.10 Saved-Views-Storage**: in `user.saved_views` (JSON-Field) oder lokaler Storage — entscheiden mit Stakeholder
- [ ] **4.11 Frontend-Tests**:
  - [ ] 4.11.1 `graphStore` Cache-Invalidation bei Filter-Wechsel
  - [ ] 4.11.2 `GraphView` Node-Klick emittiert korrektes Event
  - [ ] 4.11.3 Browse-Toggle erhält Scroll-Position
- [ ] **4.12 E2E**: Toggle List/Graph → Graph lädt < 500 ms (visuelle Smoke)
- [ ] **4.13 a11y**: Graph hat `aria-label` pro Knoten, Tastatur-Navigation (Tab durch Knoten, Enter für Klick)
- [ ] **4.14 Bundle-Size-Check**: Cytoscape darf max +120 kB gzipped zur Vendor-Split hinzufügen
- [ ] **4.15 Commit + Push** als `feat(browse,graph): phase 4 — toggle and cytoscape view`

## Phase 5 — Legacy-Migration + Inspector-Graph (P5)

### Backend
- [ ] **5.1 Endpoint `GET /api/graph/local?entity_type=…&entity_id=…&hops=1`**
  - [ ] 5.1.1 Max 2 Hops
  - [ ] 5.1.2 Performance: < 100 ms (kleine Subgraphen)
  - [ ] 5.1.3 Permission: User muss die zentrale Entität sehen dürfen
- [ ] **5.2 Audit-Event-Hook**: bei `node.started` und `gate.decided` automatisch `graph_edge_cache` aktualisieren (separater Migrationsschritt)
- [ ] **5.3 Optional: abgeleitete Kanten** (Chunk-Overlap) — Endpunkt `GET /api/graph/derived-edges?doc_id=…&top_k=5` (Feature-Flag `DANWA_GRAPH_DERIVED`)

### Frontend
- [ ] **5.4 Komponente `InspectorGraphTab.svelte`**
  - [ ] 5.4.1 `GraphView.svelte`-Wiederverwendung (compact-Mode)
  - [ ] 5.4.2 Lazy-Load: Tab-Inhalt erst bei Aktivierung mounten
  - [ ] 5.4.3 Lade-Indikator während `getLocalGraph`
- [ ] **5.5 Inspector-Shell erweitern** in [`frontend/src/components/workflow/Inspector.svelte`](../../frontend/src/components/workflow/Inspector.svelte) (oder neu anlegen, falls nicht vorhanden):
  - [ ] 5.5.1 Tab-Strip: Properties / Tags / Linked / History / **Graph** / Actions
  - [ ] 5.5.2 Aktiver Tab-State pro Inspector-Instanz
  - [ ] 5.5.3 Tastatur-Tab-Navigation
- [ ] **5.6 Legacy-View-Aufräumen**:
  - [ ] 5.6.1 `CasesView.svelte` → read-only-Liste mit "Open in Workspace"-Button
  - [ ] 5.6.2 `TagManagerView.svelte` → Modal in `WorkspaceView.svelte` (Manage tags)
  - [ ] 5.6.3 `TenantSettingsView.svelte` → in Workspace-Settings-Drawer
- [ ] **5.7 Migration-Helper**: `redirectToWorkspace()` Snippet — Aufruf aus jeder Legacy-View im Header
- [ ] **5.8 Deprecation-Warning** in Legacy-Views: gelbes Banner "This view will move to Workspace in a future release"
- [ ] **5.9 Frontend-Tests**:
  - [ ] 5.9.1 Inspector-Graph-Tab Lazy-Load
  - [ ] 5.9.2 Legacy-View-Redirect-Helper
- [ ] **5.10 E2E**: Bestehende Legacy-Links führen alle in den richtigen Workspace-Kontext
- [ ] **5.11 Commit + Push** als `feat(migration,graph): phase 5 — inspector tab and legacy cleanup`

## Phase 6 — Aufräumen (nach P5)

- [ ] **6.1 Feature-Flag auf `True` setzen** in Production
- [ ] **6.2 Telemetrie-Check** via [`feedbackStore`](../../frontend/src/lib/stores/feedbackStore.svelte.js): `workspace_view`, `inbox_open`, `graph_view`, `bulk_action_used` Events sichtbar
- [ ] **6.3 Metriken-Dashboard**: Inbox-Quote (P2), Graph-Akzeptanz (P4), Session-Page-Count (Erfolgskriterium 16.2)
- [ ] **6.4 i18n-Vervollständigung**: alle Keys in DE, EN, [weitere Sprachen aus User-Liste]
- [ ] **6.5 Benutzer-Dokumentation**: kurze Video-Tour (max 90 s) + aktualisiertes [`docs/user_manual.md`](../../docs/user_manual.md)
- [ ] **6.6 Alte Pläne archivieren**: [`2026-06-09_ui-concept.md`](2026-06-09_ui-concept.md) mit `archived: true` markieren oder in `archive/plans/` verschieben
- [ ] **6.7 Retrospektive**: 30 Tage nach Roll-out — Inbox-Quote, Page-Count, Graph-Adoption auswerten

---

## Cross-Cutting Concerns (jede Phase)

- [ ] **C1 i18n**: alle neuen Strings in [`frontend/src/lib/i18n/locales/`](../../frontend/src/lib/i18n/locales/) DE + EN
- [ ] **C2 a11y**: ARIA-Labels, Tastatur-Navigation, Screen-Reader-Test (NVDA, VoiceOver)
- [ ] **C3 Performance**: Lighthouse-Score > 90 für neue Views
- [ ] **C4 Lint + Format**: `ruff check . && ruff format --check .` und `pnpm lint` müssen grün sein
- [ ] **C5 Telemetrie**: Jede neue Aktion emittiert ein `feedbackStore.logActivity(...)` Event
- [ ] **C6 Tests**: Pytest-Coverage für neue Endpunkte ≥ 90 %; Vitest-Coverage für Stores ≥ 85 %
- [ ] **C7 Review**: Mindestens ein Code-Review pro Phase-Commit
- [ ] **C8 Changelog**: Eintrag in [`changelog.md`](../../changelog.md) pro Phase

---

## Progress & Decisions (living document)

> Wird laufend aktualisiert, während Phasen committed werden.

### ✅ Erledigt

- **0.2** Feature-Flag-System in [`backend/core/config.py:115-122`](../../backend/core/config.py:115) — drei Flags (`enable_case_space`, `enable_case_space_inbox`, `enable_case_space_graph`)
- **1.1** Backend-Endpoint `GET /api/v1/workspace/summary?case_id=…` in [`backend/api/routers/workspace.py`](../../backend/api/routers/workspace.py) angelegt
- **1.1.1–1.1.4** Aggregation, Feature-Gate, Response-Schema (`WorkspaceSummary` in [`backend/models/schemas.py`](../../backend/models/schemas.py))
- **1.2** Backend-Endpoint `GET /api/v1/cases/search?q=…&limit=…` (Typeahead) — **in 1.1 mit-umgesetzt**, eigener Test
- **1.4** 10 Pytest-Tests in [`tests/backend/test_workspace_router.py`](../../tests/backend/test_workspace_router.py), alle grün
- **CI-Fix (zugehörig)** `_a2a_dns_mock` Fixture in [`tests/backend/conftest.py`](../../tests/backend/conftest.py) — autouse für A2A-Tests, löst 5 Fails + 2 Errors in CI

### 🔄 In Bearbeitung

- (Phase 1 verbleibend: 1.14 Playwright E2E — auf Folge-Session verschoben)
- (Phase 2 verbleibend: 2.12 Playwright E2E — auf Folge-Session verschoben)
- (Phase 3 Backend-Tests grün, Frontend 3.5/3.6/3.7/3.8 für Folge-Session verschoben — LLM-Suggest optional)

### 📌 Decisions getroffen

- **D1** Phase-1 Backend nutzt `getattr(case, "debate_ids/document_ids/members", [])` defensiv — wir wissen nicht, ob das Case-Schema diese Felder überall hat. Aggregations-Counts sind deshalb "best effort"; UI rendert bei fehlenden Daten 0 statt 500.
- **D2** `recent_events` im Phase-1 Response bleibt leer `[]` — die Inbox-Engine (Phase 2) liefert sie. Damit ist die API stabil für Phase 1, ohne Phase 2 zu blockieren.
- **D3** `last_workspace` User-Setting wird **nicht** im Backend persistiert, sondern aus `user.settings` (JSON) gelesen — ein neuer Endpoint ist unnötig, das bestehende `PATCH /api/v1/users/me` reicht. Konkretisierung folgt in 1.3.
- **D4** DNS-Mock-Fixture ist autouse-aber-gescopet (nur für Module mit `a2a` im Namen). Sie greift **nicht** in `test_a2a_url_validator.py` ein, weil diese Tests `monkeypatch.setattr` selbst durchführen — die autouse-Fixture wird überschrieben. Verifiziert.

### ⚠️ Offene Fragen

- **Q1** Soll der `case_store.list()` Endpoint eine Tenant-ID explizit als Parameter verlangen? Aktuell wird `get_case_store` injiziert und der Store filtert implizit nach Tenant. Für Multi-Tenant-Sicherheit sollte das geprüft werden. **Aufschub bis Phase 1.2x Audit**.
- **Q2** Wo lebt das User-Setting `last_workspace` genau? Annahme: `User.settings` JSON-Field. Backend-Endpoint noch nicht spezifiziert.
- **Q3** Soll die `enable_case_space_inbox` Setting schon in Phase 1 abgefragt werden (z. B. um die "Suggested Next Steps"-Sektion vorerst auszublenden)? Aktuell wird sie zwar geprüft, aber das Frontend liest sie noch nicht.

### 🐛 Geblockte / verschobene Items

- **1.1.3 Permission-Check** — vollständige Permission-Logik (Role-Group + Membership-Tabelle) ist nicht in P1 enthalten, nur `store.get` als implizite Schranke. Ausführlicher Permission-Layer kommt mit Phase 2 (Bulk-Aktionen erfordern ihn ohnehin).
- **1.1.4 recent_audit_events** — siehe D2.

### 📊 Metriken

- Phase 1 Backend-Stand: **507 Zeilen** neuer Code in 5 Dateien, **10 Tests** grün
- Branch: `case-space` (remote: `origin/case-space`)
- Commits: `83173d0` (Phase 0+1.1) + `306b73c` (DNS) + `95f5139` (Phase 1.5+1.6) + `cf0d283` (Phase 1.7) + `c8af2d9` (Phase 1.8 Typeahead) + `dc692a8` (Phase 1.9 URL-Sync) + `fa2d58d` (Phase 1.11+1.12) + nächster Commit (Phase 2.1–2.4 Inbox Backend + Tests)


## Risiken und Annahmen

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|--------------------|------------|
| Cytoscape.js Bundle bricht Vite-Build | Mittel | Phase-4-Spike vor P4; ggf. vis-network als Fallback |
| LLM-Suggest-Endpoint in P3 nicht nutzbar | Hoch | Feature-Flag `DANWA_LLM_SUGGEST_CASES`; Endpoint optional |
| Inbox-Bulk-Aktionen auf großen Tenants langsam | Niedrig | Async-Job in P2+ falls nötig (Phase-2.1-Review) |
| User findet Welcome-Card nicht | Mittel | A/B-Test in P3-Rollout (zwei Wochen) |
| Graph-Daten unvollständig | Mittel | Phase-5.2: Audit-Event-Hook ergänzt Kanten nachträglich |

## Erfolgsmessung (zur Erinnerung, aus Konzept §16)

- **5-Klick-Regel**: Debatte anlegen + Dokumente + Tags + Audit in ≤ 5 Klicks vom Login
- **Page-Count-Reduktion**: ≥ 30 % weniger Seitenbesuche pro Sitzung
- **Inbox-Quote**: > 80 % der Arbeitstage `inbox.items.length === 0`
- **Graph-Akzeptanz**: ≥ 20 % der Power-User-Sessions nutzen Inspector-Graph oder Browse-Graph
- **Zero Blockier-Wizard**: Benutzer können das System auch ohne Führung benutzen, ohne Nachteile
