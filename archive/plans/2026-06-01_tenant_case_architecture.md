# Tenant-fähige Case-Architektur — Implementierungsplan

## 0. Entscheidungen

| Frage | Entscheidung |
|-------|-------------|
| Tenant im Pfad vs. Header | **Pfad** (`/tenants/{tid}/cases/{cid}/...`) — selbst-dokumentierend, Caching/Logging |
| Tags hierarchisch? | **Flach für MVP**, `parent_id` für spätere Hierarchie vorsehen |
| Tags tenant-global oder user-global? | **Tenant-global** — Team-Arbeit erfordert gemeinsames Schema |
| Ein User in mehreren Tenants? | **Ja** — Mitgliedschafts-Modell, aktiver Tenant pro Session |
| default-Projekt? | Pro Tenant als `cases/_default` |
| Dokumente zwischen Cases teilen? | **Nein** — DMS pro Case isoliert (Spillover-Risiko vermeiden) |
| Migration alter Projekte? | **Keine Symlinks** — sauber `shutil.move()` und Pfade anpassen |
| Tests? | **Neue Tests für jede Phase** |

---

## 1. Phase 0 — CaseStore + Case-Modell (ohne Pfad-Umstellung)

Backend-only. Case-Modell parallel zu Project einführen, CaseStore bauen, API-Endpunkte bereitstellen ohne bestehende Logik zu ändern.

### 1.1 Neues Modell: `Case`

**Datei:** `backend/models/case.py` (NEU)

```python
class Case(BaseModel):
    id: str
    tenant_id: str
    title: str
    description: str = ""
    status: str = "active"       # active | archived | closed
    tags: list[str] = []         # Tag-IDs
    created_by: str
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}
```

### 1.2 Neuer Store: `CaseStore`

**Datei:** `backend/persistence/case_store.py` (NEU)
- JSON-file basiert (analog `ProjectStore`)
- `__init__(base_dir: Path)` — base dir ist `data/tenants/` (default)
- `create(tenant_id, title, ...)` — legt `tenants/{tid}/cases/{cid}/case.json` an
- `get(tenant_id, case_id)` — liest aus JSON
- `list_by_tenant(tenant_id)` — listet alle Cases eines Tenants
- `update(tenant_id, case_id, **kwargs)` — updated case.json
- `delete(tenant_id, case_id)` — archiviert (setzt status=closed)
- `get_case_dir(tenant_id, case_id)` → `data/tenants/{tid}/cases/{cid}/`

### 1.3 Neues Modell: `Tag`

**Datei:** `backend/models/tag.py` (NEU)

```python
class Tag(BaseModel):
    id: str
    tenant_id: str
    name: str
    color: str = "#6366f1"
    parent_id: str | None = None
    created_at: datetime
```

### 1.4 Neuer Store: `TagStore`

**Datei:** `backend/persistence/tag_store.py` (NEU)
- Speichert alle Tags eines Tenants in `tenants/{tid}/tags.json`
- `list_by_tenant(tenant_id)` → list all tags
- `create(tenant_id, name, color)` → fügt Tag hinzu
- `update(tenant_id, tag_id, ...)` → aktualisiert Tag
- `delete(tenant_id, tag_id)` → entfernt Tag aus tags.json + aus allen Cases, die ihn referenzieren
- Lazy-loading und Cache wie ProjectStore

### 1.5 Neue API-Endpunkte

**Datei:** `backend/api/routers/cases.py` (NEU)
- `GET /api/v1/tenants/{tid}/cases` — Cases im Tenant
- `POST /api/v1/tenants/{tid}/cases` — Case anlegen
- `GET /api/v1/tenants/{tid}/cases/{cid}` — Case-Details
- `PATCH /api/v1/tenants/{tid}/cases/{cid}` — Case updaten
- `DELETE /api/v1/tenants/{tid}/cases/{cid}` — Case archivieren

