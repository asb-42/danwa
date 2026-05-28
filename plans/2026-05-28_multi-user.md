# Produktivbetrieb: Mandantenfähigkeit, Benutzerverwaltung, parallele Debatten & Server-Infrastruktur

**Datum:** 2026-05-28  
**Status:** Entwurf  
**Ziel:** Danwa als Multi-User-System produktiv nutzbar machen — mit Mandantenfähigkeit (Tenants), Authentifizierung, Autorisierung, parallelen Debatten und einer containerisierten Deployment-Infrastruktur.

---

## Ausgangslage (Ist-Zustand)

| Bereich | Status |
|---------|--------|
| Authentifizierung | **Keine** — keine User, keine Tokens, keine Sessions |
| Autorisierung | **Keine** — jeder HTTP-Client kann jeden Endpoint aufrufen |
| Mandantenfähigkeit | **Teilweise** — "Projects" als logische Gruppierung, aber ohne User-Zuordnung |
| Parallele Debatten | **Eingeschränkt** — In-Memory-State, `BackgroundTasks` im selben Prozess |
| Deployment | `manage.sh` mit `nohup` — kein Docker, kein Reverse-Proxy, kein TLS |
| Datenbank | Rohe `sqlite3`-Verbindungen, JSON-Dateien für Projekte/Debatten |
| State-Persistenz | Workflow-Pause/Resume/Cancel-State geht bei Neustart verloren |

---

## Phasen-Übersicht

```
Phase 1: Authentifizierung & Benutzerverwaltung          (Woche 1–3)
Phase 2: Mandantenfähigkeit & Daten-Isolation             (Woche 3–5)
Phase 3: Task-Queue & parallele Debatten                  (Woche 5–7)
Phase 4: Server-Infrastruktur & Deployment                (Woche 7–9)
Phase 5: Observability, Rate-Limiting & Härtung           (Woche 9–10)
Phase 6: Migration, Testing & Go-Live                     (Woche 10–12)
```

---

## Phase 1: Authentifizierung & Benutzerverwaltung (Woche 1–3)

### 1.1 User-Modell & Datenbank

**Ziel:** Persistente Benutzer mit Rollen und bcrypt-gehashten Passwörtern.

```python
# backend/models/user.py
class User(BaseModel):
    id: str                          # UUID
    email: str                       # Unique, Login-Identifier
    display_name: str
    password_hash: str               # bcrypt
    role: Literal["admin", "editor", "viewer"]
    tenant_id: str                   # FK → Tenant
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
```

**Datenbank-Migration:**
- Neue Tabelle `users` in einer dedizierten Auth-DB (`data/auth.db`) — nicht in den bestehenden SQLite-DBs mischen.
- Indizes auf `email` (unique) und `tenant_id`.

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    tenant_id TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant ON users(tenant_id);
```

### 1.2 JWT-Authentifizierung

**Ziel:** Stateless Token-basierte Authentifizierung.

**Bibliothek:** `python-jose[cryptography]` (JWT) + `passlib[bcrypt]` (Passwort-Hashing)

**Dependencies hinzufügen:**
```toml
# pyproject.toml
"python-jose[cryptography]>=3.3.0",
"passlib[bcrypt]>=1.7.4",
```

**Token-Struktur:**
```python
# backend/core/security.py
class TokenPayload(BaseModel):
    sub: str          # user_id
    email: str
    role: str
    tenant_id: str
    exp: datetime
    iat: datetime

