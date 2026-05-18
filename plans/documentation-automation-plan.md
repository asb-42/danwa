# Dokumentation — Automatisierungsplan

## Ziel

Die manuelle Pflege von `docs/technical_documentation.md` und `docs/user_manual.md` reduzieren durch automatisierte Generierung und Aktualisierung. Alles Open Source, keine SaaS-Abhängigkeiten.

## Architektur

```
Codebase (Python + Svelte + FastAPI)
    │
    ├── FastAPI OpenAPI Spec ──→ /docs, /redoc (bereits vorhanden)
    │                              ↓
    │                         docs/api-reference.md (statisch exportiert)
    │
    ├── pdoc ──→ docs/api/ (HTML aus Python Docstrings)
    │
    ├── GitNexus Wiki ──→ docs/architecture/ (aus Knowledge Graph)
    │
    ├── manage.sh doc-update ──→ LLM-basierte Updates:
    │    ├── technical_documentation.md (API-Referenz, Data Models, neue Features)
    │    └── user_manual.md (neue Features, UI-Änderungen)
    │
    └── ADR-Check ──→ docs/adr/ (Template + CI-Validierung)
```

## Phasen

### Phase 1: API-Referenz aus OpenAPI generieren

**Was:** FastAPI generiert automatisch OpenAPI-Spec unter `/openapi.json`. Diese wird als statische Markdown-Datei exportiert und ins Repo committed.

**Aufwand:** Gering (1-2 Stunden)

**Schritte:**
1. Script `scripts/export-openapi.py` — ruft `/openapi.json` vom laufenden Backend ab
2. Konvertiert zu Markdown (mit `openapi-to-markdown` oder eigenem Script)
3. Output: `docs/api-reference.md`
4. `manage.sh doc-api` Command zum Exportieren
5. Optional: In `technical_documentation.md` als Include referenzieren

**Tools:** `openapi-python-client`, `openapi-to-markdown`, oder eigenes Script

**Update-Trigger:** Manuell via `manage.sh doc-api` oder als Git-Hook nach API-Änderungen

---

### Phase 2: pdoc für Python API-Referenz

**Was:** Generiert HTML-Dokumentation aus Python Docstrings für alle Backend-Module.

**Aufwand:** Gering (1-2 Stunden)

**Schritte:**
1. `uv add pdoc` (oder `pip install pdoc`)
2. Docstrings in kritischen Modulen nachrüsten (Router, Services, Models)
3. `manage.sh doc-pdoc` Command: `pdoc backend/ -o docs/api/`
4. Output: `docs/api/index.html` + Unterseiten pro Modul
5. Optional: In GitHub Pages deployen

**Docstring-Priorität:**
1. Router (`backend/api/routers/*.py`) — höchste Priorität, Endpunkte dokumentiert
2. Services (`backend/services/*.py`) — Geschäftslogik
3. Models (`backend/blueprints/models.py`, `backend/modules/models.py`) — Datenstrukturen
4. Repository (`backend/blueprints/repository.py`) — DB-Zugriff

**Update-Trigger:** Manuell via `manage.sh doc-pdoc`

---

### Phase 3: GitNexus Wiki für Architekturdoku

**Was:** Nutzt das bestehende GitNexus-Setup um Architekturdoku aus dem Code-Graph zu generieren.

**Aufwand:** Gering (bereits indexiert)

**Schritte:**
1. `npx gitnexus wiki` — generiert Wiki aus bestehendem Index
2. Output nach `docs/architecture/` kopieren
3. `manage.sh doc-architecture` Command
4. Inhalt in `technical_documentation.md` referenzieren

**Update-Trigger:** Nach `npx gitnexus analyze` (bei größeren Code-Änderungen)

---

### Phase 4: LLM-basierte Doc-Updates

**Was:** `manage.sh doc-update` erkennt Änderungen seit letztem Update und lässt ein LLM die Docs aktualisieren.

**Aufwand:** Mittel (3-4 Stunden)

**Schritte:**
1. `manage.sh doc-update` Command:
   - `git diff HEAD~10 --name-only` → geänderte Dateien
   - Filter: nur `.py`, `.svelte`, `.js` in relevanten Pfaden
   - Prompt generieren: "Diese Dateien haben sich geändert. Aktualisiere die folgenden Doc-Sections: ..."
   - LLM-Call (über bestehendes LLM-Service oder Utility-LLM)
   - Diff anzeigen, User bestätigt oder lehnt ab
   - Bei Bestätigung: Docs updaten, commit erstellen
2. Zwei Modi:
   - `--tech` → nur `technical_documentation.md`
   - `--user` → nur `user_manual.md`
   - `--all` → beide (default)
