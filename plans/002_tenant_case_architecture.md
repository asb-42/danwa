# Tenant-fähige Case-Architektur mit Tags

## 1. Status Quo — Probleme

| Problem | Beschreibung |
|---------|-------------|
| **Keine Tenant-Isolation in Pfaden** | `data/projects/<id>/` ist global. Tenant-ID existiert im Modell, aber nicht im Dateisystem. |
| **Projekt = flache Gruppierung** | Projekte dienen als thematische Ordner, teilen sich aber DMS/Debatten-Speicher. Folge: `analysis.json`-Spillover zwischen Fällen im selben Projekt. |
| **Keine mandantenübergreifende Trennung** | User können (zumindest konzeptionell) jedes Projekt sehen, weil Projekt-Pfade nicht nach Tenant partitioniert sind. |
| **Keine Tags** | Thematische Gliederung erfolgt nur über Projekt-Zugehörigkeit. Ein Dokument/Case kann nur in genau einem Projekt sein. |

---

## 2. Ziel-Architektur

```
data/
├── tenants/
│   └── {tenant_id}/
│       ├── users.json          (Mitglieder + Rollen des Tenants)
│       ├── cases/
│       │   ├── {case_id}/
│       │   │   ├── case.json   (Metadata: Titel, Beschreibung, Status, Tags[])
│       │   │   ├── debates/
│       │   │   │   └── {debate_id}.json
│       │   │   └── dms/
│       │   │       ├── dms.db
│       │   │       ├── chroma_db/
│       │   │       └── documents/
│       │   └── ...
│       └── tags.json           (Pro Tenant: verfügbare Tags + Hierarchie)
│
├── tenants.db                  (SQLite: tenants, users, memberships)
└── auth.db                     (SQLite: accounts, credentials)
```

### Kernkonzepte

| Begriff | Alte Welt | Neue Welt |
|---------|-----------|-----------|
| **Tenant** | `"_default"`-Konstante | Explizite Organisation / Mandant mit eigenem Storage-Pfad |
| **Case** | "Projekt" | Ein abgeschlossener Fall/Vorgang mit eigenem DMS + Debatten |
| **Tag** | — | Schlüsselwörter zur fallübergreifenden thematischen Gruppierung |
| **User** | Systemweit | An Tenant gebunden; Mitgliedschaft + Rolle pro Tenant |
| **Debatte** | Liegt unter `data/projects/<id>/debates/` | Liegt unter `data/tenants/<tid>/cases/<cid>/debates/` |
| **DMS/Dokumente** | Liegt unter `data/projects/<id>/dms/` | Liegt unter `data/tenants/<tid>/cases/<cid>/dms/` |

---

## 3. Änderungen im Einzelnen

### 3.1 Tenant-Storage (`Persistence`-Layer)

**Aktuell:** `ProjectStore.get_project_dir(project_id)` → `data/projects/{project_id}/`

**Neu:** `CaseStore.get_case_dir(tenant_id, case_id)` → `data/tenants/{tenant_id}/cases/{case_id}/`

**Neue/Geänderte Stores:**

| Store | Beschreibung |
|-------|-------------|
| `TenantStore` (existiert) | Erweitern: `get_tenant_dir(tenant_id)` → `data/tenants/{tid}/` |
| `CaseStore` (neu) | Ersetzt `ProjectStore` für Fall-Speicher. Pfad: `tenants/{tid}/cases/{cid}/` |
| `TagStore` (neu) | Pro Tenant: CRUD für Tags in `tenants/{tid}/tags.json` |
| `MembershipStore` (neu) | User-zu-Tenant-Zuordnung + Rollen (admin/member/viewer). Alternativ in `TenantStore`. |

**ProjectStore** bleibt als Alias/Kompatibilitätsschicht bestehen für Migration:
```python
def get_project_dir(self, tenant_id, project_id):
    return Path("data/tenants") / tenant_id / "cases" / project_id
```

### 3.2 Case-Modell (ersetzt Project-Modell)

```python
class Case(BaseModel):
    id: str
    tenant_id: str
    title: str
    description: str = ""
    status: str = "active"       # active | archived | closed
    tags: list[str] = []         # Referenzen auf Tag-IDs des Tenants
    created_by: str              # user_id
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}          # Erweiterbare Felder
```

