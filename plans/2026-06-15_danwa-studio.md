# Plan: Danwa-Studio — UI-Separation für Admin/Dev vs. Endbenutzer

**Datum:** 2026-06-15  
**Status:** Entwurf  
**Vorgänger:** `2026-05-28_ui-multi-user.md`  
**Ziel:** Zwei separate Frontend-Repos (danwa + danwa-studio) mit shared Backend.

---

## 1. Ausgangslage

### 1.1 Problem
Die aktuelle UI mischt Endbenutzer-, Admin- und Entwickler-Funktionalität in einer App.
Das führt zu überladener Navigation, unklarer Zielgruppe und steigender Komplexität.

### 1.2 Tech-Stack (unverändert)

| Komponente | Technologie |
|------------|-------------|
| Backend | FastAPI + LangGraph (Python 3.11+) |
| Frontend | Svelte 5 + Vite 5 (JavaScript, kein TypeScript) |
| Styling | Tailwind CSS 3 |
| Workflow-Graph | @xyflow/svelte + elkjs |
| Routing | Hash-Routing (`#/route`) in `App.svelte` |
| i18n | English als SSOT, ~50 UI-Übersetzungen als Module (14 Core-Sprachen deprecated) |
| DB | SQLite (Audit, Auth), ChromaDB (Vektoren) |
| Auth | JWT (python-jose + passlib/bcrypt) |

### 1.3 Bestehende Sidebar-Struktur

```
RUN
  ├── Dashboard
  ├── Projects
  ├── Documents
  ├── Archive

BUILD
  ├── Blueprint Canvas
  ├── Workflow Templates
  ├── Input Composer
  ├── Output Composer

CONFIGURE
  ├── Config (LLM Profiles, Agents, Prompts)
  ├── Roles
  ├── Tone Profiles
  ├── Modules
  ├── Users (admin)

EVOLVE
  ├── Diff View
  ├── Replay View
  ├── Proposals
  ├── Translation Dashboard

ACCOUNT
  ├── My Profile
  ├── My API Keys

ADMINISTRATION (admin)
  ├── Tenant Settings
  ├── Server Health
  ├── System Management
```

---

## 2. Architektur-Entscheidung

### 2.1 Vier separate Repos

| Repo | Inhalt | Deployment |
|------|--------|------------|
| **danwa** | Endbenutzer-Frontend (Svelte 5) | `danwa.example.com` |
| **danwa-studio** | Admin/Dev-Frontend (Svelte 5) | `danwa.example.com/studio` |
| **danwa-core** | FastAPI Backend (aus aktuellem `danwa/backend`) | `danwa.example.com/api` |
| **danwa-modules** | Module (Agent, Prompt, Role, Tone, LLM, i18n, Workflow-Templates) | via danwa-studio verwaltet |

**Naming:**
- `danwa-core` (statt `danwa-backend`): Betont die zentrale Rolle als Shared Backend für beide Frontends
- `danwa-studio`: Klar als Admin/Dev-Tool erkennbar
- `danwa`: bleibt als Endbenutzer-App (später schlank migriert)

**danwa-modules** wird von danwa-studio aus verwaltet:
- Neues Modul erstellen (Manifest + Profile)
- Modul updaten (z.B. i18n-Sprachversion ergänzen)
- Versionierung (SemVer)
- Schema-Erweiterungen ins Repo übernehmen
- Prompts optimieren (Live-Test)
- Module publizieren (Git Commit/Push)

### 2.2 Warum drei Repos statt Monorepo?

| Kriterium | Monorepo | Drei Repos |
|-----------|----------|------------|
| Setup-Komplexität | Einfacher (ein `git clone`) | Mehr Repos, aber klarer getrennt |
| Team-Autonomie | Gemischt | Klare Eigentumsverhältnisse |
| Deploy-Isolation | Schwieriger | Frontends unabhängig deploybar |
| CI/CD | Ein Pipeline | Separate Pipelines pro Repo |
| Code-Sharing | Shared Packages nötig | npm-Pakete oder Git Submodules |