**Datei:** `backend/api/routers/tags.py` (NEU)
- `GET /api/v1/tenants/{tid}/tags` — Tags auflisten
- `POST /api/v1/tenants/{tid}/tags` — Tag anlegen
- `PUT /api/v1/tenants/{tid}/tags/{tagId}` — Tag umbenennen
- `DELETE /api/v1/tenants/{tid}/tags/{tagId}` — Tag löschen

**Router-Registrierung** in `backend/main.py`:
```python
app.include_router(cases_router, prefix="/api/v1")
app.include_router(tags_router, prefix="/api/v1")
```

### 1.6 Tests für Phase 0

**Dateien:**
- `tests/backend/test_cases.py` — CaseStore CRUD, Case-API
- `tests/backend/test_tags.py` — TagStore CRUD, Tag-API, Tag-Case-Verlinkung
- `tests/backend/test_case_isolation.py` — Cases verschiedener Tenants sind getrennt

**Test-Setup:** CaseStore mit `tmp_path / "test_tenants"` initialisieren, analog zu ProjectStore-Tests.

---

## 2. Phase 1 — Tenant-Mitgliedschaft (Multi-Tenant-User)

User können Mitglied mehrerer Tenants sein. Aktiver Tenant wird pro Session gewählt.

### 2.1 Neues Modell: `TenantMembership`

**Datei:** `backend/models/membership.py` (NEU)

```python
class TenantMembership(BaseModel):
    tenant_id: str
    user_id: str
    role: str = "member"   # admin | member | viewer
    invited_by: str | None = None
    joined_at: datetime
```

### 2.2 Neuer Store: `MembershipStore`

**Datei:** `backend/persistence/membership_store.py` (NEU)
- SQLite in `data/tenants.db` (oder existierende `data/auth.db` erweitern)
- Tabelle `memberships` mit Spalten: `tenant_id`, `user_id`, `role`, `invited_by`, `joined_at`
- `add(tenant_id, user_id, role)` — Mitglied hinzufügen
- `remove(tenant_id, user_id)` — Mitglied entfernen
- `get(tenant_id, user_id)` → Membership | None
- `list_by_user(user_id)` → alle Tenants des Users
- `list_by_tenant(tenant_id)` → alle Mitglieder eines Tenants

### 2.3 User-Modell ändern

**Datei:** `backend/models/user.py`
- `tenant_id: str = "_default"` bleibt erstmal als "aktiver Tenant"
- Füge `tenant_ids: list[str] = []` oder `memberships: list[TenantMembership]` hinzu (via MembershipStore abfragen, nicht im Modell speichern)

**Alternative:** User-Modell lässt man unverändert. Der "aktive Tenant" wird im JWT-Token + Session-State geführt, nicht im User-Modell. Der User kann seinen aktiven Tenant über einen API-Call wechseln (→ neuer JWT).

### 2.4 Auth-Erweiterungen

**Datei:** `backend/api/routers/auth.py`
- `POST /api/v1/auth/select-tenant/{tenant_id}` — aktiven Tenant wechseln, neuen JWT ausstellen
- `GET /api/v1/auth/my-tenants` — meine Tenants auflisten (via MembershipStore)

**Datei:** `backend/api/deps.py`
- Neue Dependency: `get_active_tenant(user=Depends(get_current_user), tenant_id: str | None = Header(None, alias="X-Tenant-Id"))` → validiert Membership, gibt tenant_id zurück
- Falls kein X-Tenant-Id Header: `user.tenant_id` (aktueller aktiver Tenant aus JWT)

### 2.5 Tenant-Auswahl-Frontend

**Datei:** `frontend/src/lib/stores.js`
- Neuer Store: `activeTenant` (analog zu `activeProject`)

**Datei:** `frontend/src/lib/api/core.js`
- `X-Tenant-Id` Header automatisch aus `activeTenant`-Store in jede Request injecten

**Datei:** `frontend/src/components/TenantSelector.svelte` (NEU)
- Nach Login: Liste der Tenants des Users
- Auswahl setzt `activeTenant` + ruft `POST /auth/select-tenant/{id}` auf

