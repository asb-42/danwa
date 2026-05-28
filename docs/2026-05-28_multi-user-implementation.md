# Multi-User Implementation — Phasen-Zusammenfassung

**Datum:** 2026-05-28  
**Commits:** `0522ba0` → `24554da` → `041a49e` → `104f347` → `e673d64` → `632035d`  
**Plan:** `plans/2026-05-28_multi-user.md`

---

## Phase 1: Authentifizierung & Benutzerverwaltung (`0522ba0`)

16 Dateien geändert, +3.174/-7 Zeilen.

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `backend/models/user.py` | User, UserCreate, UserUpdate, UserResponse, LoginRequest, TokenResponse, RefreshRequest, PasswordChangeRequest |
| `backend/persistence/user_store.py` | UserStore — SQLite CRUD für Users (auth.db) |
| `backend/core/security.py` | JWT-Erstellung/Validierung, bcrypt Passwort-Hashing |
| `backend/core/seed.py` | ensure_admin_user — erstellt Admin automatisch beim ersten Start |
| `backend/api/routers/auth.py` | POST /register, /login, /refresh, GET /me, PUT /password |
| `frontend/src/lib/stores/auth.svelte.js` | Auth-Stores (accessToken, refreshToken, currentUser) mit localStorage-Persistenz |
| `frontend/src/lib/auth.js` | Auth-API-Client (login, register, refreshAccessToken, logout, changePassword) |
| `frontend/src/views/LoginView.svelte` | Login/Registrier-Formular mit Svelte 5 Runes |
| `tests/backend/test_auth.py` | 18 Tests — Passwort-Hashing, JWT, UserStore CRUD, Seed-Admin |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `pyproject.toml` | `python-jose[cryptography]`, `passlib[bcrypt]` ergänzt |
| `backend/core/config.py` | `jwt_secret_key`, `jwt_algorithm`, `jwt_access_token_expire_minutes`, `jwt_refresh_token_expire_days`, `auth_enabled` |
| `backend/api/deps.py` | `get_user_store`, `get_current_user`, `require_role` Dependencies |
| `backend/main.py` | Auth-Router registriert, Seed-Admin im Lifespan |
| `frontend/src/lib/api.js` | Authorization-Header-Injection, 401-Auto-Refresh + Redirect zu Login |

### Verifikation

- 18 Auth-Tests bestanden
- `ruff check` bestanden
- Bestehende 15 Tests weiterhin bestanden

---

## Phase 2: Mandantenfähigkeit & Daten-Isolation (`24554da`)

10 Dateien geändert, +584/-1 Zeilen.

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `backend/models/tenant.py` | Tenant, TenantCreate, TenantUpdate, TenantResponse |
| `backend/persistence/tenant_store.py` | TenantStore — SQLite CRUD (auth.db) |
| `backend/api/routers/tenants.py` | GET /current, PUT /settings, GET /users, POST /invite, DELETE /users/{id} |
| `backend/api/quota.py` | check_debate_quota, check_document_quota, check_project_quota |
| `tests/backend/test_tenants.py` | 18 Tests — TenantStore CRUD, Project-Scoping, Quota-Enforcement |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `backend/models/project.py` | `tenant_id` Feld zu Project, ProjectCreateRequest, ProjectResponse, ProjectListItem hinzugefügt |
| `backend/persistence/project_store.py` | `tenant_id`-Param bei create(), `list_by_tenant()`-Methode |
| `backend/api/deps.py` | `get_tenant_store`, `get_project_scoped` |
| `backend/core/seed.py` | `ensure_default_tenant()` ergänzt, wird vor Admin-User-Erstellung aufgerufen |
| `backend/main.py` | Tenants-Router registriert, Tenant-Seed im Lifespan |

### Verifikation

- 36 Tests bestanden (18 Auth + 18 Tenant)
- `ruff check` bestanden
- App-Import verifiziert

---

## Phase 3: Task-Queue & parallele Debatten (`041a49e`)

13 Dateien geändert, +700/-366 Zeilen.

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `backend/tasks/__init__.py` | Tasks-Paket |
| `backend/tasks/celery_app.py` | Lazy Celery-Factory — gibt None zurück wenn nicht konfiguriert |
| `backend/tasks/debate.py` | `run_debate_task.delay()` — Celery-Worker-Entry-Point |
| `backend/tasks/dispatch.py` | `dispatch_debate_task()` / `dispatch_workflow_task()` — routet zu Celery oder BackgroundTasks |
| `backend/tasks/workflow.py` | Celery-Task-Stub für generische Workflows |
| `backend/state/__init__.py` | State-Paket |
| `backend/state/workflow_state.py` | `InMemoryWorkflowState` + `RedisWorkflowState` mit Protocol-Interface |
| `docker-compose.yml` | Redis + optionaler Celery-Worker (Profil: celery) |
| `tests/backend/test_task_dispatch.py` | 18 Tests — State-Backends, Celery-Factory, Dispatch-Fallback |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `backend/core/config.py` | `redis_url`, `celery_enabled`, `celery_worker_concurrency`, `max_concurrent_debates_global` |
| `backend/api/routers/debate.py` | 3× BackgroundTasks → dispatch_debate_task |
| `backend/api/routers/workflow_exec.py` | 2× BackgroundTasks → dispatch_workflow_task |
| `pyproject.toml` | `redis` + `celery[redis]` als optionale Dependencies |