def create_access_token(user: User, expires_delta: timedelta = timedelta(hours=8)) -> str: ...
def create_refresh_token(user: User, expires_delta: timedelta = timedelta(days=30)) -> str: ...
def decode_token(token: str) -> TokenPayload: ...
```

**Settings-Erweiterung:**
```python
# backend/core/config.py — neue Felder
jwt_secret_key: str = ""            # MUSS gesetzt sein in Produktion
jwt_algorithm: str = "HS256"
jwt_access_token_expire_minutes: int = 480    # 8 Stunden
jwt_refresh_token_expire_days: int = 30
```

### 1.3 Auth-Router & Login-Flow

```
POST /api/v1/auth/register     → User erstellen (nur Admin)
POST /api/v1/auth/login        → Email + Password → Access-Token + Refresh-Token
POST /api/v1/auth/refresh      → Refresh-Token → neues Access-Token
POST /api/v1/auth/logout       → Token blacklisten (optional)
GET  /api/v1/auth/me           → Aktueller User
PUT  /api/v1/auth/password     → Passwort ändern
```

### 1.4 Auth-Dependency & Middleware

```python
# backend/api/deps.py — neue Dependencies
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Validiert JWT und gibt User zurück."""
    ...

def require_role(*roles: str):
    """Decorator-Factory für Rollen-basierten Zugriff."""
    def dependency(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return Depends(dependency)

# Verwendung in Routern:
@router.post("/documents")
async def upload_document(
    user: User = Depends(require_role("admin", "editor")),
    ...
):
```

### 1.5 Frontend: Login & Auth-Guards

**Neue Komponenten:**
- `frontend/src/views/LoginView.svelte` — Login-Formular
- `frontend/src/lib/auth.js` — Token-Management (localStorage)
- `frontend/src/lib/stores/auth.svelte.js` — `user`, `isAuthenticated`, `accessToken`

**Änderungen in `api.js`:**
```javascript
// frontend/src/lib/api.js
export async function request(endpoint, options = {}) {
  const token = get(accessToken);  // Aus Auth-Store
  const headers = {
    ...DEFAULT_HEADERS,
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(projectId ? { 'X-Project-Id': projectId } : {}),
    ...options.headers,
  };
  // ...
  if (response.status === 401) {
    // Automatischer Refresh-Versuch, dann Redirect zu Login
  }
}
```

**Router-Guards:**
```javascript
// frontend/src/App.svelte oder Router
$effect(() => {
  if (!$isAuthenticated && currentRoute !== '/login') {
    navigate('/login');
  }
});
```

### 1.6 Seed-Admin bei Erstinstallation

```python
# backend/core/seed.py
def ensure_admin_user():
    """Erstellt einen Admin-User falls keine User existieren."""
    if user_store.count() == 0:
        user_store.create(
            email="admin@danwa.local",
            display_name="Admin",
            password_hash=hash_password("changeme"),  # MUSS beim ersten Login geändert werden
            role="admin",
            tenant_id="_default",
        )
```

### ✅ Phase 1 — Todo-Liste

```
[ ] 1.1  pyproject.toml: python-jose[cryptography] + passlib[bcrypt] ergänzen
[ ] 1.2  backend/models/user.py: User-Pydantic-Modell erstellen
[ ] 1.3  backend/persistence/user_store.py: UserStore (CRUD gegen auth.db) implementieren
[ ] 1.4  backend/core/security.py: JWT-Erstellung, Validierung, Passwort-Hashing
[ ] 1.5  backend/core/config.py: jwt_secret_key, jwt_algorithm, Expire-Settings ergänzen
[ ] 1.6  backend/api/routers/auth.py: Login/Register/Refresh/Me/Password-Endpunkte
[ ] 1.7  backend/api/deps.py: get_current_user, require_role Dependencies
[ ] 1.8  backend/core/seed.py: ensure_admin_user beim App-Start
[ ] 1.9  frontend/src/lib/stores/auth.svelte.js: Auth-Stores (user, token, isAuthenticated)
[ ] 1.10 frontend/src/lib/auth.js: Token-Management (login, logout, refresh, localStorage)
[ ] 1.11 frontend/src/views/LoginView.svelte: Login-Formular mit Validierung
[ ] 1.12 frontend/src/lib/api.js: Authorization-Header injizieren, 401-Redirect
[ ] 1.13 frontend/src/App.svelte: Auth-Guard (Redirect zu /login wenn nicht eingeloggt)
[ ] 1.14 Tests: test_auth.py (Login, Token-Refresh, Rollen-Check, Passwort-Änderung)
[ ] 1.15 Tests: test_auth_frontend.js (Login-Flow, Token-Persistenz, Logout)
[ ] 1.16 Manueller Test: Login → Dashboard → Logout → Redirect funktioniert
```

---

## Phase 2: Mandantenfähigkeit & Daten-Isolation (Woche 3–5)

### 2.1 Tenant-Modell

```python
# backend/models/tenant.py
class Tenant(BaseModel):
    id: str                          # UUID oder Slug
    name: str
    plan: Literal["free", "pro", "enterprise"] = "free"
    max_projects: int = 5
    max_concurrent_debates: int = 2
    max_documents: int = 50
    max_storage_mb: int = 500
    settings: dict = {}              # Tenant-spezifische Defaults
    created_at: datetime
    is_active: bool = True
```

```sql
CREATE TABLE tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    max_projects INTEGER DEFAULT 5,
    max_concurrent_debates INTEGER DEFAULT 2,
    max_documents INTEGER DEFAULT 50,
    max_storage_mb INTEGER DEFAULT 500,
    settings_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
```

### 2.2 Tenant-Scoping für alle Ressourcen

**Bestehendes `X-Project-Id`-Header-Pattern erweitern:**

```python
# backend/api/deps.py
async def get_tenant_id(user: User = Depends(get_current_user)) -> str:
    """Extrahiert Tenant-ID aus dem authentifizierten User."""
    return user.tenant_id

async def get_project_scoped(
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
) -> Project:
    """Validiert, dass der User Zugriff auf das Projekt hat."""
    project = project_store.get(project_id)
    if not project or project.tenant_id != user.tenant_id:
        raise HTTPException(404, "Project not found")  # 404 statt 403 (Security)
    return project
```

**Daten-Isolation pro Tenant:**
- Projekte werden Tenant-zugeordnet: `project.tenant_id = user.tenant_id`
- DMS-Verzeichnisse: `data/tenants/{tenant_id}/projects/{project_id}/dms/`
- Debate-Verzeichnisse: `data/tenants/{tenant_id}/projects/{project_id}/debates/`
- ChromaDB: `data/tenants/{tenant_id}/projects/{project_id}/chroma_db/`

### 2.3 Tenant-Admin-Endpunkte

```
GET    /api/v1/tenants/current          → Eigener Tenant
PUT    /api/v1/tenants/current/settings  → Tenant-Settings ändern (Admin)
GET    /api/v1/tenants/current/users     → User-Liste (Admin)
POST   /api/v1/tenants/current/invite    → User einladen (Admin)
DELETE /api/v1/tenants/current/users/{id} → User entfernen (Admin)
```

### 2.4 Quota-Enforcement

```python
# backend/api/middleware/quota.py
class QuotaMiddleware:
    """Prüft Tenant-Limits vor Ressourcen-Operationen."""

    async def check_debate_quota(self, tenant_id: str):
        active = debate_store.count_active(tenant_id)
        tenant = tenant_store.get(tenant_id)
        if active >= tenant.max_concurrent_debates:
            raise HTTPException(429, "Concurrent debate limit reached")

    async def check_document_quota(self, tenant_id: str):
        count = document_store.count(tenant_id)
        tenant = tenant_store.get(tenant_id)
        if count >= tenant.max_documents:
            raise HTTPException(429, "Document limit reached")
```

### ✅ Phase 2 — Todo-Liste

```
[ ] 2.1  backend/models/tenant.py: Tenant-Pydantic-Modell erstellen
[ ] 2.2  backend/persistence/tenant_store.py: TenantStore (CRUD gegen auth.db)
[ ] 2.3  backend/models/project.py: tenant_id Feld zum Project-Modell hinzufügen
[ ] 2.4  backend/persistence/project_store.py: Tenant-Scoping in list_all(), get()
[ ] 2.5  backend/api/deps.py: get_project_scoped Dependency (validiert Tenant-Zugehörigkeit)
[ ] 2.6  backend/api/routers/tenants.py: Tenant-Admin-Endpunkte (current, settings, users, invite)
[ ] 2.7  backend/services/dms/service.py: DMS-Pfade auf data/tenants/{tenant_id}/ umstellen
[ ] 2.8  backend/persistence/debate_store.py: Debate-Pfade auf data/tenants/{tenant_id}/ umstellen
[ ] 2.9  backend/api/middleware/quota.py: QuotaMiddleware für Debate- und Document-Limits
[ ] 2.10 Alle bestehenden Router: get_project_id durch get_project_scoped ersetzen
[ ] 2.11 frontend: Tenant-Anzeige im Header, Tenant-Settings-Seite
[ ] 2.12 Tests: test_tenant_isolation.py (User A sieht keine Daten von User B)
[ ] 2.13 Tests: test_quota_enforcement.py (Debate-Limit, Document-Limit greifen)
[ ] 2.14 Tests: test_project_scoping.py (Cross-Tenant-Zugriff wird verhindert)
[ ] 2.15 Manueller Test: Zwei User, zwei Tenants — Daten sind vollständig isoliert
```

---

## Phase 3: Task-Queue & parallele Debatten (Woche 5–7)

### 3.1 Task-Queue mit Celery + Redis

**Ziel:** Debatten werden asynchron in Worker-Prozessen ausgeführt, nicht in FastAPI-`BackgroundTasks`.

**Dependencies:**
```toml
# pyproject.toml
"celery[redis]>=5.4.0",
"redis>=5.0.0",
```

**Architektur:**
```
┌─────────────┐     ┌───────────┐     ┌─────────────────┐
│  FastAPI     │────▶│   Redis   │────▶│  Celery Worker   │
│  (API)       │     │  (Broker) │     │  (Debate Engine) │
└─────────────┘     └───────────┘     └─────────────────┘
       │                                      │
       │            ┌───────────┐             │
       └───────────▶│  Redis    │◀────────────┘
                    │  (Result) │
                    └───────────┘
```

```python
# backend/tasks/celery_app.py
from celery import Celery

celery_app = Celery(
    "danwa",
    broker=settings.redis_url,        # redis://localhost:6379/0
    backend=settings.redis_url,
)
celery_app.conf.task_routes = {
    "backend.tasks.debate.*": {"queue": "debates"},
    "backend.tasks.document.*": {"queue": "documents"},
}

# backend/tasks/debate.py
@celery_app.task(bind=True, max_retries=3, soft_time_limit=1800)
def run_debate_task(self, debate_id: str, project_id: str, tenant_id: str):
    """Führt eine Debatte als Celery-Task aus."""
    # LangGraph-Workflow ausführen
    # Status-Updates via Redis pub/sub → SSE
    ...
```

### 3.2 Redis für shared State

**Ersetzt In-Memory-Dicts für:**
- Workflow-Pause/Resume/Cancel-State
- SSE-Event-Bus (Redis pub/sub statt In-Memory)
- DMS-Cache (Redis statt module-level dict)
- Session-Status-Tracking

```python
# backend/state/redis_state.py
class RedisWorkflowState:
    """Redis-backed workflow state for multi-process safety."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def set_session_status(self, session_id: str, status: str):
        self.redis.setex(f"wf:status:{session_id}", 3600, status)

    def get_session_status(self, session_id: str) -> str:
        return self.redis.get(f"wf:status:{session_id}") or "unknown"

    def pause_session(self, session_id: str):
        self.redis.set(f"wf:paused:{session_id}", "1")

    def is_paused(self, session_id: str) -> bool:
        return self.redis.exists(f"wf:paused:{session_id}") == 1