**Storage:** `tenants/{tid}/cases/{cid}/case.json`

### 3.3 Tag-Modell (neu)

```python
class Tag(BaseModel):
    id: str
    tenant_id: str
    name: str                    # Anzeigename
    color: str = "#6366f1"       # Für UI-Badge
    parent_id: str | None = None # Hierarchische Tags
    created_at: datetime
```

**Storage:** `tenants/{tid}/tags.json`

**Tags sind tenant-global**, nicht case-global. Ein Tag kann beliebig vielen Cases zugeordnet werden.

### 3.4 Tenant-Mitgliedschaft (neu/existiert)

**Aktuell:** `User.tenant_id` ist ein Single-Value-Feld (User gehört zu genau einem Tenant).

**Neu:** User kann Mitglied mehrerer Tenants sein:

```python
class TenantMembership(BaseModel):
    tenant_id: str
    user_id: str
    role: str = "member"         # admin | member | viewer
    invited_by: str | None = None
    joined_at: datetime
```

**Storage:** In `tenants.db` oder in `tenants/{tid}/users.json`

**Auth-Modifikation:** Nach Login wählt der User einen aktiven Tenant (analog Projekt-Wechsel heute). Der `X-Tenant-Id`-Header ersetzt/ergänzt `X-Project-Id` in API-Calls.

### 3.5 API-Änderungen

#### Neue Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| GET | `/api/v1/tenants` | Meine Tenants auflisten |
| GET | `/api/v1/tenants/{id}/cases` | Cases im aktiven Tenant |
| POST | `/api/v1/tenants/{id}/cases` | Case anlegen |
| GET | `/api/v1/tenants/{id}/cases/{cid}` | Case-Details |
| PATCH | `/api/v1/tenants/{id}/cases/{cid}` | Case updaten (auch Tags) |
| DELETE | `/api/v1/tenants/{id}/cases/{cid}` | Case archivieren |
| GET | `/api/v1/tenants/{id}/tags` | Tags des Tenants |
| POST | `/api/v1/tenants/{id}/tags` | Tag anlegen |
| PUT | `/api/v1/tenants/{id}/tags/{tagId}` | Tag umbenennen |
| DELETE | `/api/v1/tenants/{id}/tags/{tagId}` | Tag löschen |

#### Geänderte Endpunkte

| Alter Pfad | Neuer Pfad | Änderung |
|-----------|-----------|---------|
| `/api/v1/debate/*` | `/api/v1/tenants/{tid}/cases/{cid}/debates/*` | Tenant + Case im Pfad |
| `/api/v1/workflow-exec/*` | `/api/v1/tenants/{tid}/cases/{cid}/workflows/*` | Tenant + Case im Pfad |
| `/api/v1/dms/*` | `/api/v1/tenants/{tid}/cases/{cid}/dms/*` | Tenant + Case im Pfad |

**Alternativ:** Tenant und Case als Header (`X-Tenant-Id`, `X-Case-Id`) statt im URL-Pfad — weniger Breaking Changes, aber unsichtbarer.

#### Authentifizierung

Neue Dependencies:
```python
def get_current_tenant(user = Depends(get_current_user), tenant_id: str = Header(...)):
    membership = membership_store.get(user.id, tenant_id)
    if not membership:
        raise HTTPException(403)
    return tenant_id

def get_current_case(tenant_id = Depends(get_current_tenant), case_id: str = Header(...)):
    case = case_store.get(tenant_id, case_id)
    if not case:
        raise HTTPException(404)
    return case
```

### 3.6 Frontend-Änderungen

#### Tenant-Auswahl
- Nach Login: Tenant-Auswahl-Seite (falls User in mehreren Tenants)
- Aktiven Tenant im Header/Seitenleiste anzeigen
- `X-Tenant-Id` in allen API-Requests mitschicken

#### Case- statt Projekt-Navigation
- Sidebar: "Fälle" statt "Projekte"
- Case-Liste mit Tag-Filtern
- Case-Detail-Ansicht mit Tag-Editor

