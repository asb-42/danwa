# Missing Links – Unimplemented UI Elements

Dieses Dokument listet alle UI-Elemente auf, die im Code vorhanden sind (Backend-API, Translation-Keys, Komponenten), aber noch nicht vollständig in die Benutzeroberfläche integriert sind.

---

## Priorität 1: Hoher Nutzen / Geringer Aufwand

### 1. Reports-Generierung: Eigenständige Seite
| Attribut | Wert |
|----------|------|
| **Status** | API implementiert, UI fehlt |
| **Priorität** | Hoch |
| **Aufwand** | Mittel |

**Vorhanden:**
- API: `generateReport()`, `getReportStatus()`, `downloadReport()`, SSE-Progress-Stream (`src/lib/api.js:424-448`)
- Translation-Keys: `report.title`, `report.generate`, `report.format`, `report.status.*`, `report.download` (en.js + de.js)
- `DebateReportPanel`-Komponente existiert in `DebateView.svelte` (Zeile 1006)

**Fehlt:**
- `ReportsView.svelte` (eigene Seite)
- Route `#/reports` in `App.svelte`
- Navigations-Eintrag in `Sidebar.svelte`
- Report-Generierungsformular (Sitzung + Format auswählen)
- Job-Status-Anzeige (pending/completed/failed)
- Download-Button für fertige Berichte

---

### 2. Backend-Logs: Eigenständige Seite
| Attribut | Wert |
|----------|------|
| **Status** | API implementiert, UI teilweise vorhanden |
| **Priorität** | Hoch |
| **Aufwand** | Gering |

**Vorhanden:**
- API: `getBackendLogs()` (`src/lib/api.js:386-390`)
- UI-Teil existiert inline in `ConfigView.svelte` (System-Tab, Zeilen 977-994)

**Fehlt:**
- `LogsView.svelte` (eigene Seite)
- Route `#/logs` in `App.svelte`
- Navigations-Eintrag in `Sidebar.svelte`
- Auto-Refresh-Toggle
- Log-Level-Filterung (ERROR, WARN, INFO, DEBUG)
- Regex-Suche
- Download als Datei

---

## Priorität 2: Mittlerer Nutzen / Mittlerer Aufwand

### 3. A2A Agenten-Verwaltung
| Attribut | Wert |
|----------|------|
| **Status** | Komponente existiert, keine Navigation |
| **Priorität** | Mittel |
| **Aufwand** | Mittel |

**Vorhanden:**
- `A2ACapabilities.svelte`-Komponente (`src/components/blueprint/A2ACapabilities.svelte`)
- `A2AApprovalCard.svelte` wird in `InputComposerView.svelte` verwendet (Zeilen 348-363)
- Translation-Keys vollständig vorhanden (en.js Zeilen 384-394, de.js Zeilen 382-394)
- Discovery-Feature (`.well-known/agent.json`)

**Fehlt:**
- `A2AAgentsView.svelte` (eigene Seite)
- Route `#/a2a-agents` in `App.svelte`
- Navigations-Eintrag in `Sidebar.svelte`
- Liste konfigurierter externer Agenten
- Add/Edit/Remove-Formulare
- Capabilities-Anzeige (Skills, Input/Output-Modi)
- Test-Connection-Button
- Discovery-Feature ("Entdecken"-Button)

---

### 4. Sitzungs-Archiv-Verwaltung
| Attribut | Wert |
|----------|------|
| **Status** | API implementiert, UI teilweise vorhanden |
| **Priorität** | Mittel |
| **Aufwand** | Mittel |

**Vorhanden:**
- API: `softDeleteSession()`, `restoreSession()` (`src/lib/api.js:469-475`)
- Archivieren/Wiederherstellen-Buttons sind inline in `ArchiveView.svelte` vorhanden
- Translation-Keys: `session.softDelete`, `session.restore`, `session.archived`

**Fehlt:**
- `ArchiveManagerView.svelte` (eigene Seite)
- Route `#/archive-manager` in `App.svelte`
- Navigations-Eintrag in `Sidebar.svelte`
- Gefilterte Liste (Datum, Projekt)
- Bulk-Aktionen (mehrere wiederherstellen/löschen)
- Option für endgültiges Löschen

---

### 5. Profil-Hot-Reload mit UI-Feedback
| Attribut | Wert |
|----------|------|
| **Status** | API implementiert, UI minimal |
| **Priorität** | Mittel |
| **Aufwand** | Gering |

**Vorhanden:**
- API: `reloadProfiles()` (`src/lib/api.js:382-384`)
- Button existiert in ConfigView > System-Tab (Zeile 961)

**Fehlt:**
- Live-Fortschrittsindikator während des Reloads
- Zusammenfassung der Änderungen (hinzugefügte/aktualisierte/entfernte Profile)
- Detaillierte Fehlerberichterstattung

---

## Priorität 3: Geringerer Nutzen / Höherer Aufwand

### 6. Blueprint-Layout-Persistenz (Backend-Anbindung)
| Attribut | Wert |
|----------|------|
| **Status** | Teilweise implementiert |
| **Priorität** | Mittel-Niedrig |
| **Aufwand** | Mittel |

**Vorhanden:**
- API: `getCanvasLayout()`, `createCanvasLayout()`, `updateCanvasLayout()` (`src/lib/blueprint/api.js`)
- Save/Load/Delete-Dialoge existieren in `BlueprintCanvasView.svelte`
- Palette zeigt "No saved layouts" an

