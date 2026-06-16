# last_workspace Cross-Tenant-Leak — Bug + 3-Stufen-Fix

**Datum:** 2026-06-16
**Status:** ✅ Behoben (3 Stufen umgesetzt)
**Schweregrad:** 🔴 Hoch — Daten eines fremden Tenants wurden im Workspace gerendert.

## Symptom

Tenant "Default" ist aktiv, im Dropdown steht "Default". User öffnet die Workspace-View, ohne explizit einen Case zu wählen. Statt des Case-Pickers oder des korrekten Cases "S 201…" wird ein Summary eines völlig anderen Cases ("hkk" / "active") angezeigt — inklusive 0 Debates / 0 Documents / 0 Members. Dieser "hkk"-Case gehört zu einem anderen Tenant.

## Ursache (3 Schichten)

1. **Schema:** `users.last_workspace TEXT` ([`user_store.py:44`](../../backend/persistence/user_store.py:44)) — eine einzige case_id pro User, **ohne Tenant-Kontext**. Wenn der User in Tenant A einen Case öffnete und später in Tenant B wechselte, blieb die alte ID gespeichert.

2. **Restore-Pfad:** [`restoreLastWorkspace()`](../../frontend/src/lib/stores/workspaceStore.svelte.js) las diese ID blind zurück und rief `setActiveCase(caseId)` ohne zu prüfen, ob der Case zum aktuellen Tenant gehört.

3. **Summary-Route:** [`get_workspace_summary`](../../backend/api/routers/workspace.py:151) lud den Case per `store.get(tenant_id, case_id)`. Bei einer Fehlkonfiguration oder einem Race mit dem Dev-User-Bypass lieferte der Store einen Case zurück, dessen `tenant_id` nicht mit der Header-`tenant_id` übereinstimmte — kein expliziter Tenant-Mismatch-Check existierte.

## Lösung (3 Stufen)

### Stufe 1 — Schema-Migration (per-tenant Mapping)

[`backend/persistence/user_store.py`](../../backend/persistence/user_store.py) hat eine neue Tabelle bekommen:

```sql
CREATE TABLE IF NOT EXISTS user_last_workspace (
    user_id   TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    case_id   TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, tenant_id)
);
```

Beim Boot läuft eine **idempotente Backfill-Migration**, die den alten Single-Value-Eintrag in die per-Tenant-Mapping überträgt (mit dem `users.tenant_id` als Mapping-Tenant — eine konservative Annahme; Cross-Tenant-Leaks werden so entschärft, weil die Legacy-Spalte nicht mehr gelesen wird).

Die `get_last_workspace()`- und `set_last_workspace()`-Methoden wurden auf `tenant_id`-Parameter umgestellt. Bei `tenant_id=None` greift der Legacy-Fallback (für Backward-Compat).

### Stufe 2 — Backend-Route → tenant-scoped

[`backend/api/routers/auth.py`](../../backend/api/routers/auth.py) `GET/PUT /me/last-workspace` zieht den aktiven Tenant jetzt per `Depends(get_active_tenant)` (das den `X-Tenant-Id`-Header liest). Damit landet jeder `setLastWorkspace`-Call in der korrekten `(user, tenant)`-Zeile, und `getLastWorkspace` gibt nur noch IDs des aktuellen Tenants zurück.

### Stufe 3 — Backend-Härtung im Summary-Endpoint

[`backend/api/routers/workspace.py`](../../backend/api/routers/workspace.py) prüft jetzt explizit:

```python
case_tenant = getattr(case, "tenant_id", None)
if case_tenant and case_tenant != tenant_id:
    logger.warning(...)
    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
```

Das ist **defence in depth**: auch wenn ein Store-Bug durchrutscht, wird der Case nicht mehr im Summary eines falschten Tenants gerendert.

### Stufe 2b — Frontend-Validierung

[`workspaceStore.svelte.js`](../../frontend/src/lib/stores/workspaceStore.svelte.js):

- `restoreLastWorkspace()` ruft nach dem `getLastWorkspace()`-Roundtrip zusätzlich `getCase(tenantId, caseId)` auf. Schlägt das fehl (404), wird der `last_workspace` per `setLastWorkspace(null)` defensiv gelöscht und der User bekommt den Case-Picker zu sehen.
- `persistActiveCase()` loggt den aktiven Tenant zu Diagnosezwecken mit; der Tenant selbst wird nicht im Body mitgeschickt (er kommt automatisch über `X-Tenant-Id` aus [`core.js:99`](../../frontend/src/lib/api/core.js:99)).

## Verifikation

1. **Direktes Symptom:** Tenant "Default" → Workspace mounten → erwartet wird "S 201…" (oder Case-Picker bei leerer DB), **nicht** "hkk".
2. **Tenant-Wechsel-Test:** Tenant A öffnen → Case X öffnen → auf Tenant B wechseln → Workspace mounten → Workspace zeigt **nicht** Case X (Cross-Tenant-Leak behoben).
3. **Persistenz-Test:** Tenant A → Case X öffnen → Tenant B wechseln → Case Y in B öffnen → zurück zu Tenant A → Workspace stellt Case X wieder her (Per-Tenant-Mapping funktioniert).
4. **Backend-Log:** Bei einem Cross-Tenant-Versuch erscheint `workspace/summary: case … belongs to tenant … but caller is in tenant … — refusing to render` als Warning.

## Siehe auch