#### Tag-Management
- Tag-Editor im Tenant-Settings
- Tag-Auswahl (Multi-Select) bei Case-Erstellung und -Bearbeitung
- Tags als Badges/Filter in Case-Liste und Debatten-Übersicht

#### Alte UI (>90% unverändert)
- Debattenerstellung / DebateView / BlueprintCanvas: bekommen `tenant_id` + `case_id` als zusätzliche Parameter
- RAG-Dialog: Tag-basierte Dokumentenauswahl zusätzlich zur Case-Auswahl

### 3.7 Migration

#### Phase 1 — Pfad-Umstellung (ohne Datenverlust)
1. `ProjectStore` so ändern, dass er `tenants/{tid}/cases/{cid}/` nutzt, aber existierende `data/projects/` noch als Fallback liest
2. `tenant_id`-Backfill in auth.db + project.json ist bereits durch v001_migration passiert
3. Für jedes existierende Projekt: Symlink oder Move von `data/projects/{id}` → `data/tenants/{tid}/cases/{id}`
4. Alte Pfade als Deprecation-Warning loggen

#### Phase 2 — Tags einführen
5. `TagStore` + API-Endpunkte bauen
6. `tags`-Feld an Case-Model anhängen
7. UI für Tag-Verwaltung bauen
8. Bestehende Projekte ohne Tags initialisieren

#### Phase 3 — Tenant-Mitgliedschaft
9. `MembershipStore` bauen
10. Bestehende User in `_default`-Tenant als admin eintragen
11. Tenant-Wechsel-UI
12. `X-Tenant-Id`-Dependency in allen Routern

#### Phase 4 — Alte Endpunkte deprecated
13. Alte `/api/v1/projects/*`-Endpunkte als Deprecation markieren
14. Alte `data/projects/`-Pfade nicht mehr lesen

---

## 4. Offene Fragen

| Frage | Optionen |
|-------|----------|
| **Tenant im Pfad vs. Header?** | **Empfehlung:** Tenant + Case im Pfad (`/tenants/{tid}/cases/{cid}/...`), weil es selbst-dokumentierend ist und Caching/Logging vereinfacht. |
| **Tags hierarchisch oder flach?** | Flach für MVP, parent_id für spätere Hierarchie vorsehen. |
| **Tags tenant-global oder user-global?** | **Tenant-global** — Team-Arbeit erfordert gemeinsames Tag-Schema. |
| **Ein User in mehreren Tenants?** | Ja — Mitgliedschafts-Modell. Aktiver Tenant wird pro Session gewählt. |
| **Was passiert mit `default`-Projekt?** | Existiert pro Tenant als `cases/_default` weiter für Rückwärtskompatibilität. |
| **Dokumente zwischen Cases teilen?** | Nein — DMS ist pro Case isoliert. Teilen nur über Tags (gleiches Dokument in mehreren Cases hochladen oder Copy-on-Write). |

---

## 5. Estimated Effort

| Bereich | Aufwand | Parallelisierbar? |
|---------|---------|------------------|
| CaseStore + Pfad-Umstellung | 2–3 Tage | Ja (Backend) |
| TagStore + API | 1–2 Tage | Ja (Backend) |
| Tenant-Mitgliedschaft + Auth | 2–3 Tage | Nein (baut auf CaseStore auf) |
| Frontend: Case-Navigation | 2–3 Tage | Ja (Frontend) |
| Frontend: Tag-UI | 1–2 Tage | Ja (Frontend) |
| Frontend: Tenant-Wechsel | 1–2 Tage | Nein (baut auf Auth-API auf) |
| Migration alter Projekte | 1 Tag | Nein (muss getestet werden) |
| Deprecation alter Pfade | 0.5 Tage | Am Ende |

**Gesamt:** ca. 10–15 Tage für komplette Umstellung.

---

## 6. Kurzfristige Quick-Wins (vor der großen Umstellung)

- `include_document_analysis: bool = False` ✅ ist bereits committed
- Projekt-Auswahl-UI vereinfachen (aktuell gibt es zwei konkurrierende Projekt-Selektoren: `ProjectSelector.svelte` und `activeProject`-Store)
- `data/projects/`-Pfad bereits heute als `tenants/default/cases/{id}/` interpretieren (nur Pfad-Logik umstellen, API intakt lassen)
