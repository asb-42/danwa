# Strangulierungs-Audit: Chainlit → FastAPI/Svelte Migration

**Datum:** 2026-05-02  
**Auditor:** Roo (Code Mode)  
**Scope:** Gesamtes Repository auf Chainlit-Reste und Migrationsschmutz

---

## TL;DR

> **Chainlit-Dependency wurde aus `pyproject.toml` entfernt** ✅  
> **Aber:** 14 Dateien enthalten noch Chainlit-Referenzen.  
> **Kritisch:** `scripts/start.sh` und `setup.sh` starten noch Chainlit statt FastAPI.  
> **Gesamtstatus:** 🟡 Migration ~60% — Backend bereinigt, Frontend/Skripte/Docs nicht.

---

## 1. Dateien mit "chainlit" im Namen oder Inhalt

### 🔴 Aktion: LÖSCHEN (Chainlit-UI, komplett ersetzt durch `frontend/`)

| Datei | Zeilen | Chainlit-Import | Aktion | Begründung |
|-------|--------|-----------------|--------|------------|
| [`src/ui/chainlit_app.py`](src/ui/chainlit_app.py) | 1016 | `import chainlit as cl` | **LÖSCHEN** | Haupt-Chainlit-App. Komplett ersetzt durch `frontend/src/` + `debate_engine/api/` |
| [`src/ui/dashboard.py`](src/ui/dashboard.py) | 49 | `import chainlit as cl` | **LÖSCHEN** | Chainlit-Dashboard. Ersetzt durch `frontend/src/views/Dashboard.svelte` |
| [`src/ui/dms_dashboard.py`](src/ui/dms_dashboard.py) | 303 | `import chainlit as cl` | **LÖSCHEN** | Chainlit-DMS-UI. Ersetzt durch `frontend/src/views/` (DMS-Integration) |
| [`chainlit.md`](chainlit.md) | 15 | Chainlit welcome screen | **LÖSCHEN** | Chainlit-Willkommensbildschirm. Nicht mehr benötigt. |
| [`.chainlit/config.toml`](.chainlit/config.toml) | 179 | Chainlit-Konfiguration | **LÖSCHEN** | Chainlit-spezifische Konfiguration (session_timeout, features, UI-Settings) |
| [`.chainlit/translations/`](.chainlit/translations/) | 25 Dateien | Chainlit-i18n | **LÖSCHEN** | Chainlit-Übersetzungen. Ersetzt durch `frontend/src/lib/i18n/` |

### 🟡 Aktion: MIGRIEREN (Chainlit-Referenz entfernen, Rest behalten)

| Datei | Zeile(n) | Fund | Aktion | Begründung |
|-------|----------|------|--------|------------|
| [`src/core/logging_config.py`](src/core/logging_config.py) | 32–33 | `logging.getLogger("chainlit").setLevel(logging.WARNING)` | **ZEILE LÖSCHEN** | Chainlit-Logger existiert nicht mehr. Litellm-Zeile behalten. |

### 🟢 Aktion: TESTS LÖSCHEN (Chainlit-Tests, nicht mehr relevant)

| Datei | Zeilen | Chainlit-Bezüge | Aktion | Begründung |
|-------|--------|-----------------|--------|------------|
| [`tests/test_chainlit_app.py`](tests/test_chainlit_app.py) | ~330 | 100% Chainlit-Mocking | **LÖSCHEN** | Testet nur Chainlit-UI. Neue Tests in `tests_debate_engine/` |
| [`tests/test_debate_engine_rag.py`](tests/test_debate_engine_rag.py) | ~440 | 90% Chainlit-Mocking | **LÖSCHEN** | Testet RAG via Chainlit-UI. Muss als API-Tests neu geschrieben werden. |
| [`tests/test_dms_integration.py`](tests/test_dms_integration.py) | ~30 | `patch("src.ui.chainlit_app.DMS")` | **LÖSCHEN** | Testet DMS via Chainlit. Muss als API-Tests neu geschrieben werden. |
| [`tests/test_logging_config.py`](tests/test_logging_config.py) | 72–84 | `test_setup_logging_configures_chainlit_level` | **TEST LÖSCHEN** | Testet Chainlit-Logger-Config. Nach Logging-Cleanup nicht mehr relevant. |

### 🔵 Aktion: DOKUMENTATION AKTUALISIEREN

