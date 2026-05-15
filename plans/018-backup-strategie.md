# Plan 18 — Datensicherungs-Strategie (Backup)

> **Branch:** `feature/backup-strategie`
> **Dauer:** 1 Sprint (1 Woche)
> **Autor:** Kilo
> **Datum:** 2026-05-15
> **Status:** In Arbeit

---

## Änderungen gegenüber dem Original-Plan

| # | Änderung | Grund |
|---|----------|-------|
| 1 | Backup-Konfiguration über UI (Konfiguration → System → Backup) statt nur CLI/API | UX-Anforderung: Bedienbarkeit ohne CLI |
| 2 | Checkbox "Automatisches Backup bei Beenden" (Default: **nein**) | Opt-in statt opt-out; Original-Plan hatte Auto-Backup immer aktiv |
| 3 | Button "Backup erstellen" im UI mit Datei-Übersicht | Sofortiges Feedback, welche Daten gesichert werden |
| 4 | Backup-Verzeichnis `backups/` statt `.backups/` | Klar benannt, kein Hidden-Directory |
| 5 | `.gitignore` ergänzt um `backups/` und `backups/*` | Sicherstellung, dass Backups nie in Git landen |
| 6 | Retention-Konfigurierbar über UI (Eingabefeld "Anzahl aufzubewahrender Backups", Default: 0 = unbegrenzt) | Beantwortung offene Frage #2 |
| 7 | Verschlüsselung: Checkbox "Backup verschlüsseln" mit Hinweis "nicht implementiert" | Beantwortung offene Frage #3 |
| 8 | Restore-Button mit explizitem Hinweis "Noch nicht implementiert" | Klare Erwartungshaltung |
| 9 | Kein Upload-Feature (nur lokales Dateisystem) | Beantwortung offene Frage #1 |

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

Ein robustes, manuell und optional automatisch (beim Shutdown) triggerbares Backup-System mit vollständiger UI-Integration, das:

1. **Alle Benutzerdaten** sichert (Debatten, Projekte, Audit-Trail, DMS)
2. **Kein Cron** benötigt
3. **Keine Dateisystem-ACLs** benötigt
4. **Einzelnes ZIP-Archiv** mit Integritätsprüfung erzeugt
5. **Wiederherstellung** in unter 2 Minuten ermöglicht
6. **Über die UI konfigurierbar** ist (Backup-Pfad, automatisches Backup, Retention)

---

## Architektur

### 3.1 Zu sichernde Daten

| Pfad | Priorität | Inhalt |
|------|-----------|--------|
| `data/projects/*/debates/*.json` | Kritisch | Alle Debatten (Requests, Runden, Ergebnisse) |
| `data/projects/*/project.json` | Kritisch | Projektdefinitionen |
| `data/audit.db` | Kritisch | Audit-Trail (SQLite) |
| `data/projects/*/dms/dms.db` | Kritisch | DMS-Datenbank pro Projekt |
| `data/projects/*/dms/chroma_db/` | Kritisch | Vektorspeicher (Embeddings) |
| `data/a2a_tasks.db` | Mittel | A2A Task-Manager |
| `data/blueprints.db` | Mittel | Blueprint-Repository |
| `config/settings.yaml` | Hoch | App-Konfiguration (ggf. API-Keys) |
| `config/a2a.json` | Hoch | A2A-Server-Konfiguration |
| `config/llm_profiles.yaml` | Hoch | LLM-Profile mit API-Zugängen |

### 3.2 Nicht zu sichernde Daten (exkludiert)

| Pfad | Grund |
|------|-------|
| `.venv/`, `node_modules/` | Generierbar, kein Nutzwert |
| `__pycache__/`, `*.pyc` | Bytecode-Cache |
| `.git/` | In Git versioniert |
| `logs/*.jsonl` | Trace-Logs, nicht kritisch für Wiederherstellung |
| `memory/` | Laufzeitdaten, transient |
| `.env` | Enthält Secrets, sollte separat gesichert werden |
| `frontend/dist/` | Build-Artefakt, regenerierbar |
| `backups/` | **Backup-Dateien selbst** (kreisförmig) |