```

### 3.3 SSE über Redis pub/sub

```python
# backend/api/events.py — Refactoring
import redis.asyncio as aioredis

class RedisEventBus:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url)

    async def publish(self, channel: str, event_type: str, data: dict):
        await self.redis.publish(f"sse:{channel}", json.dumps({"event": event_type, "data": data}))

    async def subscribe(self, channel: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"sse:{channel}")
        return pubsub
```

### 3.4 Parallele Debatten — Konfiguration

```python
# backend/core/config.py — neue Felder
max_concurrent_debates_per_tenant: int = 2
max_concurrent_debates_global: int = 20
celery_worker_concurrency: int = 4
redis_url: str = "redis://localhost:6379/0"
```

**Worker-Start:**
```bash
celery -A backend.tasks.celery_app worker -Q debates,documents -c 4 --loglevel=info
```

### ✅ Phase 3 — Todo-Liste

```
[ ] 3.1  pyproject.toml: celery[redis] + redis ergänzen
[ ] 3.2  backend/tasks/__init__.py: Celery-App-Setup
[ ] 3.3  backend/tasks/celery_app.py: Celery-Konfiguration (Broker, Backend, Routing)
[ ] 3.4  backend/tasks/debate.py: run_debate_task (Celery-Task-Wrapper für LangGraph)
[ ] 3.5  backend/tasks/document.py: process_document_task (Upload-Verarbeitung als Task)
[ ] 3.6  backend/state/redis_state.py: RedisWorkflowState (Status, Pause, Cancel)
[ ] 3.7  backend/api/events.py: RedisEventBus (publish/subscribe statt In-Memory)
[ ] 3.8  backend/workflow/workflow_runner.py: Auf Celery-Task-Dispatch umstellen
[ ] 3.9  backend/api/routers/workflow_exec.py: BackgroundTasks durch Celery ersetzen
[ ] 3.10 backend/api/routers/debate.py: BackgroundTasks durch Celery ersetzen
[ ] 3.11 backend/services/dms/service.py: _dms_cache durch Redis-backed Cache ersetzen
[ ] 3.12 backend/core/config.py: redis_url, max_concurrent_debates Settings ergänzen
[ ] 3.13 docker-compose.yml: Redis-Service hinzufügen (für lokale Entwicklung)
[ ] 3.14 Tests: test_celery_debate.py (Task wird dispatched, Status wird gepublisht)
[ ] 3.15 Tests: test_parallel_debates.py (4 gleichzeitige Debatten, keine Konflikte)
[ ] 3.16 Tests: test_redis_state.py (Pause/Resume/Cancel über Redis)
[ ] 3.17 Manueller Test: 2 Debatten parallel starten — laufen unabhängig, SSE funktioniert
```

---

## Phase 4: Server-Infrastruktur & Deployment (Woche 7–9)

### 4.1 Dockerfile (Backend)

```dockerfile
# Dockerfile.backend
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    espeak-ng espeak-ng-data \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

