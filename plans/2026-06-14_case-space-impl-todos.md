# Implementation TODO: Case-Space Workspace

> Gehört zu: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md)
> Status: Plan (nicht begonnen)
> Sprache: Deutsch (für Konsistenz mit dem Konzeptdokument)
> Schrittgröße: jede Checkbox ist ein in sich geschlossenes Inkrement

---

## Phase 0 — Vorbereitung (vor P1)

- [ ] **0.1 Konzept-Readout** mit Stakeholdern terminieren (Doku: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md))
- [ ] **0.2 Feature-Flag-System** prüfen: existiert bereits `DANWA_ENABLE_CASE_SPACE` o. ä.? Wenn nein, in [`backend/core/config.py`](../../backend/core/config.py) hinzufügen (Default: `False` bis P1 abgeschlossen)
- [ ] **0.3 Frontend-Routing**: bestehende SvelteKit-/Vite-Routes auf `src/routes/` oder äquivalent prüfen, Platzhalter `/workspace`, `/inbox`, `/browse` reservieren
- [ ] **0.4 Sidebar-Komponente** [`frontend/src/components/Sidebar.svelte`](../../frontend/src/components/Sidebar.svelte) Stand aufnehmen, Refactor-Bedarf dokumentieren
- [ ] **0.5 Datenmodell-Readback**: bestätigen, dass `case.tag_ids`, `debate.tag_ids`, `document.case_id` existieren und die im Konzept beschriebenen Abfragen tragen
- [ ] **0.6 i18n-Keys** anlegen: Namespaces `caseSpace.workspace.*`, `caseSpace.inbox.*`, `caseSpace.browse.*` in der Default-Locale (DE) + EN
- [ ] **0.7 Test-Fixture** für ein Demo-Tenant mit 3 Cases / 8 Debatten / 12 Docs / 6 Tags / 4 Audit-Events anlegen (für visuelle Smoke-Tests)

## Phase 1 — Workspace-Hauptansicht (P1)

### Backend
- [ ] **1.1 Endpoint `GET /api/workspace/summary?case_id=…`** in neuem Router [`backend/api/routers/workspace.py`](../../backend/api/routers/workspace.py) anlegen
  - [ ] 1.1.1 Query-Param-Validierung (Pydantic)
  - [ ] 1.1.2 Aggregation: `case`, `case.debates`, `case.documents`, `case.tags`, `case.recent_audit_events` (max 10)
  - [ ] 1.1.3 Permission-Check: aktueller User hat `case.tenant_id` Membership
  - [ ] 1.1.4 Response-Schema in [`backend/models/schemas.py`](../../backend/models/schemas.py) (`WorkspaceSummary`)
- [ ] **1.2 Endpoint `GET /api/cases/search?q=…`** (Typeahead)
  - [ ] 1.2.1 Limit auf 10 Treffer, Debounce-fähig
  - [ ] 1.2.2 Permission-Filter: nur Cases, die der User sehen darf
  - [ ] 1.2.3 OpenAPI-Doc mit `tag_ids`-Beispiel
- [ ] **1.3 User-Setting `last_workspace`** in `user.settings` (JSON-Field) hinzufügen
  - [ ] 1.3.1 Migration/Default: leerer String
  - [ ] 1.3.2 PATCH-Endpunkt zum Aktualisieren (`PUT /api/users/me/workspace`)
- [ ] **1.4 Tests** (Pytest):
  - [ ] 1.4.1 Test 1.1: Workspace-Summary liefert alle 4 Subkollektionen
  - [ ] 1.4.2 Test 1.2: Tenant-Filter verhindert Cross-Tenant-Datenleck
  - [ ] 1.4.3 Test 1.3: Typeahead-Suche ist case-insensitiv und paginiert
  - [ ] 1.4.4 Test 1.4: `last_workspace` Round-Trip

### Frontend
- [ ] **1.5 Store `workspaceStore.svelte.js`** in [`frontend/src/lib/stores/`](../../frontend/src/lib/stores/) anlegen
  - [ ] 1.5.1 State: `summary`, `loading`, `error`
  - [ ] 1.5.2 Actions: `load(caseId)`, `setActiveCase(caseId)`, `clear()`
- [ ] **1.6 API-Wrapper** [`frontend/src/lib/api/workspace.js`](../../frontend/src/lib/api/workspace.js): `getWorkspaceSummary`, `searchCases`, `saveLastWorkspace`
- [ ] **1.7 Komponente `WorkspaceView.svelte`** in [`frontend/src/views/`](../../frontend/src/views/)
  - [ ] 1.7.1 Header mit Tenant- + Case-Selector (Combobox)
  - [ ] 1.7.2 Drei Karten: `ThisCaseCard`, `SuggestedNextStepsCard`, `RecentActivityCard`
  - [ ] 1.7.3 Leerer Zustand mit Hinweis "Select a case to focus your workspace"
- [ ] **1.8 Komponente `CaseSelector.svelte`** (Erweiterung der bestehenden [`CaseSelector.svelte`](../../frontend/src/components/CaseSelector.svelte))
  - [ ] 1.8.1 Typeahead-Combobox
  - [ ] 1.8.2 Aktiver Case optisch markiert
  - [ ] 1.8.3 Tastatur-Navigation (↑/↓/Enter/Esc)
