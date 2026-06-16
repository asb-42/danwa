# Debate-Pfade: korrigierte Bestandsaufnahme

**Datum:** 2026-06-16
**Status:** 📋 Dokumentation (kein Code-Fix — bewusst aufgeschoben)
**Schweregrad:** 🟡 Mittel — Verzahnung fehlt, aber das System ist aktuell nicht produktiv.

## Wichtige Korrekturen zur vorherigen Bestandsaufnahme

Meine erste Version hatte einen Denkfehler. Hier die korrigierte Sicht:

### 1. Der Workflow Canvas ist **nicht** "alt" — er ist **parallel** zu den anderen Pfaden

Du hast Recht: Der Workflow Canvas (`Build → Canvas`) ist seit Langem im System. Er wurde nicht "an das Case/Tenant-System angepasst" — vielmehr wurde der **Case-Space-Workflow-Execute** als **neue, vierte Variante** daneben gebaut. Pfad 3 ist also:

> **Neuer** Code, der das Case-Space-System nutzt. Er hat den Legacy-Workflow-Code (Pfad 2) als **Vorlage** benutzt, aber Storage und Tenant-Isolation neu gemacht.

Das ist die korrekte Lesart der Geschichte: nicht "Anpassung an Tenant", sondern "neuer Pfad mit Tenant-Support".

### 2. Eine Debatte, die gestern lief, war MVP — und Workspace zeigt sie

Du hast gestern eine **MVP-Debatte** über Pfad 2 (`Run → MVP Debate`) gestartet. Sie landete in `data/projects/<id>/debates/`. Der Workspace zeigt sie als "Debates 1" in "S 201…". Das ist konsistent: der Workspace zählt Case-Space-Workflows (Pfad 3), aber **die Debatte, die du siehst, ist eine MVP-Debatte (Pfad 2)** — also ist sie zufällig in beiden Systemen sichtbar? Nein — sie ist nur in Pfad 2, also sollte der Workspace sie **nicht** sehen.

**Mögliche Erklärung:** Der Case "S 201…" hat **mindestens eine** Case-Space-Workflow-Debatte (Pfad 3), die zufällig auch im Workspace angezeigt wird. Die gestern gelaufene MVP-Debatte ist eine **separate** Debatte, die im Workspace nicht erscheint, weil sie unter `data/projects/` liegt.

Das wäre die korrekte Diagnose: was du im Workspace siehst, ist **nicht** die gestern gestartete Debatte, sondern eine **frühere** Case-Space-Debatte.

### 3. Legacy-Debatten haben **kein** Workflow-Template-Dropdown

Ich habe verifiziert: in [`DebateCreatePanel.svelte`](frontend/src/components/debate/DebateCreatePanel.svelte) gibt es **ein** `WorkflowTemplatePicker`-Dropdown (Zeile 402). Wenn ein Template ausgewählt ist, ruft der Submit-Handler:

```js
if (selectedWorkflowId && selectedWorkflow) {
  const response = await startWorkflow(selectedWorkflowId, caseText, ...);
}
```

`startWorkflow` (Frontend) ruft `POST /api/v1/workflow-exec/{workflow_id}/start` — das ist **Pfad 2 (MVP)**, nicht Pfad 1 (Legacy). Der Legacy-Debatte-Pfad in `debate.py:create_debate` hat **kein** Workflow-Template-Konzept.

Heißt: das `WorkflowTemplatePicker` in `DebateCreatePanel` ist der **MVP-Debatte-Pfad**, nicht der Legacy. Mein vorheriger Eintrag in der Tabelle ("Legacy + MVP teilen sich das `data/projects/`-Speichersystem") ist also korrekt, aber die UI-Trennung ist nicht so sauber wie es aussieht.

### 4. Korrigierte Pfad-Übersicht