### 2.4 Shared Packages (npm)

```bash
@danwa/api-client     # API-Types + Fetch Wrapper (aus FastAPI OpenAPI Spec generiert)
@danwa/ui-core        # Shared Svelte Components (Button, Card, Modal, Form, etc.)
@danwa/i18n           # i18n Loader (English als SSOT, ~50 Sprachmodule)
```

Diese werden als npm-Pakete publiziert und von beiden Frontend-Repos als Dependencies eingebunden.

**Zu @danwa/ui-core:** Gemeinsame UI-Komponenten (Button, Card, Modal, Form, Input, Select, Badge, Alert, LanguageSwitcher, LoginView, Header, Sidebar, WorkflowGraph, DebateTimeline, ConsensusPanel). Dadurch wird Code-Duplikation zwischen danwa und danwa-studio vermieden. Komponenten werden in einem eigenen npm-Paket versioniert und von beiden Apps importiert.

---

## 2.5 ADR: Entwicklungsumgebung (Development vs. Production)

**Entscheidung:** Für die Entwicklung werden **keine Systemdienste** (nginx, Docker, systemd) benötigt. Die aktuelle Script-basierte Entwicklungsumgebung (`./manage.sh`) bleibt vollständig nutzbar.

**Begründung:**
- Frontend-Dev-Server (Vite) leitet API-Calls via Proxy an Backend weiter
- Kein TLS/SSL nötig (localhost)
- Kein Reverse Proxy nötig (Vite übernimmt das)
- Docker/nginx kommen erst bei Production-Deployment zum Einsatz

**Development-Aufbau (3 parallele Terminals):**

```
Terminal 1:  cd danwa-core && uv run uvicorn backend.main:app --reload --port 8000
Terminal 2:  cd danwa && npm run dev          # Port 5173
Terminal 3:  cd danwa-studio && npm run dev   # Port 5174
```

**manage.sh anpassbar:** Das bestehende `./manage.sh` kann erweitert werden, um auch `danwa-studio` zu starten:
```bash
# Optionale Erweiterung für manage.sh:
./manage.sh start-studio   # Startet danwa-studio auf Port 5174
./manage.sh stop-studio    # Stoppt danwa-studio
```

**Vite Proxy Config** (in beiden Frontend-Repos identisch):
```javascript
// vite.config.js
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/a2a': 'http://localhost:8000',
    '/.well-known': 'http://localhost:8000',
  }
}
```

---

## 2.6 ADR: Unabhängige Entwicklung von danwa-studio und danwa-core

**Entscheidung:** `danwa-studio` und `danwa-core` (Backend) werden **vollständig unabhängig** vom bestehenden `danwa`-Repo entwickelt. Das `danwa`-Repo bleibt **unverändert** funktionsfähig, bis `danwa-studio` und `danwa-core` voll funktionsfähig sind.

**Begründung:**
- Kein Risiko für laufende Entwicklung im `danwa`-Repo
- Keine Zwischenstände mit teilweise migriertem Code
- `danwa-studio` kann sofort mit vollem Funktionsumfang gestartet werden
- Phase 2 ("Danwa-App schlank machen") kommt erst ganz zum Schluss

**Implikationen:**
- `danwa` nutzt **keine** der neuen Shared Packages (hat eigene Copies)
- `danwa-studio` wird **neu gebaut** mit Shared Packages
- `danwa-core` **exportiert** OpenAPI Spec → generiert `@danwa/api-client`
- Shared Packages werden via `file:` Protocol oder `npm link` in Development eingebunden
- Erst **nach Fertigstellung von danwa-studio** (Phase 3 Ende) wird `danwa` auf Shared Packages migriert + geschlankt (Phase 2)

