# Backup-Funktion — Was wird gesichert? Analyse

**Datum:** 2026-06-16
**Status:** 📋 Analyse (kein Code-Fix — bewusst als reine Bestandsaufnahme)
**Schweregrad:** 🟡 Mittel — Backup deckt nicht alle Datenquellen ab, die in der UI angezeigt werden.

---

## Backup-Konfiguration

- **Service:** [`backend/persistence/backup.py`](backend/persistence/backup.py) (Sprint 18)
- **API:** [`backend/api/routers/config.py`](backend/api/routers/config.py) (`/api/v1/config/backup*`)
- **UI:** Configure → Settings → Backup Tab ([`ConfigView.svelte`](frontend/src/views/ConfigView.svelte))
- **Output:** ZIP-Archive in `backups/danwa-backup-<timestamp>.zip` mit SHA-256SUMS + metadata.json
- **Auto-Trigger:** Beim Shutdown (per `main.py:267-272`)

## Was gesichert wird (Standard-Include-Pfade)

```python
INCLUDE_PATHS = [
    # ── Multi-tenant data (JSON file tree) ──────────
    "data/projects",     # legacy project store
    "data/tenants",      # tenant-cased structure (cases, tags, debates, DMS)
    # ── SQLite databases ──────────────────────────
    "data/auth.db",      # users, tenants, memberships
    "data/audit.db",     # audit trail
    "data/a2a_tasks.db", # A2A task queue
    "data/blueprints.db", # blueprints & workflow templates
    "data/modules.db",   # module registry
    "data/profiles.db",  # profile configurations
    # ── i18n translations ─────────────────────────
    "data/i18n",         # UI translation database
    # ── Application config ───────────────────────
    "config/settings.yaml",
    "config/a2a.json",
    "config/llm_profiles.yaml",
]
```

## Was wird NICHT gesichert (kritische Lücken)

### 1. `data/cases/` — Case-Space DMS, Debates, Audit

**Pfad im Code:** `data/tenants/<tenant_id>/cases/<case_id>/{dms.db, chroma_db/, debates/, audit/}`

[`case_store.py:20`](backend/persistence/case_store.py:20): `_DEFAULT_BASE_DIR = Path("data") / "tenants"`
[`case_scoped.py:708-725`](backend/api/routers/case_scoped.py:708): `dms_dir = case_dir / "dms"`, `db_path=str(dms_dir / "dms.db")`

**Im Backup?** `data/tenants` IST im Include-Pfad. Aber:
- `data/tenants/<tenant>/cases/<id>/dms/dms.db` ✅ wird gesichert
- `data/tenants/<tenant>/cases/<id>/dms/chroma_db/` ✅ wird gesichert
- `data/tenants/<tenant>/cases/<id>/debates/` ✅ wird gesichert
- `data/tenants/<tenant>/cases/<id>/audit/` ✅ wird gesichert

**Bewertung:** Pfad ist abgedeckt, **wenn** der Include-Pfad `data/tenants` korrekt matched. **Aber**: Tests in [`case_scoped.py:1012-1015`](backend/api/routers/case_scoped.py:1012) und [`case_scoped.py:1084`](backend/api/routers/case_scoped.py:1084) nutzen `get_case_dir(case_id)` aus `deps.py` — diese Variante nutzt einen Filesystem-Scan-Fallback, der **auch** `data/projects/` durchsucht. Beide Pfade werden also gemischte Daten haben.

### 2. `data/workflows/` — Workflow-Snapshots (Pfad 2+3)

**Pfad im Code:** `data/workflows/<session_id>/snapshot.json` (für MVP-Debatten und Case-Space-Workflow-Execute)

`workflow_exec.py` (Sprint 18) und `case_scoped.py` schreiben Workflow-Snapshots in `data/workflows/<session_id>/`.

**Im Backup?** ❌ **FEHLT.** `data/workflows` ist NICHT im Include-Pfad.

**Auswirkung:** Bei einem Restore gehen alle laufenden und kürzlich abgeschlossenen MVP-Debatten und Case-Space-Workflows verloren. Die zugehörigen `debate.json`-Records in `data/projects/` oder `data/tenants/` sind noch da, aber ohne Snapshot kein Replay/View möglich.

### 3. `memory/dms.db` — DMS Default-Pfad (Pfad 1+2)

**Pfad im Code:** [`services/dms/database.py:21`](backend/services/dms/database.py:21): `db_path = Path("memory/dms.db")` (Default)

**Im Backup?** `memory/` ist im `EXCLUDE_PATTERNS` ([`backup.py:47`](backend/persistence/backup.py:47))! ❌ **FEHLT und aktiv ausgeschlossen.**

**Auswirkung:** Wenn ein User Dokumente über den **legacy** DMS-Pfad (`memory/dms.db`) hochlädt — was passieren kann, wenn der case-scoped DMS-Pfad nicht benutzt wird — sind diese Dokumente **nicht im Backup** und gehen beim Restore verloren.