### 2.6 Tests für Phase 1

**Dateien:**
- `tests/backend/test_membership.py` — MembershipStore CRUD, Multi-Tenant-User
- `tests/backend/test_auth_extended.py` — Tenant-Wechsel, JWT mit aktuellem Tenant
- `tests/backend/test_api_isolation.py` — API-Calls ohne gültigen Tenant werden 403

---

## 3. Phase 2 — Pfad-Umstellung (CaseStore wird aktiv)

ProjectStore wird auf CaseStore umgestellt. **Alle** Pfade wechseln von `data/projects/{id}/` → `data/tenants/{tid}/cases/{cid}/`.

### 3.1 ProjectStore umschreiben

**Datei:** `backend/persistence/project_store.py`
- `get_project_dir(project_id)` → `data/tenants/{tid}/cases/{project_id}/` statt `data/projects/{project_id}/`
- `create()` erstellt Ordner im neuen Pfad
- `_load_all()` scannt `data/tenants/*/cases/*/case.json`

**Wichtig:** `project_store.get(project_id)` und `list_by_tenant()` müssen ohne Änderung der aufrufenden Stellen funktionieren. Alle DMS/Debate-Pfade leiten sich aus `get_project_dir()` ab — also reicht dieser eine Fix.

### 3.2 DMS-Factory anpassen

**Datei:** `backend/services/dms/service.py`
- `get_dms_for_project()` nutzt `project_store.get_project_dir(project_id)` → wird automatisch korrekt
- **Keine Änderung nötig**, weil DMS-Pfade aus `get_project_dir()` abgeleitet werden

### 3.3 DebateStore-Pfade prüfen

**Datei:** `backend/persistence/debate_store.py`
- `debates_dir = self._project_store.get_project_dir(project_id) / "debates"` → funktioniert automatisch über den fix in ProjectStore

### 3.4 Migration existierender Projekte

**Script:** `backend/migrations/v002_case_pfade.py` (NEU)

```python
async def run():
    old_base = Path("data/projects")
    new_base = Path("data/tenants")
    
    for project_dir in old_base.iterdir():
        if not project_dir.is_dir():
            continue
        project_json = project_dir / "project.json"
        if not project_json.exists():
            continue
        
        project = json.loads(project_json.read_text())
        tenant_id = project.get("tenant_id", "_default")
        case_id = project["id"]
        
        target = new_base / tenant_id / "cases" / case_id
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Sauber moven (kein Symlink)
        shutil.move(str(project_dir), str(target))
        
        # case.json aus project.json generieren
        case = {
            "id": project["id"],
            "tenant_id": tenant_id,
            "title": project["name"],
            "description": project.get("description", ""),
            "status": "active",
            "tags": [],
            "created_by": "",
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
            "metadata": {"config": project.get("config", {})},
        }
        (target / "case.json").write_text(json.dumps(case))
    
    # Leeres altes Verzeichnis mit .moved-Marker
    (old_base / ".moved_to_tenant_cases").write_text(
        json.dumps({"migrated_at": datetime.now(UTC).isoformat()})
    )
```

**Ablauf:**
1. Migration skript on deploy
2. Erst danach ProjectStore umstellen
3. Alte `data/projects/` werden nicht mehr gelesen

### 3.5 API-Dependencies aktualisieren

**Datei:** `backend/api/deps.py`
- `get_project_scoped()` — bisher prüft `project.tenant_id == current_user.tenant_id`. Neu mit Membership-Validierung kombinieren.
- `get_debate_store_for_project()` — bleibt unverändert (nutzt ProjectStore intern)

### 3.6 X-Project-Id → X-Case-Id (optional, in späterem Schritt)

Backward-compat: `X-Project-Id` Header wird weiterhin akzeptiert, aber intern als `case_id` interpretiert. Neuer Header `X-Case-Id` wird zusätzlich unterstützt.

### 3.7 Tests für Phase 2