**Sync-Punkt: OpenAPI Spec**
```
danwa-core (Backend)
    │
    ▼ GET /openapi.json
    │
    ▼ Generierung (openapi-typescript / orval)
    │
    ▼ @danwa/api-client (npm Package)
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
danwa (dev)       danwa-studio       danwa (prod, später)
(nutzt noch       (nutzt @danwa/*)    (migriert später)
 eigene Copies)
```

**Shared Packages in Development:**
- `file:` Protocol: `"@danwa/api-client": "file:../packages/api-client"` in package.json
- Alternativ: `npm link` (cd packages/api-client && npm link → cd danwa-studio && npm link @danwa/api-client)
- Später: npm/GitHub Packages Registry (für echte Versionierung)

---

## 3. Aufteilung der Features

### 3.1 danwa (Endbenutzer-App)

| Feature | Route | Beschreibung |
|---------|-------|--------------|
| Dashboard | `#/` | Meine Projekte, aktive Debatten, Schnellstart |
| Projects | `#/projects` | Projektverwaltung (erstellen, wechseln) |
| Documents | `#/documents` | DMS: Dokumente hochladen, durchsuchen |
| Debates | `#/debate/:id` | Debate starten, verfolgen, Ergebnis ansehen |
| Archive | `#/archive` | Vergangene Sessions durchsuchen |
| Reports | `#/reports` | Ergebnisse als PDF/DOCX exportieren |
| Settings | `#/settings` | Basic: Sprache, Projekt-Einstellungen |
| Login | `#/login` | Authentifizierung |

**Sidebar-Struktur (danwa):**

```
START
  ├── Dashboard
  ├── Meine Projekte

ARBEITEN
  ├── Dokumente
  ├── Neue Debate
  ├── Archive

ERGEBNISSE
  ├── Reports
  ├── Export

KONTO
  ├── Mein Profil
  ├── Meine API-Keys
```

**Entfernt (nur in Studio):**
- Blueprint Canvas
- Workflow Templates (nur Ausführung vordefinierter Templates)
- Input/Output Composer
- Config (LLM Profiles, Agents, Prompts)
- Roles, Tone Profiles
- Modules
- Diff View, Replay View
- Proposals
- Translation Dashboard
- Tenant Settings, Server Health, System Management

### 3.2 danwa-studio (Admin/Dev-App)

| Feature | Route | Beschreibung |
|---------|-------|--------------|
| Dashboard | `#/` | System-Übersicht, aktive Workflows, Quick-Actions |
| Modules | `#/modules` | Module-Registry: Manifeste, Versionierung, Publish (aus `danwa-modules`) |
| Blueprints | `#/blueprints` | Blueprint Canvas: Visuelle Workflow-Editor |
| Workflows | `#/workflows` | Workflow Templates: Erstellen, Testen, Deployen |
| Agents | `#/agents` | Agent-Personas: Erstellen, Bearbeiten, Testen |
| Prompts | `#/prompts` | Prompt Templates: Varianten, i18n, Live-Test |
| Roles | `#/roles` | Rollen-Definitionen |
| Tone Profiles | `#/tones` | Tonality-Profile |
| LLM Profiles | `#/llm` | LLM-Konfiguration (Modelle, Kosten, Limits) |
| Input Composer | `#/input-composer` | Input-Plugins konfigurieren |
| Output Composer | `#/output-composer` | Output-Plugins konfigurieren |
| Diff View | `#/diff` | Debate-Vergleich |
| Replay View | `#/replay` | Debate-Replay mit Timeline |
| Proposals | `#/proposals` | HITL: Optimierungsvorschläge |
| Translation | `#/translations` | i18n-Management mit LLM-Übersetzung |
| Tenants | `#/tenants` | Tenant-Verwaltung (nur Admin) |
| Users | `#/users` | Benutzerverwaltung (nur Admin) |
| Server Health | `#/health` | System-Status, Logs, Metriken |
| Modules Management | `#/modules/manage` | Module erstellen, updaten, versionieren (in `danwa-modules` Repo) |
| Workflow Exec | `#/exec` | Workflows ausführen, HITL-interagieren |

**Sidebar-Struktur (studio):**