### 3.3 BackupService (`backend/persistence/backup.py`)

```python
class BackupService:
    """Erstellt, verwaltet und validiert Backup-Archive."""

    BACKUP_DIR = Path("backups")  # Git-ignored

    def create_backup(trigger: str = "manual", include_paths: list[str] | None = None) -> BackupResult:
        """Erstellt ein ZIP-Archiv mit Zeitstempel und Checksummen."""
        1. Timestamp: UTC-ISO-Format → 2026-05-15T02:30:00Z
        2. Dateiname: danwa-backup-2026-05-15T02-30-00Z.zip
        3. Dateiliste aus INCLUDE_PATHS (oder Default-Liste) rekursiv durchlaufen
        4. EXCLUDE_PATTERNS überspringen
        5. SHA-256 pro Datei berechnen → SHA-256SUMS-Datei
        6. Metadata-JSON erzeugen (s. Abschnitt 3.5)
        7. Alles in ein ZIP packen (ZIP64 für >4GB)
        8. ZIP-Checksum berechnen und speichern
        9. BackupResult zurückgeben (Pfad, Größe, Checksum, Dauer, Dateianzahl)
        10. Retention anwenden: alte Backups löschen (wenn konfiguriert)

    def list_backups() -> list[BackupMetadata]:
        """Listet alle verfügbaren Backups sortiert nach Datum (neueste zuerst)."""

    def verify_backup(backup_id: str) -> VerificationResult:
        """Prüft Integrität (ZIP-Checksum + SHA-256SUMS)."""

    @staticmethod
    def restore(backup_path: Path) -> RestoreResult:
        """Entpackt und stellt Daten wieder her.
        ⚠️ Überschreibt vorhandene Daten!
        ⚠️ App muss gestoppt sein.
        → NOCH NICHT IMPLEMENTIERT (v1.0 Placeholder)"""

    def get_backup_included_files(backup_id: str) -> list[str]:
        """Gibt die Liste der in einem Backup enthaltenen Dateien zurück."""
```

### 3.4 Backup-Konfiguration (Settings)

Ergänzung in `backend/core/config.py` zur bestehenden `Settings`-Klasse:

```python
class Settings(BaseSettings):
    # ... bestehende Felder ...

    # --- Backup (Sprint 18) ---
    backup_enabled: bool = True
    backup_auto_on_shutdown: bool = False     # Default: nein (opt-in)
    backup_retention_count: int = 0            # 0 = unbegrenzt
    backup_encrypt: bool = False               # Default: nein (noch nicht implementiert)
    backup_dir: str = "backups"
```

Diese Settings werden aus `config/settings.yaml` gelesen (bestehendes Pattern).

### 3.5 Metadata-JSON (im Backup enthalten)

```json
{
    "version": 1,
    "app_version": "1.1.0",
    "commit_hash": "7e40355...",
    "created_at": "2026-05-15T02:30:00Z",
    "created_by": "api-endpoint",
    "trigger": "manual",
    "file_count": 342,
    "total_bytes": 83886080,
    "paths_included": ["data/", "config/"],
    "db_schema_versions": {
        "audit.db": "v25",
        "blueprints.db": "v1"
    },
    "settings": {
        "backup_auto_on_shutdown": false,
        "backup_retention_count": 0,
        "backup_encrypt": false
    }
}
```

---

## API-Endpoints (`backend/api/routers/config.py`)

Ergänzung zu den bestehenden Endpoints:

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| `POST` | `/api/v1/config/backup` | Backup erstellen (Body: `{"trigger": "manual\|shutdown"}`) |
| `GET` | `/api/v1/config/backups` | Liste aller Backups mit Metadaten |
| `GET` | `/api/v1/config/backups/{backup_id}` | Backup-Metadaten abrufen |
| `GET` | `/api/v1/config/backups/{backup_id}/files` | Dateiliste eines Backups abrufen |
| `POST` | `/api/v1/config/backups/{backup_id}/verify` | Integrität prüfen |
| `POST` | `/api/v1/config/backups/{backup_id}/restore` | Backup wiederherstellen (⚠️ destruktiv, **noch nicht implementiert**) |