**Dateien:**
- `tests/backend/test_migration_v002.py` — Migration alter Projekte in neue Pfade
- `tests/backend/test_project_store_compat.py` — ProjectStore funktioniert nach Pfad-Umstellung
- `tests/backend/test_dms_paths.py` — DMS-Pfade enthalten tenant_id + case_id

---

## 4. Phase 3 — API-Routen umstellen

Alle bestehenden Endpunkte bekommen Tenant+Case im Pfad. Alte Pfade bleiben als Deprecation erhalten.

### 4.1 Neue Router-Struktur

```python
# backend/api/routers/tenant_debates.py (NEU)
router = APIRouter(prefix="/api/v1/tenants/{tid}/cases/{cid}/debates")

# backend/api/routers/tenant_dms.py (NEU)
router = APIRouter(prefix="/api/v1/tenants/{tid}/cases/{cid}/dms")

# backend/api/routers/tenant_workflows.py (NEU)
router = APIRouter(prefix="/api/v1/tenants/{tid}/cases/{cid}/workflows")
```

Neue Router delegieren an bestehende Logik (DebateStore, DMS, WorkflowRunner), aber mit tenant_id + case_id als zusätzlichen Parametern.

### 4.2 Alte Endpunkte als Deprecation

Bestehende Router (`/api/v1/debate/*`, `/api/v1/dms/*`, `/api/v1/workflow-exec/*`) bleiben aktiv, aber:
- Response-Header `X-Deprecation: use /api/v1/tenants/...` 
- Response Body enthält `deprecation_notice` Feld
- Nach 2 Versionen entfernen

### 4.3 Tenant-ID in JWT + Requests

**Datei:** `backend/api/deps.py`

```python
async def get_tenant_context(
    current_user = Depends(get_current_user),
    tenant_id: str = Path(..., alias="tid"),
) -> str:
    """Validates user membership and returns tenant_id."""
    memberships = membership_store.list_by_user(current_user.id)
    if not any(m.tenant_id == tenant_id for m in memberships):
        raise HTTPException(403, "Not a member of this tenant")
    return tenant_id

async def get_case_context(
    tenant_id = Depends(get_tenant_context),
    case_id: str = Path(..., alias="cid"),
) -> Case:
    case = case_store.get(tenant_id, case_id)
    if not case:
        raise HTTPException(404)
    return case
```

### 4.4 Tests für Phase 3

- `tests/backend/test_tenant_routes.py` — Neue Tenant-Routen funktionieren
- `tests/backend/test_deprecation_headers.py` — Alte Routen senden Deprecation-Header

---

## 5. Phase 4 — Frontend-Umbau

### 5.1 Tenant-Auswahl

**Neu:** `TenantSelector.svelte`
**Geändert:** `App.svelte`, `Header.svelte`, `Sidebar.svelte`
- Nach Login: Tenant-Auswahl-Seite
- Aktiven Tenant anzeigen + wechseln können
- Alle API-Requests: `X-Tenant-Id` + `X-Case-Id` Header

### 5.2 Case-Navigation statt Projekt-Navigation

**Geändert:**
- `frontend/src/views/ProjectsView.svelte` → `CasesView.svelte`
- `frontend/src/components/ProjectSelector.svelte` → `CaseSelector.svelte`
- Sidebar: "Fälle" statt "Projekte"
- Case-Liste mit Tag-Filtern
- Case-Detail-Ansicht mit Tag-Editor

### 5.3 Tag-UI

**Neu:** `TagManager.svelte`, `TagBadge.svelte`, `TagSelector.svelte`
- Tag-Editor in Tenant-Settings
- Multi-Select Tag-Auswahl bei Case-Erstellung/Bearbeitung
- Tags als Badges und Filter in Case-Liste

### 5.4 Bestehende Views anpassen

- `DebateView.svelte`, `DocumentsView.svelte`, `MvpDebateView.svelte`, `Dashboard.svelte`
- Bekommen `case_id` als zusätzlichen Store/Parameter
- API-Calls nutzen neue Pfade

### 5.5 Tests für Phase 4