**Wahrscheinlichkeit:** Mittel. In der Praxis wird der legacy DMS-Pfad vermutlich nicht mehr direkt benutzt, da die UI alles über case-scoped Routen abwickelt. Aber die Library erlaubt es weiterhin.

### 4. DMS ChromaDB-Persistenz

**Pfad im Code:** `data/tenants/<tenant>/cases/<id>/dms/chroma_db/` (case-scoped) ODER `memory/dms_chroma/` (legacy default)

**Im Backup?** Case-scoped: ✅ (über `data/tenants`). Legacy: ❌ (in `memory/`).

### 5. `data/projects/` — Legacy Project Store + Debatten (Pfad 1+2)

**Im Backup?** ✅ `data/projects` ist im Include-Pfad. Alle Legacy-Debatten in `data/projects/<id>/debates/` werden gesichert.

### 6. `data/i18n/` — UI-Translation-DB

**Im Backup?** ✅

### 7. `data/blueprints.db`, `data/modules.db` etc.

**Im Backup?** ✅

## Konsequenz: Welche Daten gehen bei Restore verloren?

| Datenkategorie | Gesichert? | Wiederherstellbar? |
|---|---|---|
| **Cases** (case.json) | ✅ via `data/tenants` | ✅ |
| **Case-DMS (case-scoped)** | ✅ via `data/tenants/.../dms/` | ✅ |
| **Case-Debates (case-scoped)** | ✅ via `data/tenants/.../debates/` | ✅ |
| **Case-Audit** | ✅ via `data/tenants/.../audit/` | ✅ |
| **Case-DMS ChromaDB (case-scoped)** | ✅ via `data/tenants/.../chroma_db/` | ✅ |
| **Legacy Project-Daten** | ✅ via `data/projects` | ✅ |
| **Legacy Project-Debates** | ✅ via `data/projects/<id>/debates/` | ✅ |
| **Legacy Project-DMS (`memory/dms.db`)** | ❌ **NICHT im Backup** | ❌ Datenverlust |
| **Workflow-Snapshots** | ❌ **NICHT im Backup** | ❌ Replay unmöglich |
| **Tags** | ✅ via `data/tenants/<tid>/tags.json` | ✅ |
| **Members (Memberships)** | ✅ via `data/auth.db` | ✅ |
| **Audit-Trail (global)** | ✅ via `data/audit.db` | ✅ |
| **User-Profile / LLM-Configs** | ✅ via `data/profiles.db` + `config/llm_profiles.yaml` | ✅ |
| **A2A-Tasks** | ✅ via `data/a2a_tasks.db` | ✅ |
| **Module-Registry** | ✅ via `data/modules.db` | ✅ |
| **Blueprints/Workflow-Templates** | ✅ via `data/blueprints.db` | ✅ |
| **i18n-Übersetzungen** | ✅ via `data/i18n` | ✅ |
| **Settings, a2a.json, llm_profiles** | ✅ | ✅ |

## Risiko-Bewertung

**Hohes Risiko (Datenverlust bei Restore):**
1. `data/workflows/` — alle laufenden/abgeschlossenen MVP-Debatten verlieren ihren Snapshot
2. `memory/dms.db` — legacy-DMS-Daten

**Mittleres Risiko (Daten verfügbar aber falsch verknüpft):**
- Keine direkten Probleme, da `data/tenants/` und `data/projects/` korrekt erfasst werden

**Niedriges Risiko (kein Impact):**
- Alles andere ist gesichert

## Empfohlener Fix (TDD, ~30 Min)

Drei neue Include-Pfade in `backup.py`:

```python
INCLUDE_PATHS = [
    # ... existing paths ...
    # ── Workflow snapshots (Pfad 2 + 3) ──────────────────────
    "data/workflows",    # MVP + Case-Space workflow snapshots
    # NOTE: the legacy memory/dms.db is intentionally NOT backed up
    # — it is excluded because it is the legacy global DMS store and
    # the case-scoped DMS is the system of record.  Document this in
    # the backup-restore docs so operators do not expect legacy data.
]
```

Tests:
1. `test_backup_includes_workflow_snapshots` — erstelle `data/workflows/<sid>/snapshot.json`, erstelle Backup, prüfe dass die Datei im ZIP ist.
2. `test_backup_does_not_include_legacy_memory_dms` — verifiziere, dass `memory/dms.db` **nicht** im Backup ist (Test für die Ausschluss-Dokumentation).
3. `test_backup_includes_case_scoped_dms_chroma` — verifiziere, dass `data/tenants/<tid>/cases/<id>/dms/chroma_db/` mitgesichert wird.

## Aufschub-Begründung

Diese Lücken sind real, aber:
- Das Workspace/Inbox-System ist nicht produktiv.
- Die meisten Daten sind über `data/tenants/` und `data/projects/` abgedeckt.
- Workflow-Snapshots sind im Restore-Szenario ohnehin nicht garantiert konsistent (laufende Sessions, abgebrochene Workflows).

Wenn das System produktiv geht, ist die Backup-Vervollständigung ein Quick Win (10-20 Zeilen Code + 3 Tests).