COPY backend/ backend/
COPY config/ config/
COPY modules/ modules/
COPY schemas/ schemas/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

> **Hinweis:** `espeak-ng` wird für `pyttsx3` als Offline-TTS-Engine benötigt. `ffmpeg` wird für Audio-Concatenation benötigt (sowohl für `edge-tts` als auch `pyttsx3`).

### 4.2 Dockerfile (Frontend)

```dockerfile
# Dockerfile.frontend
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 4.3 docker-compose.yml

```yaml
version: "3.9"

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - DANWA_JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DANWA_REDIS_URL=redis://redis:6379/0
      - DANWA_DB_PATH=/data/danwa.db
      - DANWA_CORS_ORIGINS=["https://danwa.example.com"]
    volumes:
      - danwa-data:/data
    depends_on:
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile.backend
    command: celery -A backend.tasks.celery_app worker -Q debates,documents -c 4
    environment:
      - DANWA_REDIS_URL=redis://redis:6379/0
      - DANWA_DB_PATH=/data/danwa.db
    volumes:
      - danwa-data:/data
    depends_on:
      - redis
      - backend
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "443:443"
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

volumes:
  danwa-data:
  redis-data:
```

### 4.4 Nginx-Konfiguration

```nginx
# deploy/nginx.conf
server {
    listen 443 ssl http2;
    server_name danwa.example.com;

    ssl_certificate /etc/letsencrypt/live/danwa.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/danwa.example.com/privkey.pem;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Frontend (SPA)
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # API Proxy
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Upload-Größe
    client_max_body_size 100M;
}