3. Dry-Run Mode: `--dry-run` zeigt Diff ohne zu schreiben

**Prompt-Struktur:**
```
Du bist ein technischer Redakteur für das Danwa-Projekt.

Folgende Dateien haben sich geändert:
- backend/services/module_profile_sync.py (neu)
- backend/api/routers/llm_profiles.py (geändert)
...

Aktualisiere die folgende Dokumentation basierend auf diesen Änderungen:

[Inhalt von technical_documentation.md]

Regeln:
- Behalte die bestehende Struktur bei
- Füge neue Sections hinzu wo nötig
- Markiere geänderte Stellen mit <!-- UPDATED -->
- Entferne veraltete Informationen
- Output: Nur die aktualisierte Markdown-Datei
```

**Update-Trigger:** Manuell via `manage.sh doc-update`, empfohlen vor Releases

---

### Phase 5: ADR-Workflow

**Was:** Template + Check für Architecture Decision Records. Bei Änderungen an Kern-Architektur wird ein ADR vorgeschlagen.

**Aufwand:** Mittel (2-3 Stunden)

**Schritte:**
1. ADR-Template erstellen: `docs/adr/TEMPLATE.md`
2. `manage.sh adr-new "Titel"` → erstellt neue ADR aus Template
3. `manage.sh adr-check` — scannt `git diff` auf Architektur-Änderungen:
   - Neue Router/Services → ADR vorgeschlagen
   - Geänderte DB-Schemata → ADR vorgeschlagen
   - Neue Modul-Typen → ADR vorgeschlagen
4. Optional: Git-Hook der bei Merge in `main` prüft ob neue Architektur-Änderungen eine ADR benötigen

**ADR-Template:**
```markdown
# ADR-NNN: Titel

**Status:** Proposed | Accepted | Deprecated | Superseded
**Date:** YYYY-MM-DD
**Context:** Was war das Problem?
**Decision:** Was wurde entschieden?
**Consequences:** Was sind die Folgen?
**Affected Files:** Liste der betroffenen Dateien
```

---

### Phase 6: manage.sh Integration

**Was:** Alle Doc-Commands in `manage.sh` integrieren.

**Aufwand:** Gering (1 Stunde)

**Commands:**
```bash
./manage.sh doc              # Übersicht aller Doc-Commands
./manage.sh doc-api          # OpenAPI → docs/api-reference.md
./manage.sh doc-pdoc         # pdoc → docs/api/
./manage.sh doc-architecture # GitNexus Wiki → docs/architecture/
./manage.sh doc-update       # LLM-basierte Doc-Updates
./manage.sh doc-update --tech # Nur technische Doku
./manage.sh doc-update --user # Nur User Manual
./manage.sh doc-update --dry-run # Vorschau ohne Änderungen
./manage.sh doc-all          # Alle Doc-Generierungen nacheinander
./manage.sh adr-new "Titel"  # Neue ADR erstellen
./manage.sh adr-check        # Prüfen ob ADRs fehlen
```

---

## Zeitplan

| Phase | Aufwand | Priorität |
|-------|---------|-----------|
| 1. OpenAPI Export | 1-2h | Hoch |
| 2. pdoc Setup | 1-2h | Hoch |
| 3. GitNexus Wiki | 1h | Mittel |
| 4. LLM Doc-Updates | 3-4h | Hoch |
| 5. ADR-Workflow | 2-3h | Mittel |
| 6. manage.sh Integration | 1h | Hoch |
| **Gesamt** | **9-13h** | |

## Erfolgskriterien

- [ ] `manage.sh doc-all` läuft ohne Fehler
- [ ] `docs/api-reference.md` enthält alle aktuellen Endpunkte
- [ ] `docs/api/` enthält pdoc HTML für alle Backend-Module
- [ ] `docs/architecture/` enthält GitNexus Wiki
- [ ] `technical_documentation.md` ist auf dem Stand der letzten 10 Commits
- [ ] `user_manual.md` erwähnt alle neuen Features der letzten 10 Commits
- [ ] Neue ADRs werden bei Architektur-Änderungen vorgeschlagen

## Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|--------|---------------|
| LLM generiert falsche Doku | Dry-Run Mode, manuelle Bestätigung vor Commit |
| pdoc Docstrings fehlen | Priorisierte Liste, schrittweise nachrüsten |
| OpenAPI-Export veraltet | CI-Check bei API-Änderungen |
| ADR-Check zu aggressiv | Nur bei Änderungen in definierten Kern-Verzeichnissen |
| Docs werden zu groß | Sections aufteilen, Links statt Inline-Content |
