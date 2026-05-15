# Plan 18 — Datensicherungs-Strategie (Backup)

> **Branch:** `feature/module-architecture`
> **Dauer:** 1 Sprint (1 Woche)
> **Autor:** Kilo
> **Datum:** 2026-05-14

---

## Ausgangslage & Motivation

Am 14. Mai 2026 wurden durch einen unbekannten Vorgang **sämtliche Benutzerdaten** gelöscht:
- Alle Debate-JSON-Dateien (`data/projects/_default/debates/`)
- Die Audit-Datenbank (`data/audit.db`)
- Die DMS-Vektorspeicher

Die Migration (`migrate_projects.py`) verwendete `shutil.move` (destruktiv), und die App erstellte beim Neustart stillschweigend ein leeres Default-Projekt — ohne Warnung, ohne Fehler.

**Es existiert kein Backup-System.** Das `manage.sh backup` sichert nur Logs und Speicher, nicht die eigentlichen Nutzdaten.

---

## Ziel

Ein robustes, manuell und automatisch (beim Shutdown) triggerbares Backup-System, das:

1. **Alle Benutzerdaten** sichert (Debatten, Projekte, Audit-Trail, DMS)
2. **Kein Cron** benötigt
3. **Keine Dateisystem-ACLs** benötigt
4. **Einzelnes ZIP-Archiv** mit Integritätsprüfung erzeugt
5. **Wiederherstellung** in unter 2 Minuten ermöglicht

---

## Architektur

### 2.1 Zu sichernde Daten

| Pfad | Priorität | Inhalt |
|------|-----------|--------|
| `data/projects/*/debates/*.json` | Kritisch | Alle Debatten (Requests, Runden, Ergebnisse) |
| `data/projects/*/project.json` | Kritisch | Projektdefinitionen |
| `data/db/audit.db` | Kritisch | Audit-Trail (SQLite) |
| `data/projects/*/dms/dms.db` | Kritisch | DMS-Datenbank pro Projekt |
| `data/projects/*/dms/chroma_db/` | Kritisch | Vektorspeicher (Embeddings) |
| `data/a2a_tasks.db` | Mittel | A2A Task-Manager |
| `data/blueprints.db` | Mittel | Blueprint-Repository |
| `config/settings.yaml` | Hoch | App-Konfiguration (ggf. API-Keys) |
| `config/a2a.json` | Hoch | A2A-Server-Konfiguration |
| `config/llm_profiles.yaml` | Hoch | LLM-Profile mit API-Zugängen |

### 2.2 Nicht zu sichernde Daten (exkludiert)

| Pfad | Grund |
|------|-------|
| `.venv/`, `node_modules/` | Generierbar, kein Nutzwert |
| `__pycache__/`, `*.pyc` | Bytecode-Cache |
| `.git/` | In Git versioniert |
| `logs/*.jsonl` | Trace-Logs, nicht kritisch für Wiederherstellung |
| `memory/` | Laufzeitdaten, transient |
| `.env` | Optional (enthält Secrets, sollte separat gesichert werden) |

### 2.3 BackupService (`backend/persistence/backup.py`)

```python
class BackupService:
    """Erstellt, verwaltet und validiert Backup-Archive."""

    BACKUP_DIR = Path(".backups")  # .gitignore'd

    def create_backup(trigger: str = "manual") -> BackupResult:
        """Erstellt ein ZIP-Archiv mit Zeitstempel und Checksummen."""
        1. Timestamp: UTC-ISO-Format → 2026-05-14T08:30:00Z
        2. Dateiname: danwa-backup-2026-05-14T08-30-00Z.zip
        3. Rekursives Durchlaufen aller INCLUDE_PATHS
        4. EXCLUDE_PATTERNS überspringen
        5. SHA-256 pro Datei berechnen → SHA-256SUMS-Datei
        6. Metadata-JSON erzeugen (s. Abschnitt 2.4)
        7. Alles in ein ZIP packen (ZIP64 für >4GB)
        8. ZIP-Checksum berechnen und speichern
        9. BackupResult zurückgeben (Pfad, Größe, Checksum, Dauer, Dateianzahl)

    def list_backups() -> list[BackupMetadata]:
        """Listet alle verfügbaren Backups sortiert nach Datum."""

    def verify_backup(backup_id: str) -> VerificationResult:
        """Prüft Integrität (ZIP-Checksum + SHA-256SUMS)."""

    @staticmethod
    def restore(backup_path: Path) -> RestoreResult:
        """Entpackt und stellt Daten wieder her.
        ⚠️ Überschreibt vorhandene Daten!
        ⚠️ App muss gestoppt sein."""
```

### 2.4 Metadata-JSON (im Backup enthalten)

```json
{
    "version": 1,
    "app_version": "2.0.0",
    "commit_hash": "8a77f82...",
    "created_at": "2026-05-14T08:30:00Z",
    "created_by": "api-endpoint",
    "trigger": "manual",
    "file_count": 342,
    "total_bytes": 83886080,
    "paths_included": ["data/", "config/"],
    "db_schema_versions": {
        "audit.db": "v23",
        "blueprints.db": "v1"
    },
    "danwa_version": "2.0.0"
}
```

---

## API-Endpoints (`backend/api/routers/config.py`)

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| `POST` | `/api/v1/config/backup` | Backup erstellen (Body: `{"trigger": "manual\|shutdown", "include_config": true, "include_memory": false}`) |
| `GET` | `/api/v1/config/backups` | Liste aller Backups mit Metadaten |
| `GET` | `/api/v1/config/backups/{backup_id}` | Backup-Metadaten abrufen |
| `POST` | `/api/v1/config/backups/{backup_id}/verify` | Integrität prüfen |
| `POST` | `/api/v1/config/backups/{backup_id}/restore` | Backup wiederherstellen (⚠️ destruktiv) |

