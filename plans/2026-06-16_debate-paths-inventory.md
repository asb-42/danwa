# Debate-Pfade: Bestandsaufnahme + Migrationsstrategie

**Datum:** 2026-06-16
**Status:** 📋 Dokumentation (kein Code-Fix — bewusst aufgeschoben)
**Schweregrad:** 🟡 Mittel — Verzahnung fehlt, aber das System ist aktuell nicht produktiv.

---

## Übersicht: Drei Debate-Pfade

Alle drei Pfade laufen heute (parallel) im Monolithen. Sie unterscheiden sich in **Speicherort**, **Datenformat** und **API-Endpoint**.

### Pfad 1: Legacy-Debatte (Run → New Debate)

**UI-Pfad:** `Run → New Debate`
**Backend:** [`backend/api/routers/debate.py`](backend/api/routers/debate.py) (gesamter Router)
**Datenformat:** `rounds[].agent_outputs[]` (klassische `debate_engine`-Struktur)
**Speicherort:** `data/projects/<project_id>/debates/<debate_id>.json`
  - via `get_debate_store_for_case(project_id)` ([`deps.py:176`](backend/api/deps.py:176))
  - `project_id` kommt aus dem `X-Case-Id`-Header (`get_project_id`)
**Identifier:** `debate_id` (UUID, kein Präfix)
**Tabelle:** [`projects`](backend/persistence/project_store.py) für die Projekt-Metadaten (tenant_id ist effektiv `_default`)
**Audit:** [`audit.py:120`](backend/api/routers/audit.py:120) — `GET /{debate_id_or_title}` über `workflow.audit_logger`

### Pfad 2: MVP-Debatte (Run → MVP Debate)

**UI-Pfad:** `Run → MVP Debate`
**Backend:** [`backend/api/routers/workflow_exec.py:232`](backend/api/routers/workflow_exec.py:232) (`POST /mvp/start`)
**Datenformat:** `node_outputs[]` im **Workflow-Snapshot** (NICHT in `rounds[]`!)
**Speicherort:** zweistufig:
  1. Workflow-Snapshot: `data/workflows/<session_id>/snapshot.json`
  2. Legacy-Debate-Record (für Dashboard/Archive): `data/projects/<project_id>/debates/<debate_id>.json` mit `is_mvp: true` Flag
  - via `get_debate_store_for_case(project_id)` ([`workflow_exec.py:584`](backend/api/routers/workflow_exec.py:584))
**Identifier:** zwei verschiedene IDs!
  - `session_id` = `"wf-<uuid>"` (Workflow-Engine)
  - `debate_id` = `<uuid>` (für Dashboard-Anzeige, mit `is_mvp: true`)
**Tabelle:** `projects` (pro `project_id`)
**Audit:** Hybrid — [`audit.py:139`](backend/api/routers/audit.py:139) fällt für MVP-Debatten auf `workflow.audit_log`-Tabelle zurück

### Pfad 3: Case-Space-Workflow-Execute (Build → Canvas)

**UI-Pfad:** `Build → Canvas → Workflows → Template laden → Execute`
**Backend:** [`backend/api/routers/case_scoped.py:1076`](backend/api/routers/case_scoped.py:1076) (`POST /tenants/{tid}/cases/{cid}/workflows/{wfid}/start`)
**Datenformat:** Workflow-Snapshot (identisch mit MVP-Pfad)
**Speicherort:** zweistufig:
  1. Workflow-Snapshot (über `workflow_exec.start_workflow`)
  2. Legacy-Debate-Record: `data/cases/<tenant_id>/cases/<case_id>/debates/<debate_id>.json` mit `is_mvp: true` und `tenant_id: <tenant>`
  - via `_get_debate_store_for_case(tenant_id, case_id, case_store)` ([`case_scoped.py:61`](backend/api/routers/case_scoped.py:61))
**Identifier:** wie Pfad 2 — `session_id` (wf-…) + `debate_id` (UUID) mit `is_mvp: true`
**Tabelle:** `cases` ([`case_store.py:109`](backend/persistence/case_store.py:109))
**Audit:** [`case_scoped.py:1179`](backend/api/routers/case_scoped.py:1179) — gleicher Hybrid wie MVP

---

## Vergleichstabelle

| Eigenschaft | Pfad 1 (Legacy) | Pfad 2 (MVP) | Pfad 3 (Canvas) |
|---|---|---|---|
| UI-Trigger | Run → New Debate | Run → MVP Debate | Build → Canvas → Execute |
| Backend-Endpoint | `POST /api/v1/debate/` | `POST /api/v1/workflow/mvp/start` | `POST /api/v1/tenants/{tid}/cases/{cid}/workflows/{wfid}/start` |
| Storage-Verzeichnis | `data/projects/<id>/debates/` | `data/projects/<id>/debates/` | `data/cases/<tenant>/cases/<id>/debates/` |
| Tenant-Isolation | ❌ nein (projekt-scoped) | ❌ nein (projekt-scoped) | ✅ ja (case-scoped) |
| Tenant-Mitgliedschaft | implizit via `users.tenant_id` | implizit via `users.tenant_id` | explizit via `MembershipStore` |
| `is_mvp`-Flag | nein | ja | ja |
| Round-Format | `rounds[].agent_outputs[]` | `node_outputs[]` (im Snapshot) | `node_outputs[]` (im Snapshot) |
| Audit-Quelle | `workflow.audit_logger` | `workflow.audit_log`-Tabelle | `workflow.audit_log`-Tabelle |
| Wird vom Workspace-Count erfasst? | ❌ **nein** (Bug E) | ❌ **nein** | ✅ ja (richtig gezählt) |
| Wird vom Inbox angezeigt? | ✅ ja (über `get_inbox`) | ✅ ja | ✅ ja |