| Pfad | UI-Trigger | API-Endpoint | Storage | Template? |
|---|---|---|---|---|
| 1 | Run → New Debate (klassisch) | `POST /api/v1/debate` | `data/projects/<id>/debates/` | ❌ nein |
| 2 | Run → MVP Debate **oder** Run → New Debate + Template | `POST /api/v1/workflow-exec/mvp/start` | `data/projects/<id>/debates/` + Workflow-Snapshot | ✅ ja (Dropdown in `DebateCreatePanel`) |
| 3 | Build → Canvas → Execute | `POST /api/v1/tenants/{tid}/cases/{cid}/workflows/{wfid}/start` | `data/cases/<tenant>/cases/<id>/debates/` + Workflow-Snapshot | ✅ ja (Templates aus Canvas) |

Pfad 1 ist ein dünner Wrapper um `debate_engine` ohne Workflow-Support. Pfad 2 ist der "moderne" Pfad für Run-Seite. Pfad 3 ist die Case-Space-Integration.

## Warum die Counts im Workspace falsch sind

Wenn du im Workspace "S 201…" mit "Debates 1 / Documents 0" siehst, dann:

- **debate_count=1**: Es gibt genau **eine** Case-Space-Workflow-Debatte (Pfad 3) in `data/cases/.../debates/`
- **document_count=0**: Sollte nicht 0 sein wenn du 52 im DMS hast — Bug E sollte das fixen. Ich hatte die Tests geschrieben und grün bekommen, aber vielleicht ist der Test-Setup-Pfad nicht identisch mit dem Production-Pfad. Vorschlag: manueller Test mit Debug-Log.

**Die gestern gelaufene MVP-Debatte** wird im Workspace **nicht** mitgezählt, weil sie unter `data/projects/` liegt.

## Konsequenz

Die "fehlende Verzahnung" ist real, aber meine erste Bestandsaufnahme war ungenau. Die richtige Aussage:

> Das Case-Space-System hat einen **neuen** Workflow-Pfad (Pfad 3) bekommen, der tenant-scoped speichert. Die **alten** Pfade (1+2) wurden nicht migriert, weil der Migrations-Aufwand hoch ist und das System nicht produktiv genutzt wird.

## Vorschlag (aktualisiert)

Die Migrationsoptionen aus meiner ersten Bestandsaufnahme bleiben gültig:

1. **Union-Count** (schnell) — `get_workspace_summary` zählt in beiden Stores. Vorteil: gestern gelaufene MVP-Debatte erscheint im Workspace.
2. **One-Time-Migration** (mittel) — Alt-Debatten nach `data/cases/<tenant>/cases/<id>/` verschieben.
3. **Komplette Vereinheitlichung** (groß) — Pfad 1 abschalten, alle Workflows laufen tenant-scoped.

**Empfehlung unverändert:** Option 1 als Workaround, Option 3 mit Danwa-Studio-Split.

## Zu klärende Fragen für den Sprint

1. **Was passiert mit dem `case_id` in alten Debatten?** Legacy-Debatten haben `project_id` als Top-Level-Key, Case-Debatten haben `case_id`. Mapping `project_id` → `case_id` ist nicht 1:1 (ein Project kann mehreren Cases entsprechen, oder gar keinem).
2. **Werden MVP-Debatten je case-scoped?** Wenn Pfad 2 MVP-Debatten grundsätzlich an einen Case gebunden sein sollen, müsste `createCaseDebate` mit `workflow_template_id` erweitert werden.
3. **Was passiert mit dem `is_cancelled(session_id)`-Check?** MVP-Debatten nutzen `session_id` für Cancel, Legacy-Debatten nutzen `debate_id`. Vereinheitlichung würde eine neue Session-ID-Semantik erfordern.

## Aufschub

Diese Architektur-Entscheidung gehört in den Danwa-Studio-Plan. Aktuell ist das Workspace/Inbox-System nicht produktiv, und die irreführenden Counts schaden niemandem aktiv.