**Response-Modelle:**
```python
class BackupResult(BaseModel):
    backup_id: str          # Dateiname ohne Pfad
    path: str               # .backups/danwa-backup-...
    size_bytes: int
    file_count: int
    created_at: datetime
    sha256: str             # ZIP-Checksum

class BackupMetadata(BaseModel):
    backup_id: str
    created_at: datetime
    app_version: str
    commit_hash: str
    file_count: int
    size_bytes: int
    trigger: str

class VerificationResult(BaseModel):
    valid: bool
    errors: list[str]       # leere Liste = OK
    file_count_verified: int
```

---

## Trigger-Strategie

### 4.1 Manuell (Primär)

Über API oder Frontend-Button: **"Backup erstellen"** in den Einstellungen.

### 4.2 Automatisch bei Shutdown (Sicherheitsnetz)

Im `lifespan()` in `main.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    # ... bestehende Startup-Logik ...

    try:
        yield
    finally:
        # Bei jedem geordneten Shutdown: Auto-Backup
        try:
            from backend.persistence.backup import BackupService
            service = BackupService()
            result = service.create_backup(trigger="shutdown")
            logger.info(
                "Shutdown-Backup erstellt: %s (%d Dateien, %d Bytes)",
                result.path, result.file_count, result.size_bytes,
            )
        except Exception as exc:
            logger.error("Shutdown-Backup fehlgeschlagen: %s", exc)
```

**Warum Shutdown und nicht Cron:**
- Kein externer Scheduler nötig
- Kein Risiko, dass Backup-Daten inkonsistent sind (App läuft noch)
- Bei jedem Deploy/Restart automatisch ein Snapshot
- Git-Commit-Synchronisation: Backup enthält immer den Stand des letzten Stopps

---

## Wiederherstellungsprozess (Disaster Recovery)

### Szenario A: Kompletter Datenverlust

```bash
# 1. App stoppen
./scripts/stop.sh

# 2. Backup entpacken (kopiert data/ und config/ zurück)
python -c "
from backend.persistence.backup import BackupService
BackupService.restore(Path('.backups/danwa-backup-2026-05-14T08-30-00Z.zip'))
"

# 3. Integrität prüfen
python -c "
from backend.persistence.backup import BackupService
result = BackupService.verify_backup('danwa-backup-2026-05-14T08-30-00Z')
print('Valid:', result.valid)
"

# 4. App starten → Migration läuft idempotent
./scripts/start.sh
```

### Szenario B: Einzelne Debate wiederherstellen

```python
from zipfile import ZipFile
with ZipFile("danwa-backup-...zip") as z:
    z.extract("data/projects/_default/debates/abc123.json", path=".")
```

---

## Integration in die Modul-Architektur

Die Backup-Strategie bleibt **modularitäts-agnostisch**:

| Aspekt | Vorher (aktuell) | Nachher (modular) |
|--------|-------------------|---------------------|
| Gesicherte Daten-Pfade | `data/projects/`, `data/*.db` | + `modules/`, `data/modules/` |
| Backup-Umfang | Hardcodierte Pfadliste | Dynamisch: alle installierten Module registrieren ihre Daten-Pfade |
| Wiederherstellung | ZIP entpacken | `POST /api/v1/modules/restore` + Backup-Restore |

Der `BackupService` kennt die INCLUDE-Pfade als Konfiguration. Sobald Module eigene Datenpfade haben, tragen sie diese bei der Installation in die Backup-Konfiguration ein (Observer-Pattern).

---

## Umsetzungsplan

| Aufgabe | Aufwand | Abhängigkeit |
|---------|---------|-------------|
| `BackupService` implementieren | ~1 Tag | Keine |
| API-Endpoints erstellen | ~0,5 Tag | BackupService |
| Shutdown-Auto-Backup in `lifespan()` | ~0,5 Tag | BackupService |
| `.gitignore` aktualisieren (`.backups/`) | 5 Min | Keine |
| Unit-Tests für BackupService | ~0,5 Tag | BackupService |
| Integrationstest (Backup → Löschen → Restore → Verify) | ~1 Tag | BackupService |
| Frontend-Button "Backup erstellen" | ~0,5 Tag | API-Endpoints |
| Dokumentation | ~0,5 Tag | Keine |

**Gesamt: ~4 Tage (1 Sprint)**

---

## Akzeptanzkriterien

- [ ] AC-18.1: `POST /api/v1/config/backup` erstellt gültiges ZIP mit allen Nutzdaten
- [ ] AC-18.2: ZIP-Datei enthält `metadata.json` und `SHA-256SUMS`
- [ ] AC-18.3: `POST /api/v1/config/backups/{id}/verify` meldet gültig/ungültig korrekt
- [ ] AC-18.4: Shutdown erzeugt automatisch ein Backup
- [ ] AC-18.5: Restore stellt Debatten, Projekte und Audit-Trail wieder her
- [ ] AC-18.6: `.backups/` ist in `.gitignore` enthalten
- [ ] AC-18.7: Backup-Daten sind vor dem nächsten Commit nicht in Git sichtbar
- [ ] AC-18.8: Wiederherstellung aus Backup dauert < 2 Minuten

---

## Offene Fragen

1. **Optionaler Upload:** Sollen Backups auch in externen Speicher (S3, MinIO) geschrieben werden? → Für MVP: Nein, nur lokales Dateisystem.
2. **Retention:** Wie viele Backups behalten? → Default: unbegrenzt (Platz ist günstig). Konfigurierbar.
3. **Verschlüsselung:** Sollen Backups verschlüsselt werden? → Für MVP: Nein. Optional in Zukunft.