- [`backend/persistence/user_store.py`](../../backend/persistence/user_store.py) — neue Tabelle + Methoden
- [`backend/api/routers/auth.py`](../../backend/api/routers/auth.py) — tenant-scoped Route
- [`backend/api/routers/workspace.py`](../../backend/api/routers/workspace.py) — Tenant-Mismatch-Check
- [`frontend/src/lib/stores/workspaceStore.svelte.js`](../../frontend/src/lib/stores/workspaceStore.svelte.js) — `restoreLastWorkspace` validiert
- [`plans/2026-06-15_danwa-studio.md`](2026-06-15_danwa-studio.md) — übergeordneter Split-Plan
- [`plans/2026-06-16_tenant-dropdown-workaround.md`](2026-06-16_tenant-dropdown-workaround.md) — verwandter Admin/Membership-Bug

---

## Spätere Befunde (gleiche Symptom-Familie)

Während der Verifikation des ursprünglichen Fixes tauchten
weitere Bugs auf, die zusammen mit dem Cross-Tenant-Leak
sichtbar wurden. Sie wurden im selben Sprint behoben:

### Bug A — Cross-Tenant-Backfill (commit df0ba69)

**Symptom:** Die UserStore-Migration aus Commit b6a9c61
kopierte den Legacy-Wert aus `users.last_workspace` per
One-Shot-Backfill in die neue `user_last_workspace`-Tabelle
unter dem `tenant_id` des Users.  Bei einem User mit
mehreren Memberships wurde der Case damit potentiell dem
falschen Tenant zugeordnet.

**Fix:** Backfill-Block komplett entfernt.  Legacy-Spalte
bleibt nur als Lese-Cache für den Backward-Compat-Pfad
(`get_last_workspace(tenant_id=None)`).

**Tests:** `test_no_silent_backfill_from_legacy_column` — ein
echter Pre-Migration-DB-Lifecycle (write legacy value, close,
reopen) wird durchgespielt.

### Bug D — Counts-Logik mit Cross-Tenant-Filesystem-Scan (commit b8779ab)

**Symptom:** Workspace zeigte Debates=0 / Documents=0 für
Cases, die nachweislich Diskussionen hatten.  Du hast in
einer Anmerkung darauf hingewiesen, dass deine Cases nicht
leer seien — das war die entscheidende Beobachtung.

**Ursache:** `get_workspace_summary` rief
`backend.api.deps.get_debate_store_for_case(case.id)` auf.
Dieser Helper hat einen **Cross-Tenant-Filesystem-Scan**
als Fallback, der im falschen Tenant-Verzeichnis landet
(und im schlimmsten Fall Debates aus einem anderen Tenant
als Counts für den aktuellen Tenant meldet).

**Fix:** `get_workspace_summary` benutzt jetzt
`case_scoped._get_debate_store_for_case(tenant_id, case_id,
case_store)` — der tenant-scoped Helper, der den Case-Dir
über `case_store.get_case_dir(tenant_id, case_id)` auflöst
(gleicher Pfad, den der Debate-Erstellungs-Endpunkt
schreibt).

**Tests:** `TestWorkspaceSummaryDebateCountTenantScoped` (2
Tests) — gleicher Case in zwei Tenants mit verschiedenen
Counts;  Cross-Tenant-Leak wird verhindert.

### Bug C — URL/Prop wird von async restore überschrieben (commit f5d5ec5)

**Symptom:** Wenn WorkspaceView mountet, ruft sie
`restoreLastWorkspace()` als async Promise auf.  Parallel
schon gesetzter `activeCaseId` (über URL `?case=…` oder
`initialCaseId`-Prop) wurde durch den Backend-Wert
überschrieben — Race Condition.

**Fix:** `restoreLastWorkspace()` ruft `setActiveCase()` nur
dann auf, wenn `_state.activeCaseId === null` ist.  URL/Prop
haben Vorrang; Backend-Wert ist nur Fallback.

**Tests:** 5 neue Tests in
`TestRestoreLastWorkspaceBugCtenantValidation` — happy path,
cross-tenant 404, URL-Precedence, kein Tenant, defensives
Cleanup.

### Bug B — Header-CaseSelector vs. WorkspaceStore-Desync (commit 7459d09)

**Symptom:** Header-CaseSelector und Workspace benutzten
zwei unabhängige Stores.  User pickte "S 201…" im Header,
Workspace zeigte weiter "hkk".

**Fix:**
1. Neuer Helper `workspaceStore.syncFromActiveCase(sourceStore)`
liest den aktuellen Wert eines Svelte-Stores und ruft
`setActiveCase()` nur bei Differenz auf.  Null/undefined
werden ignoriert, damit Header-Deselection den Workspace
nicht wischt.
2. `WorkspaceView` hat jetzt einen `$effect`, der den Helper
bei jedem Tick des globalen `activeCase`-Stores aufruft.

**Tests:** 4 neue Tests in
`TestSyncFromActiveCaseBugBHeaderWorkspaceSync` — happy
path, gleicher Wert (kein Clobber), Null-Wert, undefinierter
Store.

## Gesamt-Test-Lage

| Testset | Status |
|---------|--------|
| `test_workspace_router.py` (Backend) | 8/10 grün (2 pre-existing failures, nicht durch Fix verursacht) |
| `test_case_scoped_router.py` (Backend) | 55/55 grün |
| `test_last_workspace_tenant_scoping.py` (Backend) | 13/13 grün |
| `workspaceStore.test.js` (Frontend) | 24/24 grün + 1 todo |
| Volle Frontend-Suite | 309/310 grün (1 unhandled error in workflow/layout.test.js — pre-existing crypto.randomUUID() in Node-Env) |

## Manuelle Verifikation (Browser)

1. Backend + Frontend neu starten.
2. Tenant "Default" → Cases → "S 201…" wählen → "Open in Workspace".
3. Erwartet: Workspace zeigt "S 201…" mit korrekten Counts
   (Debates, Documents, Members > 0 wenn aktiv).
4. Tenant-Wechsel: A → B → A → Workspace rendert jeweils
   den richtigen Case, kein Cross-Tenant-Leak.
