# Sprint 4 — API, Frontend & Modul-Registry

> **Branch:** `feature/module-architecture`  
> **Dauer:** 1 Woche  
> **Liefergegenstand:** REST-API, Frontend-Module-Manager, Remote-Discovery

---

## Kontext

Sprint 1–3 haben die Backend-Grundlagen geschaffen. Jetzt wird die API vervollständigt, das Frontend eingebaut und die Remote-Discovery vorbereitet.

---

## Todo-Liste

### 4.1 — REST-API: Module-Endpunkte

- [ ] Neuer Router `backend/api/routers/modules.py`
  - [ ] `GET /api/v1/modules/` — Liste installierter Module mit Metadaten
    - [ ] Filter: `?category=`, `?type=`, `?enabled=`
    - [ ] Sortierung: `?sort=name|installed_at|version`
    - [ ] Paginierung: `?limit=&offset=`
  - [ ] `GET /api/v1/modules/{module_id}` — Detailansicht
    - [ ] Manifest-Inhalt
    - [ ] Installationsdatum, Version
    - [ ] Abhängigkeiten (installiert/nicht installiert)
    - [ ] Übersetzungsstatus pro Sprache
  - [ ] `GET /api/v1/modules/available` — Verfügbare Remote-Module
    - [ ] Liest `registry.json` von Remote-URL
    - [ ] Vergleicht mit installierten → zeigt Updates an
    - [ ] Filter: `?category=`
  - [ ] `POST /api/v1/modules/install` — Modul installieren
    - [ ] Body: `{module_id, source: "local" | "remote", url?}`
    - [ ] Validierung → Installation → DB-Eintrag
    - [ ] Antwort: `InstallationReport`
  - [ ] `POST /api/v1/modules/{module_id}/uninstall` — Deinstallieren
    - [ ] Body: `{purge_data: boolean}`
    - [ ] Abhängigkeitsprüfung
  - [ ] `PUT /api/v1/modules/{module_id}/update` — Aktualisieren
    - [ ] Prüft Remote auf neue Version
    - [ ] Download + Validierung + Update
  - [ ] `POST /api/v1/modules/{module_id}/translate` — Übersetzung auslösen
  - [ ] `GET /api/v1/modules/categories` — Verfügbare Kategorien

### 4.2 — Prompts-API erweitern

- [ ] Neuer Endpunkt `GET /api/v1/prompts/{role_type_id}/languages`
  - [ ] Zeigt verfügbare Sprachen (EN immer vorhanden, DE aus Cache, weitere)
- [ ] `GET /api/v1/prompts/{role_type_id}?language=de`
  - [ ] Liest aus Übersetzungscache oder EN-Fallback
- [ ] `POST /api/v1/prompts/{role_type_id}/translate`
  - [ ] Trigger für neue Übersetzung

### 4.3 — Frontend: Modul-Manager-Komponente

- [ ] Neue Komponente `ModuleManager.svelte`
  - [ ] Tab-basierte Navigation:
    - [ ] **Installiert** — Übersicht aller installierten Module
    - [ ] **Verfügbar** — Remote-Module zum Installieren
    - [ ] **Updates** — Module mit neuer Version
    - [ ] **Übersetzungen** — Übersetzungsstatus
  - [ ] Jede Karte zeigt:
    - [ ] Name, Version, Kategorie, Autor
    - [ ] Status: Aktiviert/Deaktiviert
    - [ ] Sprachen: EN ✅ | DE ✅/⚠️/❌
    - [ ] Buttons: Aktivieren/Deaktivieren, Aktualisieren, Deinstallieren, Übersetzen
  - [ ] Modul-Detailansicht (Modal oder Seite):
    - [ ] Manifest-Informationen
    - [ ] Dateien-Liste
    - [ ] Abhängigkeiten
    - [ ] Changelog

### 4.4 — Frontend: Modul-Marktplatz

- [ ] Komponente `ModuleMarketplace.svelte`
  - [ ] Zeigt verfügbare Remote-Module
  - [ ] Suchfunktion und Filterung nach Kategorie
  - [ ] Installieren-Button öffnet Bestätigungsdialog
  - [ ] Fortschrittsanzeige bei Installation

### 4.5 — Frontend: Übersetzungs-Dashboard

- [ ] Seite **Konfiguration → Übersetzungen**
  - [ ] Modul-Baum nach Kategorien (wie in Sprint-Plan beschrieben)
  - [ ] Pro Modul:
    - [ ] Sprachen mit Status (Original ✅ | Übersetzt ✅/⚠️/❌)
    - [ ] Qualitätsscore
    - [ ] Button "Übersetzen" / "Erneut übersetzen"
    - [ ] Button "Manuell bearbeiten"
  - [ ] Vergleichsansicht: EN-Original vs. DE-Übersetzung
  - [ ] Massenaktionen: "Alle fehlenden übersetzen"

### 4.6 — Frontend: Prompt-Editor mit Übersetzungsbutton

- [ ] Im bestehenden Prompt-Editor
  - [ ] Button "🌐 Übersetzen" neben Sprach-Auswahl
  - [ ] Modal mit:
    - [ ] Zielsprache (aktuell: DE)
    - [ ] Vorschau der Übersetzung
    - [ ] "Speichern" und "Manuell bearbeiten"-Option
  - [ ] Gespeichert wird nur in DB (Übersetzungscache), nicht als Datei

### 4.7 — Backend: Module in bestehende Konfigurationsseiten einbinden

- [ ] Integration in `SettingsView.svelte` (oder neue Seite)
- [ ] Service-Worker/Hintergrund-Jobs für automatische Übersetzung
- [ ] Event-System: `module_installed`, `module_updated`, `module_uninstalled`

### 4.8 — Tests

- [ ] `tests/backend/test_module_api.py`
  - [ ] GET-Endpoints: Listen, Details, Kategorien
  - [ ] POST-Endpoints: Install, Uninstall, Update
  - [ ] Fehlerfälle: Ungültiges Manifest, doppelt installieren, Abhängigkeitsfehler
- [ ] `tests/backend/test_module_permissions.py`
  - [ ] Nur Admin kann Module installieren/deinstallieren
  - [ ] Rollenbasierter Zugriffsschutz
- [ ] E2E-Tests:
  - [ ] Modul installieren/deinstallieren über UI
  - [ ] Übersetzungs-Workflow im Frontend
  - [ ] Prompt-Editor Übersetzungsbutton

---

## Abhängigkeiten
- Benötigt Sprint 1 (DB) und Sprint 2 (Import-Engine)
- Übersetzungsteile benötigen Sprint 3

## Akzeptanzkriterien
- [ ] AC-4.1: Alle API-Endpoints erreichbar und dokumentiert
- [ ] AC-4.2: Modul-Manager zeigt installierte Module korrekt an
- [ ] AC-4.3: Modul installieren/aktualisieren/deinstallieren über UI
- [ ] AC-4.4: Übersetzungs-Dashboard funktioniert
- [ ] AC-4.5: 30+ neue API- und E2E-Tests