---

## Hauptbefund: drei Speicherorte, zwei Tabellen

| Speicherort | Tabelle | Tenant? | Round-Format | Use-Case |
|---|---|---|---|---|
| `data/projects/<id>/debates/` (Pfad 1+2) | `projects` (project_id) | nein | unterschiedlich | Legacy + MVP, beide ohne Tenant |
| `data/cases/<tenant>/cases/<id>/debates/` (Pfad 3) | `cases` (case_id, tenant_id) | ja | Workflow-Snapshot | Case-Space |

Pfad 1 und 2 teilen sich das **gleiche** Speichersystem (`projects` + `data/projects/`), unterscheiden sich aber im Round-Format. Pfad 3 nutzt ein **komplett anderes** Speichersystem (`cases` + `data/cases/`).

## Konsequenz für `get_workspace_summary`

Der Workspace-Count für Cases zählt **nur** Pfad 3. Pfad 1 (Legacy-Debatten) und Pfad 2 (MVP-Debatten) werden **nicht** mitgezählt, wenn sie in `data/projects/` liegen statt in `data/cases/`. Daher:

- Cases mit nur Legacy/MVP-Debatten zeigen `debate_count = 0`
- Cases mit nur Case-Space-Workflows zeigen die richtige Anzahl
- Cases mit gemischten Debatten zeigen nur die Case-Space-Anzahl

Das ist die "fehlende Verzahnung" aus deinem Hinweis.

## Vorschlag: Migrationsstrategie (zur Diskussion)

Drei Optionen, in aufsteigender Invasivität:

### Option 1: Union-Count (schnell, nicht-invasiv)

`get_workspace_summary` zählt in **beiden** DebateStores und gibt die Summe zurück. Vorteile:
- Sofort korrekte Counts für alle Cases
- Kein Daten-Move nötig
- Audit-Trails bleiben unverändert

Nachteile:
- Counts können doppelt zählen, wenn eine Debate in beiden Stores landet (sollte nicht passieren, aber Edge-Case)
- Pfad 1/2-Debatten werden im Workspace-Summary gerendert, aber nicht über den case-scoped Endpunkt editierbar

### Option 2: One-Time-Migration (mittlere Invasivität)

Beim Backend-Start (oder per expliziter CLI): für jeden `projects`-Eintrag mit `tenant_id != _default`, kopiere die `data/projects/<id>/debates/` nach `data/cases/<tenant>/cases/<id>/debates/` und setze `case_id` korrekt. Vorteile:
- Nach der Migration: nur noch eine Datenquelle
- Counts sind automatisch korrekt
- Kann inkrementell gemacht werden (pro Tenant)

Nachteile:
- Audit-Trail-Verlust beim Pfad-1/2 (oder Duplizierung)
- Diskspeicher verdoppelt sich kurzzeitig
- Mapping `project_id` → `case_id` ist nicht 1:1 (ein Projekt kann mehreren Cases entsprechen)

### Option 3: Komplette Vereinheitlichung (große Invasivität)

Pfad 1 wird komplett abgeschaltet. Alle "neuen" Debatten laufen über Pfad 2 (MVP) oder Pfad 3 (Case-Space). Bestehende Legacy-Debatten werden in eine "read-only archive"-Tabelle verschoben.

Vorteile:
- Saubere Architektur, eine Datenquelle
- Tenant-Isolation überall

Nachteile:
- Breaking change
- Verlust der `debate_engine`-Round-Format (oder Migration)
- Migrationsstrategie für die ~100 Alt-Debatten

## Empfehlung

**Option 1 (Union-Count) als schneller Workaround** für die Workspace-Anzeige, kombiniert mit **einer langfristigen Option 3** im Zuge des Danwa-Studio-Splits. Die Verzahnung ist nicht trivial und sollte mit der Studio-Architektur-Entscheidung zusammen erfolgen.

## Was zu tun ist, wenn der Sprint kommt

1. **Entscheidung treffen:** Welche Option? Union-Count als Übergang, dann Vereinheitlichung im Studio?
2. **Test schreiben:** Der Workspace-Count muss nach der Vereinheitlichung alle drei Pfade berücksichtigen.
3. **Daten-Migration:** CLI-Script für die Alt-Debatten, idempotent, mit Trockenlauf.
4. **Schema-Migration:** `cases.debate_ids` als denormalisierte Liste? (Performance-Trade-off vs. Konsistenz)

Aufschub-Begründung: aktuell ist das Workspace/Inbox-System nicht produktiv. Solange niemand es aktiv nutzt, sind die Counts irreführend, aber nicht schädlich.