server {
    listen 80;
    server_name danwa.example.com;
    return 301 https://$host$request_uri;
}
```

### 4.5 Gunicorn mit Uvicorn-Workern

```bash
# Produktion statt uvicorn direkt:
gunicorn backend.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 300 \
  --graceful-timeout 30 \
  --keep-alive 5
```

### ✅ Phase 4 — Todo-Liste

```
[ ] 4.1  Dockerfile.backend erstellen (Python 3.12-slim, tesseract, espeak-ng, ffmpeg)
[ ] 4.2  Dockerfile.frontend erstellen (Node 22 build → Nginx alpine)
[ ] 4.3  docker-compose.yml erstellen (backend, celery-worker, frontend, redis)
[ ] 4.4  deploy/nginx.conf erstellen (TLS, API-Proxy, SSE, Security-Headers)
[ ] 4.5  deploy/.env.example erstellen (JWT_SECRET_KEY, REDIS_URL, CORS_ORIGINS)
[ ] 4.6  .dockerignore erstellen (.git, .venv, __pycache__, node_modules, data/)
[ ] 4.7  Makefile: docker-build, docker-up, docker-down Targets ergänzen
[ ] 4.8  Backend-Health-Check: /health Endpoint prüft SQLite + Redis + ChromaDB
[ ] 4.9  docker compose build lokal testen
[ ] 4.10 docker compose up lokal testen (alle Services starten)
[ ] 4.11 TLS: Let's Encrypt Zertifikat generieren (certbot)
[ ] 4.12 Nginx-Konfiguration mit echtem TLS testen
[ ] 4.13 Upload-Test: 50MB-Datei über Nginx hochladen
[ ] 4.14 SSE-Test: Debate-Events kommen über Nginx-Proxy an
[ ] 4.15 Manueller Test: Kompletter Flow über HTTPS (Login → Debate → SSE → Download)
```

---

## Phase 5: Observability, Rate-Limiting & Härtung (Woche 9–10)

### 5.1 Structured Logging

```python
# backend/core/logging.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
    ],
)

# Middleware: Request-ID + User-Kontext
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

### 5.2 Rate-Limiting

```toml
# pyproject.toml
"slowapi>=0.1.9",
```

```python
# backend/main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
app.state.limiter = limiter

# Pro-Endpunkt:
@router.post("/debate")
@limiter.limit("10/minute")
async def create_debate(request: Request, ...):
    ...
```

**Limits (konfigurierbar pro Tenant-Plan):**
| Aktion | Free | Pro | Enterprise |
|--------|------|-----|------------|
| Debate erstellen | 5/h | 50/h | Unlimited |
| Dokument upload | 10/h | 100/h | Unlimited |
| LLM-Analysis | 2/h | 20/h | 100/h |
| API allgemein | 60/min | 300/min | 1000/min |

### 5.3 Health-Checks (erweitert)

```python
# backend/api/routers/health.py
@router.get("/health")
async def health_check():
    checks = {}
    # SQLite
    try:
        db.conn.execute("SELECT 1")
        checks["sqlite"] = "ok"
    except Exception:
        checks["sqlite"] = "error"
    # Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    # ChromaDB
    try:
        chroma.heartbeat()
        checks["chromadb"] = "ok"
    except Exception:
        checks["chromadb"] = "error"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "healthy" if healthy else "degraded", "checks": checks},
    )
```

### 5.4 Prometheus-Metriken

```toml
# pyproject.toml
"prometheus-fastapi-instrumentator>=7.0.0",
```

```python
# backend/main.py
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

**Metriken:**
- `http_requests_total` (nach Endpoint, Status-Code)
- `debate_duration_seconds` (Histogramm)
- `llm_call_duration_seconds` (nach Provider, Modell)
- `llm_tokens_total` (in/out)
- `active_debates_gauge`
- `documents_total` (nach Tenant)

### ✅ Phase 5 — Todo-Liste

```
[ ] 5.1  pyproject.toml: structlog + slowapi + prometheus-fastapi-instrumentator ergänzen
[ ] 5.2  backend/core/logging.py: structlog-Konfiguration (JSON in Prod, Console in Dev)
[ ] 5.3  backend/main.py: Request-ID-Middleware (X-Request-ID Header)
[ ] 5.4  backend/main.py: slowapi Limiter-Setup (Redis-Backend)
[ ] 5.5  Alle kritischen Router: @limiter.limit() Decorators hinzufügen
[ ] 5.6  backend/core/config.py: Rate-Limit-Settings pro Tenant-Plan
[ ] 5.7  backend/api/routers/health.py: Erweiterter Health-Check (SQLite + Redis + ChromaDB)
[ ] 5.8  backend/main.py: Prometheus Instrumentator registrieren
[ ] 5.9  deploy/prometheus.yml: Prometheus-Konfiguration (optional, für Monitoring-Server)
[ ] 5.10 Alle logger.* Aufrufe: structlog-Binding für request_id und user_id prüfen
[ ] 5.11 Tests: test_rate_limiting.py (429 nach X Anfragen)
[ ] 5.12 Tests: test_health_check.py (ok, degraded, error States)
[ ] 5.13 Manueller Test: Rate-Limit greift, /health zeigt korrekte States, /metrics liefert Daten
```

---

## Phase 6: Migration, Testing & Go-Live (Woche 10–12)

### 6.1 Datenbank-Migration

**Bestehende Daten migrieren:**
1. Default-Tenant `_default` erstellen
2. Alle bestehenden Projects → `_default`-Tenant zuordnen
3. Admin-User erstellen (Seed)
4. Bestehende DMS/Debate-Verzeichnisse unter `data/tenants/_default/` neu strukturieren

```python
# backend/migrations/v001_multi_tenant.py
def migrate_to_multi_tenant():
    """Migriert Single-User-Daten zum Multi-Tenant-Modell."""
    # 1. Tenant-Tabelle erstellen
    # 2. Default-Tenant anlegen
    # 3. User-Tabelle erstellen
    # 4. Admin-User seeden
    # 5. Projects.tenant_id = '_default' setzen
    # 6. Verzeichnisse verschieben
    ...