| Datei | Zeile(n) | Fund | Aktion | Begründung |
|-------|----------|------|--------|------------|
| [`README.md`](README.md) | 77–78 | `UI Framework: Chainlit` | **ÄNDERN** → `UI Framework: Svelte 5 + Tailwind CSS` | Technologie-Stack aktualisieren |
| [`README.md`](README.md) | 120–122 | `chainlit_app.py # Main entry point` | **ÄNDERN** → `debate_engine/main.py` + `frontend/` | Projektstruktur aktualisieren |
| [`docs/user_manual.md`](docs/user_manual.md) | 95–96 | `import chainlit, litellm, chromadb` | **ÄNDERN** → FastAPI-Import-Check | Installationsverifikation |
| [`docs/user_manual.md`](docs/user_manual.md) | 184–185 | `uv run chainlit run src/ui/chainlit_app.py` | **ÄNDERN** → `bash scripts/start.sh` | Startanweisung |
| [`docs/user_manual.md`](docs/user_manual.md) | 692–694 | `Access the DMS dashboard via Chainlit` | **ÄNDERN** → FastAPI/Svelte-basierte Anleitung | DMS-Dokumentation |
| [`docs/user_manual.md`](docs/user_manual.md) | 949–951 | `chainlit_app.py # Main Chainlit entry point` | **ÄNDERN** → `debate_engine/main.py` | Projektstruktur |

### ⚪ INFORMATIONAL (Pläne, nur Referenz)

| Datei | Fund | Aktion |
|-------|------|--------|
| [`plans/fastapi-langgraph-sse.md`](plans/fastapi-langgraph-sse.md) | Zeilen 848–852: Dokumentiert Chainlit-Entfernung | Keine Aktion (Plan-Dokument) |
| [`plans/fastapi-ui-rewrite.md`](plans/fastapi-ui-rewrite.md) | Zeilen 336–338, 378–380: Dokumentiert Chainlit-Entfernung | Keine Aktion (Plan-Dokument) |

---

## 2. Abhängigkeiten

### [`pyproject.toml`](pyproject.toml)

| Prüfpunkt | Status | Details |
|-----------|--------|---------|
| `chainlit` in `dependencies` | ✅ **BEREITS ENTFERNT** | Nicht in `[project.dependencies]` |
| `chainlit` in `dev-dependencies` | ✅ **NICHT VORHANDEN** | Nur pytest, ruff, httpx |
| `chainlit` in `[project.optional-dependencies]` | ✅ **NICHT VORHANDEN** | Nur `dms` extra (paddlepaddle, paddleocr) |
| `testpaths` | 🟡 **ENHÄLT ALTEN PFAD** | `["tests", "tests_debate_engine"]` — `tests/` enthält Chainlit-Tests |

### [`frontend/package.json`](frontend/package.json)

| Prüfpunkt | Status |
|-----------|--------|
| Chainlit-Imports | ✅ **KEINE** — reines Svelte/Vite/Playwright-Projekt |

### `.venv/` (installierte Pakete)

| Prüfpunkt | Status | Details |
|-----------|--------|---------|
| `chainlit` installiert? | ⚠️ **JA** | Noch in `.venv/` installiert (wird aber nicht mehr von `pyproject.toml` gemanaged) |

**Empfehlung:** `uv sync` ausführen, um `.venv/` mit aktuellem `pyproject.toml` zu synchronisieren. Chainlit wird dann automatisch entfernt.

---

## 3. Umgebungsvariablen

### [`.env.example`](frontend/.env.example)

| Variable | Wert | Chainlit-spezifisch? |
|----------|------|---------------------|
| `VITE_API_URL` | `http://localhost:8000` | ❌ Nein — Svelte/FastAPI |

### Root `.env.example`

| Prüfpunkt | Status |
|-----------|--------|
| Existiert? | ❌ **NICHT VORHANDEN** |
| Chainlit-Variablen (`CHAINLIT_*`) | ❌ Keine gefunden |

### Docker-Compose

| Prüfpunkt | Status |
|-----------|--------|
| `docker-compose.yml` existiert? | ❌ **NICHT VORHANDEN** |
| Chainlit-Container? | ❌ N/A |

**Ergebnis:** ✅ Keine Chainlit-Umgebungsvariablen gefunden.

---

## 4. Start-Skripte

### [`scripts/start.sh`](scripts/start.sh) 🔴 **KRITISCH**

```bash
# Zeile 23 — STARTET NOCH CHAINLIT!
nohup uv run chainlit run src/ui/chainlit_app.py --port "$PORT" > "$LOG_FILE" 2>&1 &
```

**Aktion:** ÄNDERN zu:
```bash
nohup uv run uvicorn debate_engine.main:app --host 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
```

### [`setup.sh`](setup.sh) 🟡

```bash
# Zeile 15 — Referenziert noch Chainlit
echo "✅ Setup abgeschlossen. Starte mit: uv run chainlit run src/ui/chainlit_app.py --port 7860"
```

**Aktion:** ÄNDERN zu:
```bash
echo "✅ Setup abgeschlossen. Starte mit: bash scripts/start.sh"
```

### [`scripts/manage.sh`](scripts/manage.sh)

| Prüfpunkt | Status |
|-----------|--------|
| Chainlit-Referenzen | ✅ **KEINE** — delegiert an `start.sh`/`stop.sh`/`status.sh` |
| systemd-Referenzen | ✅ **KEINE** — bereits migriert |

### Dockerfile / docker-compose.yml / entrypoint.sh