```
BUILD
  ├── Blueprint Canvas
  ├── Workflow Templates
  ├── Input Composer
  ├── Output Composer

CONFIGURE
  ├── LLM Profiles
  ├── Agent Personas
  ├── Prompts
  ├── Roles
  ├── Tone Profiles
  ├── Modules

EXECUTE
  ├── Workflow Exec
  ├── Diff View
  ├── Replay View
  ├── Proposals

EVOLVE
  ├── Translation Dashboard
  ├── Module Publishing

ADMINISTRATION (admin)
  ├── Tenant Settings
  ├── User Management
  ├── Server Health
  ├── System Management

KONTO
  ├── Mein Profil
  ├── Meine API-Keys
```

---

## 4. Deployment-Architektur

### 4.1 Single Server (empfohlen)

```
┌─────────────────────────────────────────────────────┐
│                  Nginx (Reverse Proxy)                │
│                  danwa.example.com                   │
├─────────────────────────────────────────────────────┤
│  /api/*          → danwa-core:8000                   │
│  /a2a/*          → danwa-core:8000                   │
│  /.well-known/*  → danwa-core:8000                   │
│  /studio/*       → /var/www/danwa-studio/            │
│  /*              → /var/www/danwa/                   │
├─────────────────────────────────────────────────────┤
│  Danwa Core (FastAPI)                                │
│  ├── SQLite (data/audit.db, data/auth.db)           │
│  ├── ChromaDB (data/chromadb/)                       │
│  ├── Modules (data/modules/ oder modules/)          │
│  └── Output (output/)                               │
└─────────────────────────────────────────────────────┘
```

### 4.2 Nginx-Konfiguration

```nginx
server {
    listen 80;
    server_name danwa.example.com;

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /a2a/ {
        proxy_pass http://127.0.0.1:8000;
    }

    location /.well-known/ {
        proxy_pass http://127.0.0.1:8000;
    }

    # Studio (Admin/Dev)
    location /studio/ {
        alias /var/www/danwa-studio/;
        try_files $uri $uri/ /studio/index.html;
    }

    # Endbenutzer-App (Default)
    location / {
        root /var/www/danwa/;
        try_files $uri $uri/ /index.html;
    }
}
```

### 4.3 Docker (optional, für Entwicklung)

```yaml
services:
  backend:
    build: ./danwa-core
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data
      - ./modules:/app/modules:ro

  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./danwa/dist:/var/www/danwa:ro
      - ./danwa-studio/dist:/var/www/danwa-studio:ro
    depends_on: [backend]
```

---

## 5. Authentifizierung & Autorisierung

### 5.1 JWT-Token (unverändert)

```json
{
  "sub": "user-id",
  "email": "user@example.com",
  "role": "admin|editor|viewer",
  "tenant_id": "tenant-id",
  "exp": 1234567890
}
```

**Speicherort:** JWT-Secret wird in `danwa-core` konfiguriert (über `DANWA_JWT_SECRET_KEY` Env-Var). Beide Frontends (danwa + danwa-studio) teilen dasselbe Secret, da sie dasselbe Backend nutzen.

### 5.2 Rollen-Check im Frontend

**danwa (Endbenutzer):**
- `editor` und `viewer` → vollen Zugriff
- `admin` → Redirect auf `/studio` (optional)

**danwa-studio (Admin/Dev):**
- `admin` → alle Features
- `editor` → BUILD, CONFIGURE, EXECUTE (keine ADMINISTRATION)
- `viewer` → nur READ-ONLY

### 5.3 Login-Flow (identisch in beiden Apps)

```
1. User öffnet danwa.example.com oder danwa.example.com/studio
2. Redirect auf #/login (falls nicht authentifiziert)
3. Login-Formular (identisch in beiden Apps)
4. POST /api/v1/auth/login → JWT Token
5. Token wird in localStorage gespeichert
6. Redirect basierend auf Rolle:
   - admin → /studio/#/ (oder /#/ wenn Endbenutzer-App)
   - editor/viewer → /#/ (oder /studio/#/ wenn Zugriff verweigert)
```

