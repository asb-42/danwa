# Tenant-Dropdown Workaround — temporärer Konsistenz-Fix

**Datum:** 2026-06-16
**Status:** 🔧 Temporärer Workaround (MUSS zurückgebaut werden)
**Betroffener Code:** [`frontend/src/components/TenantSelector.svelte`](../../frontend/src/components/TenantSelector.svelte)
**Zugehöriger Plan-Kontext:** Danwa wird aufgeteilt in Endbenutzer-Frontend, Danwa-Core (FastAPI, kein UI) und Danwa-Studio (Admin/Builder/Developer).

---

## Problem

Im aktuellen Monolithen zeigte der Tenant-Dropdown im Header (`TenantSelector.svelte`)
eine **andere** Tenant-Liste als das Panel **Inhabit → Tenant Settings**:

- **Header-Dropdown** rief `GET /api/v1/auth/my-tenants` auf — lieferte nur Tenants,
  für die der aktuelle User eine Membership-Zeile besaß.
- **Tenant Settings** rief `GET /api/v1/tenants/` auf — lieferte alle Tenants
  systemweit (admin-only).

Für den synthetischen "Dev User" bedeutete das: in Tenant Settings waren vier
Tenants sichtbar, im Header-Dropdown nur "aktiv + der eine, in den zuletzt
gewechselt wurde" (weil jeder Wechsel eine Membership-Zeile erzeugte, die
übrigen Tenants aber nie besucht wurden).

→ Inkonsistente UX, gleiche Daten sollten in beiden Stellen sichtbar sein.

---

## Lösung (Workaround)

[`TenantSelector.svelte`](../../frontend/src/components/TenantSelector.svelte)
zieht jetzt primär `listAllTenants()` (admin-only, systemweit) und fällt
transparent auf `getMyTenants()` zurück, wenn der Aufruf fehlschlägt
(Nicht-Admin in Produktion, 403, Netzwerkfehler).

```text
loadTenants() {
  try {
    tenants = await listAllTenants();      // bevorzugt (admin/systemweit)
    tenants = tenants.map(t => ({ tenant_id: t.id, tenant_name: t.name, ...t }));
  } catch {
    tenants = await getMyTenants();        // Fallback (Endbenutzer-kompatibel)
  }
}
```

Damit ist der Dropdown im Monolithen identisch zu Tenant Settings, aber in
einem künftigen Endbenutzer-Frontend weiterhin funktional (über den Fallback).

---

## Warum das **nur** ein Workaround ist

Sobald Danwa in die drei Ziel-Produkte zerfällt:

1. **Endbenutzer-Frontend** — kein Admin-Feature, normale User haben keine
   `admin`-Rolle → `listAllTenants()` würde 403 zurückgeben. Der Fallback
   auf `getMyTenants()` ist dann der **einzig korrekte** Pfad.
2. **Danwa-Core** (FastAPI, kein UI) — bleibt unverändert, beide Endpoints
   existieren weiter (`/auth/my-tenants` membership-gefiltert,
   `/tenants/` admin-only).
3. **Danwa-Studio** (Admin/Builder/Developer) — bekommt eine *eigene*
   Tenant-Auswahl, die systemweit sein darf und **nicht** der
   User-Sichtbarkeit unterliegt. Der dortige Selektor sollte wiederum
   `listAllTenants()` direkt benutzen, ohne Workaround.

Im Monolithen ist die Unterscheidung verschwommen: dieselbe UI-Komponente
muss heute beide Welten bedienen. Das ist die Inkonsistenz, die der
Workaround kaschiert.

---

## Rückbau-Plan

Wenn Danwa-Core und Danwa-Studio produktiv sind:

1. **Endbenutzer-Frontend**: In [`TenantSelector.svelte`](../../frontend/src/components/TenantSelector.svelte)
   den `try { listAllTenants() } catch { getMyTenants() }`-Block entfernen
   und nur noch `getMyTenants()` benutzen.
2. **Danwa-Studio**: Eigene Tenant-Auswahl-Komponente bauen, die direkt
   `listAllTenants()` aufruft (kein Fallback nötig, weil der User dort
   per Definition Admin-Rechte hat).
3. **Code-Kommentar** in `TenantSelector.svelte` (siehe JSDoc über
   `loadTenants`) entfernen.
4. Diese Plan-Datei löschen.

---

## Verifikation (Monolith, vor Rückbau)

- Header-Dropdown zeigt alle Tenants (sollte mit Tenant Settings übereinstimmen).
- Bei Nicht-Admin in Produktion (theoretischer Fall im Monolithen) fällt
  der Code sauber auf `getMyTenants()` zurück — keine 403-Toast im UI.
- Wechsel zwischen Tenants funktioniert weiterhin über `selectTenant()`.

---

## Siehe auch

- [`frontend/src/components/TenantSelector.svelte`](../../frontend/src/components/TenantSelector.svelte) — der geänderte Code
- [`frontend/src/views/TenantSettingsView.svelte`](../../frontend/src/views/TenantSettingsView.svelte) — Referenzimplementierung, die `listAllTenants()` benutzt
- [`backend/api/routers/auth.py`](../../backend/api/routers/auth.py) (Zeile 289 ff.) — `/auth/my-tenants` mit Dev-Mode-Bypass
- [`backend/api/routers/tenants.py`](../../backend/api/routers/tenants.py) (Zeile 19 ff.) — `/tenants/` (admin-only)
- `plans/2026-06-15_danwa-studio.md` — übergeordneter Plan für den Core/Studio-Split