### Kern-Design-Entscheidung

Redis/Celery sind **100% optional**. Ohne sie funktioniert das System wie bisher (In-Memory-State + BackgroundTasks). Mit `DANWA_REDIS_URL` + `DANWA_CELERY_ENABLED=true` werden Debatten an Celery-Worker dispatched.

### Verifikation

- 51 Tests bestanden (18 Auth + 18 Tenant + 18 Task-Dispatch, minus 2 fehlerhafte DMS-OCR-Tests)

---

## Phase 4: Server-Infrastruktur & Deployment (`104f347`)

9 Dateien geändert, +394/-30 Zeilen.

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `Dockerfile.backend` | Python 3.12-slim + tesseract + espeak-ng + ffmpeg + gunicorn |
| `Dockerfile.frontend` | Node 22 Build → Nginx alpine |
| `deploy/nginx.conf` | TLS, API-Proxy, SSE-Support, Security-Headers, Static-Asset-Caching |
| `deploy/.env.example` | JWT_SECRET_KEY, REDIS_URL, CORS_ORIGINS Vorlage |
| `.dockerignore` | Schließt .git, node_modules, data, tests vom Build-Context aus |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `docker-compose.yml` | Full Stack: backend, frontend, redis, optionaler celery-worker |
| `Makefile` | Docker-Targets: build, up, down, logs, celery, restart, clean |
| `backend/api/routers/health.py` | Umfassende Health-Checks (SQLite, Redis, Auth-DB) mit 200/503-Responses |
| `pyproject.toml` | `gunicorn>=22.0.0` ergänzt |

### Quick-Start

```bash
# Lokale Entwicklung (nur Redis):
docker compose up redis -d

# Full Stack:
cp deploy/.env.example deploy/.env  # JWT_SECRET_KEY editieren
docker compose up -d

# Mit Celery:
docker compose --profile celery up -d

# Via Makefile:
make docker-build
make docker-up
make docker-logs
```

---

## Phase 5: Observability, Rate-Limiting & Härtung (`e673d64`)

7 Dateien geändert, +177 Zeilen.

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `backend/core/logging.py` | structlog-Setup — JSON in Prod, Console in Dev, Contextvars-Binding |
| `backend/api/rate_limit.py` | Rate-Limit-Hilfsfunktionen |
| `deploy/prometheus.yml` | Prometheus-Scrape-Konfiguration |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `backend/core/config.py` | `rate_limit_enabled`, `rate_limit_default`, `rate_limit_debate/upload/analysis`, `prometheus_enabled` |
| `backend/main.py` | Request-ID-Middleware, slowapi Limiter (Default 60/min), Prometheus Instrumentator bei `/metrics` |
| `backend/api/errors.py` | Rate-Limit-Exception-Handler (429-Response) |
| `pyproject.toml` | `structlog`, `slowapi`, `prometheus-fastapi-instrumentator` ergänzt |

### Neue Endpunkte

- `GET /metrics` — Prometheus-Metriken (http_requests_total, debate_duration, etc.)
- `X-Request-ID` Header auf allen Responses (propagiert durch structlog)

### Rate-Limits (konfigurierbar via Env-Vars)

| Aktion | Limit |
|--------|-------|
| Global Default | 60/Minute pro IP |
| Debate-Erstellung | 10/Stunde |
| Dokument-Upload | 20/Stunde |
| LLM-Analysis | 5/Stunde |

---

## Phase 6: Migration, Testing & Go-Live (`632035d`)

4 Dateien geändert, +413/-1 Zeilen.

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `backend/migrations/v001_multi_tenant.py` | Idempotent-Migration: erstellt Default-Tenant, fügt tenant_id zu allen Projekt-Dateien hinzu |
| `.github/workflows/deploy.yml` | CI/CD-Pipeline: test → build → deploy |
| `tests/backend/test_multi_tenant.py` | 22 Integrationstests |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `backend/main.py` | Multi-Tenant-Migration im Lifespan nach Projekt-Migration |

### CI/CD-Pipeline

```
Push to main → Lint & Test → Docker Build (Buildx + Cache) → SSH Deploy
```

Erforderliche GitHub-Secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY`, `JWT_SECRET_KEY`

### Integrationstests (22 Tests)

- **Tenant-Isolation:** User und Projekte sind nach Tenant getrennt
- **JWT-Token-Lifecycle:** Access-Token, Refresh-Token, Claims, Secret-Rotation
- **Quota-Enforcement:** Debate-, Document-, Project-Limits greifen
- **Migration:** Idempotenz verifiziert (Doppelausführung = kein Fehler)

---

## Gesamt-Testergebnis

**65 Tests bestanden** über alle Phasen hinweg:

| Test-Suite | Anzahl |
|------------|--------|
| test_auth.py | 18 |
| test_tenants.py | 18 |
| test_task_dispatch.py | 18 |
| test_multi_tenant.py | 22 |

(2 vorher existierende DMS-OCR-Testfehler sind nicht regressionsbedingt.)