```

### 6.2 CI/CD-Pipeline (erweitert)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make test
      - run: make lint

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build
      - run: docker compose push

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production
    steps:
      - run: ssh deploy@server "cd /opt/danwa && docker compose pull && docker compose up -d"
```

### 6.3 Integrationstests

```python
# tests/integration/test_multi_tenant.py
async def test_user_cannot_access_other_tenant_projects(): ...
async def test_debate_quota_enforcement(): ...
async def test_parallel_debates_different_tenants(): ...
async def test_jwt_token_refresh_flow(): ...
async def test_document_upload_respects_tenant_storage_limit(): ...
```

### ✅ Phase 6 — Todo-Liste

```
[ ] 6.1  backend/migrations/v001_multi_tenant.py: Migrationsskript schreiben
[ ] 6.2  Migration testen: Lokale DB sichern → Migration ausführen → Daten prüfen
[ ] 6.3  data/ Verzeichnisstruktur auf Tenant-Pfade umstellen
[ ] 6.4  Seed-Admin: admin@danwa.local wird automatisch erstellt
[ ] 6.5  .github/workflows/deploy.yml: CI/CD-Pipeline mit Docker-Build
[ ] 6.6  Integrationstests schreiben (test_multi_tenant.py, 5+ Tests)
[ ] 6.7  E2E-Tests: Login → Tenant erstellen → Projekt → Debate → Download
[ ] 6.8  Backup-Test: Backup erstellen → Restore → Daten vollständig
[ ] 6.9  Lasttest: 10 parallele Debatten, Response-Zeiten messen
[ ] 6.10 Sicherheitstest: SQL-Injection, XSS, CORS, Rate-Limiting verifizieren
[ ] 6.11 Dokumentation: README.md aktualisieren (Setup, Deployment, Konfiguration)
[ ] 6.12 Go-Live: Produktivserver aufsetzen, Docker deployen, TLS verifizieren
[ ] 6.13 Monitoring: Prometheus + Grafana Dashboard einrichten (optional)
[ ] 6.14 Post-Go-Live: Logs prüfen, erste echte Debatten durchführen
```

---

## TTS: pyttsx3 als zusätzliche Option

### Hintergrund

Die aktuelle TTS-Implementierung verwendet `edge-tts` (LGPL-3.0), das eine Internetverbindung zu Microsofts Edge-TTS-Dienst benötigt. Als AGPL-konforme Offline-Alternative wird `pyttsx3` (MIT-Lizenz) integriert.

### Architektur

```
backend/services/output/plugins/
├── edge_tts_renderer.py      ← Bestehend (edge-tts, benötigt Internet)
├── pyttsx3_renderer.py       ← NEU (pyttsx3 + espeak-ng, Offline)
├── tts_plugin.py             ← Gemeinsames Interface (TTSScript → Audio)
└── tts_models.py             ← Gemeinsame Modelle (TTSScript, TTSSegment)
```

### pyttsx3-Renderer

```python
# backend/services/output/plugins/pyttsx3_renderer.py
"""Pyttsx3Renderer — renders TTSScript to audio via pyttsx3 (Offline TTS).

Pipeline:
  1. For each segment: pyttsx3 → temp .wav file
  2. Generate silence files for pauses via ffmpeg anullsrc
  3. Build concat_list.txt with all segments + silences in order
  4. ffmpeg -f concat → final audio file (mp3/wav)
  5. Optionally clean up segment files
"""

class Pyttsx3Renderer:
    """Renders a ``TTSScript`` to audio using pyttsx3 + ffmpeg.

    Offline-capable — uses espeak-ng as TTS backend.
    Stateless — a fresh instance is created per render call.
    """

    async def render(
        self,
        script: TTSScript,
        job_id: str,
        output_dir: Path,
        output_format: AudioFormat = AudioFormat.MP3,
        bitrate: str = "128k",
        keep_segments: bool = False,
    ) -> Path:
        """Render the TTS script to an audio file."""
        # 1. Initialize pyttsx3 engine
        # 2. For each segment: engine.save_to_file → .wav
        # 3. Generate silence for pauses
        # 4. Concatenate via ffmpeg
        # 5. Cleanup
        ...

    @staticmethod
    def _render_segment(text: str, voice_id: str, output_path: Path) -> None:
        """Render a single text segment to WAV via pyttsx3."""
        import pyttsx3
        engine = pyttsx3.init()
        if voice_id:
            engine.setProperty('voice', voice_id)
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
```