- `tests/frontend/` — (wenn Frontend-Tests existieren) Case-Navigation, Tag-Filter

---

## 6. Details zur Pfad-Umstellung

### 6.1 Neues Pfadschema

```
data/
└── tenants/
    └── {tenant_id}/
        ├── cases/
        │   ├── _default/           # Default-Case jedes Tenants
        │   │   ├── case.json
        │   │   ├── debates/
        │   │   └── dms/
        │   │       ├── dms.db
        │   │       ├── chroma_db/
        │   │       └── documents/
        │   └── {case_id}/
        │       ├── case.json
        │       ├── debates/
        │       └── dms/
        │           ├── dms.db
        │           ├── chroma_db/
        │           └── documents/
        └── tags.json
```

### 6.2 ProjectStore-Kompatibilität

```python
class ProjectStore:
    def __init__(self, base_dir: str | Path = "data"):
        self._base_dir = Path(base_dir) / "tenants"
    
    def get_project_dir(self, tenant_id: str | None, project_id: str) -> Path:
        """ProjectStore delegiert an Case-Pfad."""
        tid = tenant_id or "_default"
        return self._base_dir / tid / "cases" / project_id
```

**Problem:** Viele Aufrufer von `get_project_dir()` übergeben nur `project_id`, nicht `tenant_id`. Wir brauchen entweder:
1. **Option A:** `get_project_dir(project_id)` liest `project.json` aus altem Pfad, ermittelt `tenant_id`, dann neuer Pfad — teuer
2. **Option B:** `get_project_dir(project_id, tenant_id)` mit tenant_id als Pflichtparameter — viele Änderungen
3. **Option C:** Internen Cache pflegen: `self._project_tenant: dict[str, str]` mappt project_id → tenant_id. Wird beim Laden befüllt.

**Empfehlung:** **Option B** — tenant_id als Parameter ergänzen. Alle Aufrufer anpassen. Das ist der sauberste Weg und disambiguiert project_ids über Tenant-Grenzen hinweg.

### 6.3 Änderungen an get_project_dir-Aufrufern

Folgende Dateien übergeben `project_id` an `get_project_dir()` und müssen um `tenant_id` ergänzt werden:

| Datei | Aufruf | Fix |
|-------|--------|-----|
| `backend/api/deps.py:get_project_scoped()` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |
| `backend/services/dms/service.py:get_dms_for_project()` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |
| `backend/services/render_engine.py` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |
| `backend/services/debate_workflow.py` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |
| `backend/services/debate/debate_rag.py` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |
| `backend/workflow/nodes.py` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |
| `backend/workflow/legacy_nodes.py` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |
| `backend/tasks/debate.py` | `store.get_project_dir(project_id)` | `store.get_project_dir(project.tenant_id, project_id)` |

### 6.4 Keine Symlinks

Migration verwendet `shutil.move()` (s. 3.4). Danach existieren `data/projects/` nicht mehr als Quelle. Ein Marker-File `.moved_to_tenant_cases` verhindert versehentliche Neu-Nutzung.

---

## 7. Detaillierte File-Changes pro Phase

### Phase 0 — Case/Tag Model + Store + API

| Aktion | Datei | Änderung |
|--------|-------|----------|
| CREATE | `backend/models/case.py` | Case-Modell |
| CREATE | `backend/models/tag.py` | Tag-Modell |
| CREATE | `backend/persistence/case_store.py` | CaseStore (JSON, pro Case) |
| CREATE | `backend/persistence/tag_store.py` | TagStore (JSON, pro Tenant) |
| CREATE | `backend/api/routers/cases.py` | Case-CRUD-Endpunkte |
| CREATE | `backend/api/routers/tags.py` | Tag-CRUD-Endpunkte |
| MODIFY | `backend/main.py` | Neue Router registrieren |
| CREATE | `tests/backend/test_cases.py` | Case-Tests |
| CREATE | `tests/backend/test_tags.py` | Tag-Tests |
| CREATE | `tests/backend/test_case_isolation.py` | Isolationstests |