**Response-Modelle:**
```python
class BackupResult(BaseModel):
    backup_id: str          # Dateiname ohne Pfad, z.B. "danwa-backup-2026-05-15T02-30-00Z.zip"
    path: str               # "backups/danwa-backup-..."
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
    sha256: str             # Hinzugefügt: direkte Prüfsumme in der Übersicht

class BackupFileList(BaseModel):
    backup_id: str
    files: list[str]        # Relative Pfade innerhalb des ZIP
    file_count: int

class VerificationResult(BaseModel):
    valid: bool
    errors: list[str]       # Leere Liste = OK
    file_count_verified: int

class RestoreResult(BaseModel):
    success: bool
    message: str
    restored_files: int = 0
```

---

## Frontend-UI-Konfiguration

### Menü: Konfiguration → System → Backup

Neuer Tab **"Backup"** innerhalb der Konfigurationsansicht (ConfigView.svelte), aufgeteilt in:

#### 4.1 Backup-Einstellungen

| Element | Typ | Default | Beschreibung |
|---------|-----|---------|-------------|
| **Automatisches Backup bei Beenden** | Checkbox | `nein` | Erzeugt bei jedem geordneten Shutdown ein Backup |
| **Anzahl aufzubewahrender Backups** | Zahleneingabe | `0` (unbegrenzt) | Alte Backups werden automatisch gelöscht; 0 = alle behalten |
| **Backup verschlüsseln** | Checkbox (disabled) | `nein` | ⚠️ Hinweis: "Diese Funktion ist noch nicht implementiert" |

#### 4.2 Backup-Aktionen

| Element | Typ | Beschreibung |
|---------|-----|-------------|
| **Backup erstellen** | Button | Erzeugt sofort ein ZIP-Backup; zeigt Fortschritt und Ergebnis an |

#### 4.3 Backup-Übersicht

Tabelle aller vorhandenen Backups mit:
- Dateiname
- Erstellungsdatum
- Größe
- Dateianzahl
- Trigger (manual / shutdown)
- SHA-256-Prüfsumme
- Aktionen: Prüfen, Herunterladen, Wiederherstellen

#### 4.4 Backup-Inhalt-Anzeige

Beim Öffnen eines Backup-Datensatzes oder Klick auf "Details":
- Liste aller im Backup enthaltenen Dateien mit relativen Pfaden
- Gruppierung nach Kategorie (Datenbanken, Projekte, Konfiguration)
- Dateianzahl und Gesamtgröße

#### 4.5 Wiederherstellung

| Element | Typ | Beschreibung |
|---------|-----|-------------|
| **Backup wiederherstellen** | Button (disabled) | ⚠️ Hinweis: "Diese Funktion ist noch nicht implementiert" |

Der Button ist sichtbar aber deaktiviert, mit deutlich sichtbarem Hinweis-Text.

---

## UI-State (Frontend Store)

Ergänzung in `frontend/src/lib/stores.js`:

```javascript
/** Backup-Konfiguration aus den Settings */
export const backupConfig = persisted('danwa.backupConfig', {
    autoOnShutdown: false,
    retentionCount: 0,
    encrypt: false
});

/** Liste der verfügbaren Backups */
export const backups = writable([]);

/** Aktuell geladene Backup-Details (Dateiliste) */
export const backupDetails = writable(null);

/** Ladezustand */
export const isLoadingBackups = writable(false);
```

---

## UI-API-Funktionen (Frontend)

Ergänzung in `frontend/src/lib/api.js`:

```javascript
// Backup (Sprint 18)
export function createBackup(trigger = "manual") {
    return request('/api/v1/config/backup', { method: 'POST', body: { trigger } });
}

export function getBackups() {
    return request('/api/v1/config/backups');
}

export function getBackupDetails(backupId) {
    return request(`/api/v1/config/backups/${backupId}/files`);
}

export function verifyBackup(backupId) {
    return request(`/api/v1/config/backups/${backupId}/verify`, { method: 'POST' });
}

export function restoreBackup(backupId) {
    return request(`/api/v1/config/backups/${backupId}/restore`, { method: 'POST' });
}
```

---