**Identischer Login:** Beide Apps nutzen dasselbe Login-Formular (aus `@danwa/ui-core`), dieselbe API (`/api/v1/auth/login`), denselben JWT-Token. Der User kann zwischen beiden Apps wechseln, ohne sich erneut einloggen zu müssen.

---

## 6. Shared Packages

### 6.1 @danwa/api-client

**Zweck:** Typisierte API-Funktionen für beide Frontends.

**Inhalt:**
```javascript
// api-client/src/index.js
export const api = {
  auth: {
    login(email, password) { /* POST /api/v1/auth/login */ },
    me() { /* GET /api/v1/auth/me */ },
    // ...
  },
  debates: {
    list(projectId) { /* GET /api/v1/debates */ },
    get(id) { /* GET /api/v1/debates/:id */ },
    create(data) { /* POST /api/v1/debates */ },
    // ...
  },
  modules: {
    list() { /* GET /api/v1/modules/manifest */ },
    get(type, id) { /* GET /api/v1/modules/:type/:id */ },
    // ...
  },
  // ... alle weiteren Endpoints
};
```

**Generierung:** Aus FastAPI OpenAPI Spec (`/openapi.json`) von `danwa-core` mit `openapi-typescript` oder manuell.

**Sync-Trigger:** Bei jeder Änderung an `danwa-core` API-Routen muss `@danwa/api-client` neu generiert werden (CI-Check).

### 6.2 @danwa/ui-core

**Zweck:** Shared Svelte Components für beide Frontends.

**Kandidaten:**
- Button, Card, Modal, Form, Input, Select, Badge, Alert
- LanguageSwitcher (i18n)
- LoginView (identisches Login-Formular)
- Header (mit User-Menü)
- Sidebar (Navigation)
- WorkflowGraph (@xyflow/svelte Wrapper)
- DebateTimeline
- ConsensusPanel

**Entwicklung:** Komponenten werden in `packages/ui-core/` entwickelt und über `file:` Protocol oder `npm link` in beide Frontend-Repos eingebunden.

### 6.3 @danwa/i18n

**Zweck:** i18n-Loader + Sprachmodule.

**Architektur:**
- **English** ist die einzige SSOT (Single Source of Truth) im Code
- **~50 UI-Übersetzungen** sind Module in `danwa-modules` (nicht im Core)
- 14 Core-Sprachen (de, fr, es, it, pt, ru, zh, ja, ko, sv, el, ar, he) sind **deprecated**

**Inhalt:**
- `loader.js` — Lädt Sprachmodule dynamisch
- `locales/en.js` — English als Fallback/SSOT
- Sprachmodule werden aus `danwa-modules/i18n-*` geladen

**Lade-Reihenfolge:**
1. `en.js` (immer geladen, SSOT)
2. Falls User-Sprache ≠ en: Sprachmodul aus `danwa-modules/i18n-{lang}` laden
3. Fallback auf en.js für fehlende Keys

**Entwicklung:** Loader wird in `packages/i18n/` entwickelt. Sprachmodule bleiben in `danwa-modules` und werden zur Laufzeit geladen.

---

## 7. Implementierungs-Phasen

### Phase 0: Vorbereitung (1–2 Tage)

| Aufgabe | Beschreibung |
|---------|--------------|
| `danwa-core` Repo anlegen | `danwa/backend` → `danwa-core` extrahieren (eigenständiges Repo) |
| `danwa-studio` Repo anlegen | Svelte 5 + Vite Setup, `@danwa/*` Packages einbinden |
| API-Client generieren | OpenAPI Spec aus `danwa-core` → `@danwa/api-client` Package |
| i18n-Loader extrahieren | `danwa/frontend/src/lib/i18n/loader.js` → `@danwa/i18n` Package (nur Loader + en.js SSOT) |
| UI-Core Components auswählen | Shared Components identifizieren → `@danwa/ui-core` Package |
| npm-Publish-Setup | Packages als `@danwa/*` auf npm oder GitHub Packages publizieren |