### Phase 1 — Tenant-Mitgliedschaft

| Aktion | Datei | Änderung |
|--------|-------|----------|
| CREATE | `backend/models/membership.py` | TenantMembership-Modell |
| CREATE | `backend/persistence/membership_store.py` | MembershipStore (SQLite) |
| MODIFY | `backend/api/routers/auth.py` | select-tenant, my-tenants Endpunkte |
| MODIFY | `backend/api/deps.py` | get_active_tenant Dependency |
| MODIFY | `backend/core/security.py` | JWT: aktueller Tenant im Token |
| CREATE | `frontend/src/lib/stores.js` | activeTenant-Store |
| MODIFY | `frontend/src/lib/api/core.js` | X-Tenant-Id Header |
| CREATE | `frontend/src/components/TenantSelector.svelte` | Tenant-Auswahl-UI |
| CREATE | `tests/backend/test_membership.py` | Membership-Tests |

### Phase 2 — Pfad-Umstellung

| Aktion | Datei | Änderung |
|--------|-------|----------|
| MODIFY | `backend/persistence/project_store.py` | get_project_dir(tenant_id, project_id), Pfad-Umstellung |
| MODIFY | `backend/api/deps.py` | get_project_scoped tenant-Parameter ergänzen (s. 6.3) |
| MODIFY | `backend/services/dms/service.py` | tenant_id in get_dms_for_project (s. 6.3) |
| MODIFY | `backend/services/render_engine.py` | tenant_id ergänzen (s. 6.3) |
| MODIFY | `backend/services/debate_workflow.py` | tenant_id ergänzen (s. 6.3) |
| MODIFY | `backend/services/debate/debate_rag.py` | tenant_id ergänzen (s. 6.3) |
| MODIFY | `backend/workflow/nodes.py` | tenant_id ergänzen (s. 6.3) |
| MODIFY | `backend/workflow/legacy_nodes.py` | tenant_id ergänzen (s. 6.3) |
| MODIFY | `backend/tasks/debate.py` | tenant_id ergänzen (s. 6.3) |
| CREATE | `backend/migrations/v002_case_pfade.py` | Migration alter Projekte |
| MODIFY | `backend/persistence/debate_store.py` | Pfad-Prüfung |
| CREATE | `tests/backend/test_migration_v002.py` | Migration-Tests |
| CREATE | `tests/backend/test_project_store_compat.py` | Kompatibilitätstests |

### Phase 3 — API-Routen Umstellung