**Fehlt:**
- `listCanvasLayouts()` wird nie aufgerufen → Layouts werden nicht in der Palette angezeigt
- Auto-Laden beim App-Start
- Versions-/Historienunterstützung
- Layout-Umbenennung, Duplizierung, Export/Import als JSON

---

### 7. Multi-Profil-Kostenvergleich
| Attribut | Wert |
|----------|------|
| **Status** | API implementiert, UI-Basis vorhanden |
| **Priorität** | Niedrig |
| **Aufwand** | Mittel |

**Vorhanden:**
- API: `estimateCost()` (`src/lib/api.js:246-248`)
- Basisformular im Config-Tab "Cost" (Zeilen 868-902)
- Translation-Keys: `config.costEstimate`, `config.estimatedCost`

**Fehlt:**
- Auswahl mehrerer LLM-Profile zum Vergleich
- Visuelles Balkendiagramm für den Vergleich
- Zusammenfassungsempfehlung (bestes Kosten-Nutzen-Verhältnis)

---

### 8. Eigenständige Workflow-Ausführungs-Seite
| Attribut | Wert |
|----------|------|
| **Status** | Komponente implementiert, nicht eigenständig nutzbar |
| **Priorität** | Niedrig |
| **Aufwand** | Hoch |

**Vorhanden:**
- `ExecutionPanel.svelte` (`src/components/blueprint/ExecutionPanel.svelte`) ist voll funktionsfähig
- Übersetzungs-Keys vollständig vorhanden (`workflow.execution.*`)

**Fehlt:**
- `WorkflowExecutionView.svelte` (eigene Seite)
- Route `#/execution` in `App.svelte`
- Navigations-Eintrag oder Floating-Action-Button
- Mehrere gleichzeitige Ausführungen (Multi-Session-Ansicht)
- Ausführungswarteschlange-Management
- Pause/Fortsetzen/Abbruch-Steuerung
- Ausführungsverlauf pro Workflow

---

## Zusätzliche fehlende Integrationen

### 9. Übersetzungs-Dashboard: Keine Navigation
- **Status**: `TranslationDashboard.svelte` existiert, Route `#/translation` ist in `App.svelte` eingerichtet
- **Fehlt**: Navigations-Eintrag in `Sidebar.svelte` (Key `nav.translation` existiert in en.js/de.js, aber wird nicht verwendet)

### 10. Optimierungs-Vorschläge: Unbenutzte Komponente
- **Status**: `ProposalsPanel.svelte` existiert mit voller Funktionalität (Approve/Reject über `/api/v1/optimization-proposals/*`)
- **Fehlt**: Wird nirgends importiert oder eingebunden; `workflow.reflect.proposals`-Translation-Key existiert, hat aber kein UI

### 11. Modul-Manager: Keine eigene Seite
- **Status**: `ModuleManager.svelte` existiert, ist in `ConfigView.svelte` eingebunden (`modules`-Tab)
- **Fehlt**:Eigenständige Seite, Sidebar-Navigation, direkte Module-Registrierung/Deinstallation außerhalb der Config

### 12. Dashboard Workflow-Graph: Platzhalter
- **Status**: Platzhalter-Box in `Dashboard.svelte` (Zeile 183-188)
- **Text**: "Workflow graph visualization — coming in Sprint 4" / "Workflow-Graph-Visualisierung — kommt in Sprint 4"
- **Fehlt**: ELK.js-Graphvisualisierung

### 13. Audit Trail Visualisierung: Platzhalter
- **Status**: Platzhalter-Box in `AuditView.svelte` (Zeile 182-187)
- **Text**: "Audit trail visualization — coming in Sprint 4" / "Prüfpfad-Visualisierung — kommt in Sprint 4"
- **Fehlt**: Graphische Visualisierung des Audit-Trails

---

## Zusammenfassung

| Kategorie | Anzahl | Wesentliche Punkte |
|-----------|--------|-------------------|
| Neue Seiten + Routen + Sidebar-Navigation | 4 | Reports, Logs, A2A-Agenten, Archiv-Manager |
| Vorhandene Komponenten erweitern | 3 | Hot-Reload-Feedback, Kostenvergleich, Execution-Panel eigenständig |
| Layout-Persistenz (Backend ↔ UI) | 1 | Blueprint-Layout-Listen/-Laden/-Speichern |
| Fehlende Navigations-Einträge | 2 | Übersetzungs-Dashboard, Modul-Manager |
| Unbenutzte Komponenten integrieren | 1 | Optimierungs-Vorschläge |
| Platzhalter-Visualisierungen | 2 | Dashboard-Workflow-Graph, Audit-Trail |

**Gesamt: 13 nicht implementierte UI-Elemente**

---

*Erstellt: 2026-05-15*
*Quellen: App.svelte, Sidebar.svelte, ConfigView.svelte, Dashboard.svelte, BlueprintCanvasView.svelte, AuditView.svelte, ArchiveView.svelte, DebateView.svelte, TranslationDashboard.svelte, OutputComposerView.svelte, InputComposerView.svelte, DocumentsView.svelte, ExecutionPanel.svelte, ProposalsPanel.svelte, api.js, en.js, de.js, missing-links-todo.md (ursprünglich)*