### Dependencies

```toml
# pyproject.toml — zusätzlich zu edge-tts
"pyttsx3>=2.90",
```

### Dockerfile-Anpassung

```dockerfile
# pyttsx3 benötigt espeak-ng als System-Backend
RUN apt-get install -y --no-install-recommends espeak-ng espeak-ng-data
```

### Renderer-Auswahl in der API

```python
# backend/services/output/registry.py — Erweiterung
TTS_RENDERERS = {
    "edge-tts": EdgeTTSRenderer,     # Cloud, hohe Qualität
    "pyttsx3": Pyttsx3Renderer,      # Offline, eingeschränkte Qualität
}

def get_tts_renderer(engine: str = "edge-tts"):
    """Returns the TTS renderer for the given engine name."""
    renderer_cls = TTS_RENDERERS.get(engine)
    if not renderer_cls:
        raise ValueError(f"Unknown TTS engine: {engine}. Available: {list(TTS_RENDERERS.keys())}")
    return renderer_cls()
```

### Einstellbar pro Tenant

```python
# Tenant-Settings
class TenantSettings(BaseModel):
    tts_engine: Literal["edge-tts", "pyttsx3"] = "edge-tts"
    tts_default_voice: str = "de-DE-KatjaNeural"  # edge-tts voice
    tts_pyttsx3_voice: str = "de"                   # espeak-ng voice
```

### ✅ TTS — Todo-Liste

```
[ ] T.1  pyproject.toml: pyttsx3>=2.90 ergänzen
[ ] T.2  backend/services/output/plugins/pyttsx3_renderer.py: Renderer implementieren
[ ] T.3  backend/services/output/registry.py: TTS_RENDERERS dict + get_tts_renderer()
[ ] T.4  backend/models/tenant.py: tts_engine in TenantSettings aufnehmen
[ ] T.5  backend/api/routers/verweistelle TTS-Engine-Auswahl in Debate-Config
[ ] T.6  Dockerfile.backend: espeak-ng Pakete ergänzen
[ ] T.7  Test: pyttsx3 rendert TTSScript zu WAV/MP3
[ ] T.8  Test: Fallback wenn edge-tts nicht erreichbar → pyttsx3
[ ] T.9  Manueller Test: Debate-Podcast mit pyttsx3 generieren, Qualität prüfen
```

---

## Technologie-Stack (Zusammenfassung)

| Komponente | Ist | Soll |
|------------|-----|------|
| **Auth** | Keine | JWT (`python-jose`) + bcrypt (`passlib`) |
| **User-DB** | Keine | SQLite `auth.db` (Users, Tenants, Roles) |
| **Task-Queue** | `BackgroundTasks` | Celery + Redis |
| **Shared State** | In-Memory-Dicts | Redis |
| **SSE** | In-Memory pub/sub | Redis pub/sub |
| **TTS** | `edge-tts` (Cloud) | `edge-tts` + `pyttsx3` (Offline) |
| **Deployment** | `manage.sh` (nohup) | Docker Compose + Nginx + TLS |
| **WSGI-Server** | Uvicorn (single) | Gunicorn + Uvicorn-Worker (4x) |
| **Rate-Limiting** | Keine | `slowapi` + Redis |
| **Logging** | `logging` (unstructured) | `structlog` (JSON, mit Request-IDs) |
| **Monitoring** | Keine | Prometheus + `/metrics` + `/health` |
| **TLS** | Keine | Let's Encrypt via Nginx |
| **CI/CD** | GitHub Actions (lint+test) | + Docker Build + Deploy |

---

## Risiken & Abhängigkeiten

| Risiko | Impact | Mitigation |
|--------|--------|------------|
| SQLite-Skalierung bei vielen Tenants | MEDIUM | SQLite WAL + Monitoring; bei >50 Tenants: Migration zu PostgreSQL |
| Celery-Worker-Crash verliert Task-State | MEDIUM | `acks_late=True` + `task_reject_on_worker_lost=True` |
| Redis als Single Point of Failure | HIGH | Redis Sentinel oder Redis Cluster für HA |
| JWT-Secret-Leak | CRITICAL | Secret via Environment Variable, nie im Code; Rotation-Plan |
| Breaking Changes in API durch Auth-Pflicht | MEDIUM | Phase-1-Release mit opt-in Auth, dann erzwingen |
| LangGraph-Compatibility mit Celery | LOW | LangGraph ist synchron-kompatibel; `asyncio.run()` in Celery-Task |
| pyttsx3 Qualität vs. edge-tts | LOW | pyttsx3 als Fallback/Offline-Option, nicht als Standard |