| Aktion | Datei | Änderung |
|--------|-------|----------|
| CREATE | `backend/api/routers/tenant_debates.py` | Neue /tenants/{tid}/cases/{cid}/debates/* |
| CREATE | `backend/api/routers/tenant_dms.py` | Neue /tenants/{tid}/cases/{cid}/dms/* |
| CREATE | `backend/api/routers/tenant_workflows.py` | Neue /tenants/{tid}/cases/{cid}/workflows/* |
| MODIFY | `backend/api/routers/debate.py` | Deprecation-Header |
| MODIFY | `backend/api/routers/dms.py` | Deprecation-Header |
| MODIFY | `backend/api/routers/workflow_exec.py` | Deprecation-Header |
| MODIFY | `backend/api/deps.py` | get_tenant_context + get_case_context Dependencies |
| CREATE | `tests/backend/test_tenant_routes.py` | Neue Routen-Tests |

### Phase 4 — Frontend-Umbau

| Aktion | Datei | Änderung |
|--------|-------|----------|
| CREATE | `frontend/src/components/TagManager.svelte` | Tag-Editor |
| CREATE | `frontend/src/components/TagBadge.svelte` | Tag-Badge-Component |
| CREATE | `frontend/src/components/TagSelector.svelte` | Multi-Select Tag-Auswahl |
| CREATE | `frontend/src/components/CaseSelector.svelte` | Case-Auswahl (ersetzt ProjectSelector) |
| MODIFY | `frontend/src/views/ProjectsView.svelte` → rename to `CasesView.svelte` |
| MODIFY | `frontend/src/components/Sidebar.svelte` | "Fälle" statt "Projekte" |
| MODIFY | `frontend/src/components/Header.svelte` | Tenant-Anzeige + Wechsel |
| MODIFY | `frontend/src/views/DebateView.svelte` | case_id + tenant_id Parameter |
| MODIFY | `frontend/src/views/DocumentsView.svelte` | case_id + tenant_id Parameter |
| MODIFY | `frontend/src/views/Dashboard.svelte` | case_id + tenant_id Filter |
| MODIFY | `frontend/src/views/ArchiveView.svelte` | case_id + tenant_id Filter |

---

## 8. Reihenfolge & Abhängigkeiten

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
 (Case)      (Membership) (Pfade)      (API)        (Frontend)
                                  ↓
                            Phase 2.5
                            (Migration alter Daten)

Abhängigkeiten:
- Phase 1 benötigt Phase 0 (Membership referenziert Tenant)
- Phase 2 benötigt Phase 0 (CaseStore/Pfade)
- Phase 2 benötigt Phase 1 (tenant_id in get_project_dir)
- Phase 3 benötigt Phase 2 (neue Pfade)
- Phase 4 benötigt Phase 3 (neue API-Routen)

Parallelisierbar:
- Phase 0 (Backend) + Phase 4 Vorbereitung (Frontend-Stores) — parallel
- Phase 1 (Backend) + Phase 4 (Frontend-Stores/TenantSelector) — parallel
- Phase 2 (Backend) — standalone
- Phase 3 (Backend) + Phase 4 Rest (Frontend) — parallel
```

---

## 9. Test-Strategie

### Pro Phase

| Phase | Unit-Tests | Integrationstests | Migrationstests |
|-------|-----------|-------------------|-----------------|
| 0 | CaseStore CRUD, TagStore CRUD | Case-API, Tag-API | — |
| 1 | MembershipStore CRUD | Tenant-Wechsel, JWT | — |
| 2 | get_project_dir tenant_id | DMS/Debate-Pfade korrekt | Alte Projekte → neue Pfade |
| 3 | Dependency-Validierung | Neue vs. alte Routen | Deprecation-Header |
| 4 | — | Frontend-Komponenten | — |

### Kritische Testfälle

1. **Case-Isolation:** gleiche case_id in verschiedenen Tenants → getrennte Daten
2. **Migration:** alte `data/projects/` wird nach Migration nicht mehr gelesen
3. **Tenant-Wechsel:** User wechselt Tenant → neue API-Calls nutzen neuen Tenant
4. **Berechtigung:** User ohne Membership → 403
5. **default-Case:** `_default` Case existiert pro Tenant automatisch
6. **Tags löschen:** Tag gelöscht → aus allen Cases entfernt

---

## 10. Geschätzter Aufwand (aktualisiert)

| Phase | Aufwand | Parallelisierbar? |
|-------|---------|------------------|
| **Phase 0:** Case/Tag-Modelle + Store + API | 1–2 Tage | Ja (Backend) |
| **Phase 1:** Tenant-Mitgliedschaft + Auth | 2–3 Tage | Teilweise mit Phase 0 |
| **Phase 2:** Pfad-Umstellung + Migration | 2–3 Tage | Nein (baut auf Phase 0+1 auf) |
| **Phase 3:** API-Routen umstellen | 1–2 Tage | Ja mit Phase 4 |
| **Phase 4:** Frontend-Umbau | 2–4 Tage | Ja mit Phase 3 |
| **Tests (phasenweise)** | 1–2 Tage | In jeder Phase enthalten |
| **Summe** | **9–16 Tage** | |

**Quick-Wins (vor Phase 0):**
- `include_document_analysis: bool = False` ✅ committed
- Projekt-Auswahl-UI vereinfachen (zwei konkurrierende Selektoren)
- `data/projects/` bereits heute als `tenants/default/cases/{id}/` interpretieren