- [ ] **1.9 URL-State-Synchronisation**: Query-Param `?case=…` lesen + schreiben (kein SvelteKit-`$page`-Hack; einfacher `URLSearchParams`-Effekt)
- [ ] **1.10 Login-Default-Wiederherstellung**: nach Login `last_workspace` lesen und Case automatisch setzen
- [ ] **1.11 Sidebar-Eintrag "Workspace"** in [`Sidebar.svelte`](../../frontend/src/components/Sidebar.svelte) hinzufügen, *oberhalb* der bestehenden technischen Kategorien
- [ ] **1.12 Routing**: `/workspace` als Default-Route konfigurieren, falls Feature-Flag aktiv
- [ ] **1.13 Frontend-Tests** (Vitest):
  - [ ] 1.13.1 `workspaceStore` Reducer (load / setActiveCase / clear)
  - [ ] 1.13.2 `CaseSelector` Typeahead-Filter
  - [ ] 1.13.3 `WorkspaceView` Empty-State
- [ ] **1.14 E2E-Playwright-Test**: Login → Workspace rendert → Case-Wechsel aktualisiert alle 3 Karten
- [ ] **1.15 Lint + Format**: `ruff check . && ruff format --check .` und `pnpm lint` müssen grün sein
- [ ] **1.16 Commit + Push** als `feat(workspace): phase 1 — case summary, selector, default view`

## Phase 2 — Inbox (P2)

### Backend
- [ ] **2.1 Endpoint `GET /api/inbox?tenant_id=…`** anlegen
  - [ ] 2.1.1 Query: `documents WHERE case_id IS NULL AND tenant_id=?`
  - [ ] 2.1.2 Query: `debates WHERE tag_count = 0 AND tenant_id=?`
  - [ ] 2.1.3 Query: `debates WHERE status='completed' AND completed_at > now-7d`
  - [ ] 2.1.4 Query: `audit_events WHERE mentioned_user_id=?` (falls Spalte existiert; sonst skippen)
  - [ ] 2.1.5 Sortierung: neueste zuerst, optional Limit (default 50)
- [ ] **2.2 Bulk-Endpoints** (alle atomar, alle Permission-geprüft):
  - [ ] 2.2.1 `POST /api/inbox/bulk-move` mit `{item_type, item_ids, target_case_id}`
  - [ ] 2.2.2 `POST /api/inbox/bulk-tag` mit `{item_type, item_ids, tag_ids: [...]}`
  - [ ] 2.2.3 `POST /api/inbox/bulk-archive` mit `{item_type, item_ids}`
- [ ] **2.3 Permission-Regel**: nur `tenant.member` darf Bulk auf Items im selben Tenant; Cross-Tenant strikt verboten
- [ ] **2.4 Tests** (Pytest):
  - [ ] 2.4.1 Inbox liefert nur Items des aktuellen Tenants
  - [ ] 2.4.2 Bulk-Move aktualisiert `case_id` und triggert Workspace-Refresh-Event
  - [ ] 2.4.3 Bulk-Tag akzeptiert leere Tag-Liste als No-op (nicht als 400)
  - [ ] 2.4.4 Bulk-Archive erzeugt Audit-Event

### Frontend
- [ ] **2.5 Store `inboxStore.svelte.js`**
  - [ ] 2.5.1 State: `items`, `selectedIds`, `loading`, `error`
  - [ ] 2.5.2 Actions: `load`, `select`, `clearSelection`, `bulkMove`, `bulkTag`, `bulkArchive`
- [ ] **2.6 API-Wrapper** [`frontend/src/lib/api/inbox.js`](../../frontend/src/lib/api/inbox.js)
- [ ] **2.7 Komponente `InboxView.svelte`**
  - [ ] 2.7.1 Tabs: `Unlinked Documents` / `Untagged Debates` / `Recently Completed` / `My Mentions`
  - [ ] 2.7.2 Jeder Tab: Checkbox-Liste + Action-Bar am unteren Rand
  - [ ] 2.7.3 Bulk-Action-Bar erscheint nur bei `selectedIds.length > 0`
  - [ ] 2.7.4 "All clear"-Badge bei leerem State
- [ ] **2.8 Komponente `InboxItemRow.svelte`** (generisch, drei Slots: icon, title, suggested actions)
- [ ] **2.9 Inline-Action-Dropdowns** ("Move to Case ▾", "Tag with ▾") mit Combobox und Live-Suche
- [ ] **2.10 Sidebar-Badge** mit `inboxStore.items.length` (rot bei > 0, grau bei 0)
- [ ] **2.11 Frontend-Tests**:
  - [ ] 2.11.1 `inboxStore` Bulk-Actionen
  - [ ] 2.11.2 `InboxView` Tab-Wechsel behält Selektion nicht bei (gewollt)
- [ ] **2.12 E2E-Playwright**: Bulk-Move von 3 Docs → Workspace reflektiert die Änderung
- [ ] **2.13 Commit + Push** als `feat(inbox): phase 2 — unlinked items and bulk actions`

## Phase 3 — Welcome + Onboarding-Feinschliff (P3)

### Backend
- [ ] **3.1 Endpoint `GET /api/onboarding/state?tenant_id=…`** liefert `{has_cases, has_documents, has_debates}` Booleans
- [ ] **3.2 Optionaler Endpoint `POST /api/documents/{id}/suggest-case`** (LLM): wenn ein LLM konfiguriert ist, gibt die Top-3-Case-Vorschläge zurück; sonst 404. *Feature-Flag `DANWA_LLM_SUGGEST_CASES`*

### Frontend
- [ ] **3.3 Komponente `WelcomeCard.svelte`** — drei Karten (Create Case / Upload Documents / Start Debate), `+ Add`-Buttons
- [ ] **3.4 Logik**: Welcome-Card rendert nur, wenn `onboarding.state.has_cases === false`
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
