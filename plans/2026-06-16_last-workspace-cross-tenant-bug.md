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