| Prüfpunkt | Status |
|-----------|--------|
| Existieren? | ❌ **NICHT VORHANDEN** |
| Chainlit-Start? | ❌ N/A |

---

## 5. Datenbank

### [`data/audit.db`](data/audit.db)

| Prüfpunkt | Status | Details |
|-----------|--------|---------|
| Existiert? | ❌ **NICHT VORHANDEN** (oder leer) | `sqlite3 data/audit.db ".tables"` → keine Ausgabe |
| Chainlit-Tabellen (`messages`, `sessions`, `feedback`) | ❌ **NICHT VORHANDEN** | Chainlit nutzt eigene interne DB, nicht `audit.db` |
| Neue Tabellen (`audit_events`) | ✅ Definiert in [`debate_engine/persistence/audit.py`](debate_engine/persistence/audit.py) | Wird bei erstem Start erstellt |

**Ergebnis:** ✅ Keine Chainlit-Datenbank-Reste. Die neue `audit.db` wird vom `debate_engine` bei Bedarf erstellt.

---

## 6. Statische Dateien

| Datei/Verzeichnis | Existiert? | Aktion | Begründung |
|-------------------|-----------|--------|------------|
| [`chainlit.md`](chainlit.md) | ✅ JA (15 Zeilen) | **LÖSCHEN** | Chainlit-Willkommensbildschirm |
| [`.chainlit/config.toml`](.chainlit/config.toml) | ✅ JA (179 Zeilen) | **LÖSCHEN** | Chainlit-Konfiguration |
| [`.chainlit/translations/`](.chainlit/translations/) | ✅ JA (25 Dateien) | **LÖSCHEN** | Chainlit-i18n-Übersetzungen |
| `public/chainlit/` | ❌ NEIN | — | Nicht vorhanden |

---

## 7. Zusammenfassungs-Checkliste

### Dateien zum LÖSCHEN (8 Dateien/Verzeichnisse)

- [ ] `src/ui/chainlit_app.py` (1016 Zeilen)
- [ ] `src/ui/dashboard.py` (49 Zeilen)
- [ ] `src/ui/dms_dashboard.py` (303 Zeilen)
- [ ] `chainlit.md` (15 Zeilen)
- [ ] `.chainlit/` (Verzeichnis: config.toml + 25 Übersetzungen)
- [ ] `tests/test_chainlit_app.py` (~330 Zeilen)
- [ ] `tests/test_debate_engine_rag.py` (~440 Zeilen)
- [ ] `tests/test_dms_integration.py` (~30 Zeilen)

### Dateien zum ÄNDERN (5 Dateien)

- [ ] `scripts/start.sh` — Chainlit-Start → FastAPI/uvicorn-Start
- [ ] `setup.sh` — Chainlit-Referenz → `bash scripts/start.sh`
- [ ] `src/core/logging_config.py` — Chainlit-Logger-Zeile entfernen
- [ ] `README.md` — UI Framework + Projektstruktur aktualisieren
- [ ] `docs/user_manual.md` — Chainlit-Befehle → FastAPI/Svelte-Befehle

### Tests zum AKTUALISIEREN (1 Datei)

- [ ] `tests/test_logging_config.py` — `test_setup_logging_configures_chainlit_level` entfernen

### Optional/Bereinigung

- [ ] `uv sync` ausführen (Chainlit aus `.venv/` entfernen)
- [ ] `pyproject.toml` `testpaths` prüfen (alte `tests/` Pfade mit Chainlit-Tests)

---

## 8. Risiko-Bewertung

| Risiko | Level | Beschreibung |
|--------|-------|--------------|
| `scripts/start.sh` startet Chainlit | 🔴 **HOCH** | Produktionsstart schlägt fehl, wenn Chainlit nicht installiert |
| `setup.sh` verweist auf Chainlit | 🟡 **MITTEL** | Neue Entwickler erhalten falsche Startanweisung |
| Chainlit-Tests in CI | 🟡 **MITTEL** | CI schlägt fehl, wenn Chainlit nicht installiert |
| `.chainlit/` Verzeichnis | 🟢 **NIEDRIG** | Kein Funktionsverlust, nur Ballast |
| README/Docs veraltet | 🟢 **NIEDRIG** | Dokumentation stimmt nicht mit Code überein |

---

## 9. Empfohlene Reihenfolge

1. **Sofort:** `scripts/start.sh` auf uvicorn umstellen (Produktionskritisch)
2. **Sofort:** `setup.sh` aktualisieren
3. **Danach:** Chainlit-UI-Dateien löschen (`src/ui/chainlit_app.py`, `dashboard.py`, `dms_dashboard.py`)
4. **Danach:** Chainlit-Tests löschen
5. **Danach:** `.chainlit/` und `chainlit.md` löschen
6. **Danach:** `src/core/logging_config.py` bereinigen
7. **Zuletzt:** README + Docs aktualisieren
8. **Cleanup:** `uv sync` ausführen