## Shutdown-Auto-Backup

In `backend/main.py`, innerhalb des bestehenden `lifespan()`-Context-Managers:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Debate Engine starting up...")

    # ... bestehende Startup-Logik ...

    yield

    # --- Shutdown-Backup (opt-in via settings) ---
    try:
        from backend.core.config import settings
        if settings.backup_auto_on_shutdown:
            from backend.persistence.backup import BackupService
            service = BackupService()
            result = service.create_backup(trigger="shutdown")
            logger.info(
                "Shutdown-Backup erstellt: %s (%d Dateien, %d Bytes)",
                result.path, result.file_count, result.size_bytes,
            )
    except Exception as exc:
        logger.error("Shutdown-Backup fehlgeschlagen: %s", exc)

    logger.info("Debate Engine shutting down.")
```

---

## .gitignore-Ergänzung

```gitignore
# Backups (lokale Sicherungen, niemals committen)
backups/
backups/*
```

---

## Integration in die bestehende Architektur

### Mapping: Plan → Bestehende Architektur

| Plan-Element | Bestehendes Äquivalent | Ergänzung |
|-------------|----------------------|-----------|
| Settings-Speicher | `config/settings.yaml` | Neuer Abschnitt `backup:` |
| Settings-Klasse | `backend/core/config.py: Settings` | Backup-Felder ergänzen |
| API-Router | `backend/api/routers/config.py` | Backup-Endpoints hinzufügen |
| Shutdown-Hook | `backend/main.py: lifespan()` | Auto-Backup-Callback |
| Frontend-Store | `frontend/src/lib/stores.js` | Backup-stores ergänzen |
| Frontend-API | `frontend/src/lib/api.js` | Backup-API-Funktionen |
| ConfigView | `frontend/src/views/ConfigView.svelte` | Neuer Tab "System → Backup" |

### Abhängigkeiten im `lifespan()` (bestehende Reihenfolge)

1. Logging Setup ✅ (bereits vorhanden)
2. DB-Verzeichnis erstellen ✅ (bereits vorhanden)
3. Project-Migration ✅ (bereits vorhanden)
4. System-Templates seeden ✅ (bereits vorhanden)
5. Module deployen ✅ (bereits vorhanden)
6. **Shutdown-Backup** → kommt nach `yield` (neu)

### Backup-Verzeichnis-Logik

- `backups/` wird im Projekt-Root erstellt (analog zu `logs/`, `data/`)
- Wird bei Bedarf automatisch erstellt durch `BackupService`
- `.gitignore` verhindert versehentliches Committen
- Absolute Pfadauflösung: `Path(__file__).resolve().parent.parent / "backups"`

---

## Umsetzungsplan

| Aufgabe | Aufwand | Abhängigkeit | Status |
|---------|---------|-------------|--------|
| `BackupService` in `backend/persistence/backup.py` | ~1 Tag | Keine | ⬜ Offen |
| Backup-Settings in `core/config.py` ergänzen | ~0,5 Tag | Keine | ⬜ Offen |
| API-Endpoints in `config.py` Router | ~0,5 Tag | BackupService | ⬜ Offen |
| Shutdown-Auto-Backup in `main.py` `lifespan()` | ~0,5 Tag | BackupService, Settings | ⬜ Offen |
| `.gitignore` aktualisieren (`backups/`) | 5 Min | Keine | ⬜ Offen |
| Frontend: Backup-API-Funktionen in `api.js` | ~0,5 Tag | API-Endpoints | ⬜ Offen |
| Frontend: Backup-State in `stores.js` | ~0,25 Tag | Keine | ⬜ Offen |
| Frontend: Backup-Tab in `ConfigView.svelte` | ~1 Tag | API-Endpoints, Stores | ⬜ Offen |
| Unit-Tests für `BackupService` | ~0,5 Tag | BackupService | ⬜ Offen |
| Integrationstest (Backup → Löschen → Restore → Verify) | ~1 Tag | BackupService | ⬜ Offen |
| Dokumentation & Changelog | ~0,5 Tag | Keine | ⬜ Offen |

**Gesamt: ~5,5 Tage (1 Sprint)**

---

## Akzeptanzkriterien

### Muss-Kriterien (Sprint 18)

- [ ] **AC-18.1:** `POST /api/v1/config/backup` erstellt gültiges ZIP mit allen Nutzdaten
- [ ] **AC-18.2:** ZIP-Datei enthält `metadata.json` und `SHA-256SUMS`
- [ ] **AC-18.3:** `GET /api/v1/config/backups` liefert Liste aller Backups mit Metadaten
- [ ] **AC-18.4:** `GET /api/v1/config/backups/{id}/files` liefert die enthaltenen Dateien
- [ ] **AC-18.5:** `POST /api/v1/config/backups/{id}/verify` meldet gültig/ungültig korrekt
- [ ] **AC-18.6:** Shutdown-Backup funktioniert bei aktivierter Einstellung
- [ ] **AC-18.7:** `.backups/` ist in `.gitignore` enthalten (→ `backups/`)
- [ ] **AC-18.8:** Backup-Daten sind vor dem nächsten Commit nicht in Git sichtbar
- [ ] **AC-18.9:** UI: Checkbox "Automatisches Backup bei Beenden" mit Default "nein" funktioniert
- [ ] **AC-18.10:** UI: Button "Backup erstellen" erzeugt sofortiges Backup
- [ ] **AC-18.11:** UI: Anzeige der enthaltenen Dateien pro Backup
- [ ] **AC-18.12:** UI: Eingabefeld "Anzahl aufzubewahrender Backups" funktioniert
- [ ] **AC-18.13:** UI: Backup-Wiederherstellen-Button ist sichtbar aber deaktiviert mit Hinweistext
- [ ] **AC-18.14:** UI: Verschlüsselungs-Checkbox mit Hinweistext "nicht implementiert"

### Kann-Kriterien (zukünftige Sprints)

- [ ] **AC-18.15:** Manueller Backup-Download im Browser
- [ ] **AC-18.16:** Backup-Upload und -Restore über UI (nach Implementierung)
- [ ] **AC-18.17:** Backup-Verschlüsselung (nach Implementierung)
- [ ] **AC-18.18:** Externer Upload (S3, MinIO) — optional

---

## Sicherheitsüberlegungen

- `config/settings.yaml` kann API-Keys enthalten → wird nur bei aktivierter Backup-Config-Einstellung mitgesichert
- `.env` wird **nicht** mitgesichert (enthält Secrets, sollte separat gesichert werden)
- Backup-Dateien enthalten sensible Projekt-Daten → Zugriffskontrolle über Dateisystem-Berechtigungen
- Keine Verschlüsselung in v1.0 (optional in Zukunft)

---

## Offene Fragen (beantwortet)

| # | Frage | Antwort |
|---|-------|---------|
| 1 | Optionaler Upload (S3, MinIO)? | **Nein** für MVP. Nur lokales Dateisystem. Optional in Zukunft. |
| 2 | Retention: Wie viele Backups behalten? | **Default: unbegrenzt** (0 = alle behalten). Konfigurierbar über UI mit Eingabefeld "Anzahl aufzubewahrender Backups". |
| 3 | Verschlüsselung? | **Nein** für MVP. Checkbox "Backup verschlüsseln" im UI vorgesehen, aber mit Hinweis "noch nicht implementiert". Optional in Zukunft. |

---

## Abhängigkeiten zu anderen Plänen

| Plan | Beziehung |
|------|-----------|
| [Plan 017 — Versionierung](https://github.com/asb-42/danwa/blob/main/archive/plans/017-versionierung.md) | ✅ Abgeschlossen — `app_version` wird dynamisch aus `/version` gelesen und in Backup-Metadata geschrieben |
| [Plan 016 — Service LLM](https://github.com/asb-42/danwa/blob/main/archive/plans/016-service-llm.md) | ✅ Abgeschlossen — Kein direkter Einfluss auf Backup |
| [Plan 009 — Modularisierung](https://github.com/asb-42/danwa/blob/main/archive/plans/009-modularisierung-gesamtplan.md) | 🔶 Modul-System soll zukünftig eigene Datenpfade registrieren können → BackupService muss erweiterbar sein |