---

## Meilensteine & Abnahmekriterien

| Meilenstein | Kriterium | Woche |
|-------------|-----------|-------|
| **M1: Auth funktioniert** | Login/Logout, JWT, Rollen-Check, Frontend-Guards | 3 |
| **M2: Tenants isoliert** | User A sieht keine Daten von User B, Quotas greifen | 5 |
| **M3: Parallele Debatten** | 4 Debatten gleichzeitig, keine In-Memory-Konflikte | 7 |
| **M4: Docker-Deployment** | `docker compose up` startet alles, TLS funktioniert | 9 |
| **M5: Production-Härtung** | Rate-Limiting, Monitoring, Structured Logging, Health-Checks | 10 |
| **M6: Go-Live** | Migration bestehender Daten, Integrationstests grün, Backup-Verifikation | 12 |

---

## Anhang: Lizenz-Kompatibilität (AGPL-3.0)

Alle eingesetzten Komponenten müssen mit der AGPL-3.0-Lizenz des Gesamtprojekts kompatibel sein.

### Neue Komponenten (im Plan vorgeschlagen)

| Komponente | Lizenz | AGPL-kompatibel | Anmerkung |
|------------|--------|-----------------|-----------|
| `python-jose[cryptography]` | MIT | ✅ | |
| `cryptography` (Transitive) | Apache-2.0 OR BSD-3-Clause | ✅ | Dual-Licensed |
| `passlib[bcrypt]` | BSD-3-Clause | ✅ | |
| `bcrypt` (Transitive) | Apache-2.0 | ✅ | |
| `celery[redis]` | BSD-3-Clause | ✅ | |
| `redis` (Python-Client) | MIT | ✅ | |
| `slowapi` | MIT | ✅ | |
| `structlog` | Apache-2.0 OR MIT | ✅ | Dual-Licensed |
| `prometheus-fastapi-instrumentator` | MIT | ✅ | |
| `gunicorn` | MIT | ✅ | |
| `nginx` | BSD-2-Clause | ✅ | Kein Python-Paket |
| Docker / docker-compose | Apache-2.0 | ✅ | Nur Infrastruktur |
| **`pyttsx3`** | **MIT** | **✅** | Offline-TTS, AGPL-konform |

### Bestehende Komponenten (aus pyproject.toml)

| Komponente | Lizenz | AGPL-kompatibel | Anmerkung |
|------------|--------|-----------------|-----------|
| `fastapi` | MIT | ✅ | |
| `uvicorn` | BSD-3-Clause | ✅ | |
| `pydantic` | MIT | ✅ | |
| `pydantic-settings` | MIT | ✅ | |
| `httpx` | BSD-3-Clause | ✅ | |
| `chromadb` | Apache-2.0 | ✅ | |
| `langgraph` | MIT | ✅ | |
| `langchain-core` | MIT | ✅ | |
| `litellm` | MIT | ✅ | |
| `sse-starlette` | MIT | ✅ | |
| `pdfplumber` | MIT | ✅ | |
| `pypdf` | BSD-3-Clause | ✅ | |
| `python-docx` | MIT | ✅ | |
| `weasyprint` | BSD-3-Clause | ✅ | |
| `tiktoken` | MIT | ✅ | |
| `rank_bm25` | MIT | ✅ | |
| `jinja2` | BSD-3-Clause | ✅ | |
| `pyyaml` | MIT | ✅ | |
| `markdown` | BSD-3-Clause | ✅ | |
| `python-dotenv` | BSD-3-Clause | ✅ | |
| `python-multipart` | Apache-2.0 | ✅ | |
| `odfpy` | Apache-2.0 | ✅ | |
| `pypandoc` | MIT | ✅ | |
| `pytesseract` | Apache-2.0 | ✅ | |
| `ddgs` | MIT | ✅ | |
| `paddleocr` | Apache-2.0 | ✅ | Optional |
| **`edge-tts`** | **LGPL-3.0** | **⚠️ Ja, mit Einschränkung** | Siehe unten |

### Hinweis zu `edge-tts` (LGPL-3.0)

`edge-tts` steht unter der **LGPL-3.0**. Die LGPL-3.0 ist mit der AGPL-3.0 **kompatibel**, solange:

1. `edge-tts` als separates Python-Modul importiert bleibt (dynamisch geladen).
2. Der LGPL-3.0-Text zusammen mit der Software verteilt wird.
3. Der Quellcode von `edge-tts` verfügbar ist.

**Empfehlung:** `edge-tts` ist sicher verwendbar. `pyttsx3` (MIT) wird als zusätzliche Offline-Option integriert, sodass bei LGPL-Bedenken auf eine vollständig AGPL-konforme Alternative zurückgegriffen werden kann.

### Zusammenfassung

**Alle Komponenten sind AGPL-3.0-kompatibel.** Mit der Integration von `pyttsx3` existiert eine vollständig AGPL-konforme Offline-TTS-Alternative zu `edge-tts`.