### Phase 1: danwa-studio Scaffold (2–3 Tage)

| Aufgabe | Beschreibung |
|---------|--------------|
| Svelte 5 + Vite Projekt erstellen | `npm create vite@latest danwa-studio -- --template svelte` |
| @danwa/* Packages einbinden | `npm install @danwa/api-client @danwa/ui-core @danwa/i18n` |
| Hash-Routing einrichten | Identisch zu danwa App (`App.svelte` mit `$route` Store) |
| Auth-Guard implementieren | Login-Check + Rollen-Prüfung |
| Sidebar-Struktur (BUILD, CONFIGURE, EXECUTE, EVOLVE, ADMIN) | Wie in Abschnitt 3.2 definiert |
| Grundlegende Views scaffold | Alle Routes mit Stub-Komponenten |

### Phase 2: Danwa-App schlank machen (ERST NACH Phase 3)

**Wichtig:** Diese Phase beginnt **erst nach Fertigstellung von Phase 3** (danwa-studio voll funktionsfähig). Das `danwa`-Repo bleibt während der gesamten Entwicklung unverändert funktionsfähig.

| Aufgabe | Beschreibung |
|---------|--------------|
| Blueprint Canvas entfernen | Route `#/blueprints` + Component löschen |
| Workflow Templates entfernen | Route `#/workflow-templates` + Component löschen |
| Input/Output Composer entfernen | Routes + Components löschen |
| Config-View reduzieren | Nur Basic Settings (Sprache, Projekt) |
| Modules-View entfernen | Route `#/modules` + Component löschen |
| Diff/Replay/Proposals entfernen | Routes + Components löschen |
| Translation Dashboard entfernen | Route `#/translations` + Component löschen |
| Tenant/User/Admin Views entfernen | Routes + Components löschen |
| Sidebar reduzieren | Nur START, ARBEITEN, ERGEBNISSE, KONTO |
| "In Studio öffnen" Links ergänzen | Deep Links zu danwa-studio (optional) |
| Shared Packages migrieren | `@danwa/api-client`, `@danwa/ui-core`, `@danwa/i18n` einbinden |

### Phase 3: Danwa-Studio Features (1–2 Wochen)

| Sprint | Scope |
|--------|-------|
| 1 | Blueprint Canvas (aus danwa kopieren), Workflow Templates, Config Views |
| 2 | Module Manager: Manifest-Viewer, Versionierung, Schema-Editor |
| 3 | Prompt Editor mit Live-Test-Run, i18n Sync Tool |
| 4 | Workflow Exec + HITL Panel, Diff View, Replay View |
| 5 | Tenant/Admin Views, Server Health, System Management |
| 6 | Module Publishing (Git Commit/Push in `danwa-modules`), Translation Dashboard |

### Phase 4: Deployment (1 Tag)

| Aufgabe | Beschreibung |
|---------|--------------|
| Nginx-Config erstellen | Wie in Abschnitt 4.2 definiert |
| Frontends bauen | `cd danwa && npm run build` + `cd danwa-studio && npm run build` |
| Backend deployen | Docker Compose oder direkter Start |
| SSL/HTTPS konfigurieren | Let's Encrypt oder manuelles Zertifikat |

---

## 8. Offene Fragen (finalisiert)

| Frage | Entscheidung |
|-------|--------------|
| **Module-Repo:** Separates Repo oder Submodule? | `danwa-modules` als eigenständiges Repo, verwaltet via danwa-studio |
| **API-Client:** Manuell oder generiert? | Aus FastAPI OpenAPI Spec generiert (`@danwa/api-client`) |
| **UI-Core:** Wie teilen? | npm-Package (`@danwa/ui-core`) — gemeinsame Komponenten, versioniert |
| **Login:** Identisch oder separat? | Identisch in beiden Apps (shared Login-Formular aus `@danwa/ui-core`) |
| **i18n:** Core oder Module? | English als SSOT im Core, ~50 Sprachen als Module in `danwa-modules` |
| **Dev-Environment:** Docker/nginx nötig? | Nein — 3 Terminals + Vite Proxy reichen |
| **Unabhängige Entwicklung?** | Ja — danwa-core + danwa-studio vollständig unabhängig, danwa bleibt unverändert |
| **Reihenfolge:** Phase 2 wann? | Erst nach Phase 3 (danwa-studio fertig) |

**Noch offen:**
| Frage | Optionen | Empfehlung |
|-------|----------|------------|
| **Deep Links:** Studio → Danwa? | a) "In Studio öffnen" in danwa<br>b) Keine Deep Links (User manuell wechseln) | (a) für bessere UX |
| **Danwa-App:** Admin-Features completely entfernen? | a) Admin-User wird auf `/studio` redirectet<br>b) Admin sieht alle Features in beiden Apps | (a) für klare Trennung |

---

## 9. Risiken & Migration

| Risiko | Impact | Gegenmaßnahme |
|--------|--------|---------------|
| **Type Drift** (API ↔ Frontends) | Features funktionieren nicht | CI-Check: API-Client aus OpenAPI Spec generieren, Lint-Check ob aktuell |
| **Code-Duplikation** (z.B. Login-Formular) | Wartungsaufwand | Shared Packages (`@danwa/ui-core`) nutzen |
| **Build-Complexität** | Längere CI-Zeiten | Separate Pipelines pro Repo, nur bei Änderung in `@danwa/*` rebuild |
| **Nginx-Fehler** | Frontend nicht erreichbar | Test-Deployment mit Docker Compose vor Produktions-Deploy |
| **Auth-Token-Kompatibilität** | Login funktioniert nicht in Studio | JWT-Secret muss identisch sein (shared Backend) |
| **Module-Repo-Konflikte** | Git-Merges nötig | Studio nutzt Feature Branches + PR Flow (GitHub/Gitea API) |
| **i18n-Modul-Laden** | Sprachen geladen werden | Loader muss Fallback auf en.js haben, wenn Modul fehlt |
| **Danwa-Backend-Extraktion** | Backend-Änderungen während Migration | CI-Check: `danwa-core` muss API-Kompatibilität zu `danwa` halten |

---

## 10. Zeitplan

```
Phase 0:  2026-06-16 bis 2026-06-17  Vorbereitung (Shared Packages)
Phase 1:  2026-06-18 bis 2026-06-20  danwa-studio Scaffold + Auth
Phase 3:  2026-06-21 bis 2026-07-05  danwa-studio Features (6 Sprints)
Phase 2:  2026-07-06 bis 2026-07-11  Danwa-App schlank machen (ERST NACH Phase 3)
Phase 4:  2026-07-12 bis 2026-07-13  Deployment + Test
```

**Gesamt:** ~4 Wochen (inkl. Testing)

**Reihenfolge:**
1. Phase 0: Shared Packages (`@danwa/api-client`, `@danwa/ui-core`, `@danwa/i18n`)
2. Phase 1: danwa-studio Scaffold + Auth (unabhängig von danwa)
3. Phase 3: danwa-studio Features (6 Sprints, unabhängig von danwa)
4. Phase 2: Danwa-App schlank migrieren (erst wenn danwa-studio fertig ist)
5. Phase 4: Deployment + Test (Production)

---

## 11. Erfolgskriterien

| Kriterium | Zielwert |
|-----------|----------|
| Danwa-App Bundle-Size | < 200 KB (gzipped) |
| Danwa-Studio Bundle-Size | < 500 KB (gzipped) |
| Login-Flow (beide Apps) | < 2s |
| Module-Listing (Studio) | < 1s |
| Blueprint Canvas (Studio) | < 3s First Paint |
| Kein Code-Duplikat > 50 Zeilen | Shared Packages nutzen |
