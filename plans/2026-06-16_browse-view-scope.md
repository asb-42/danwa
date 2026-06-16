# BrowseView — Scope-Korrektur und Studio-Migration

**Datum:** 2026-06-16
**Status:** 📝 Dokumentation + kosmetische Korrektur; Architektur-Plan für Studio
**Betroffener Code:**
- [`frontend/src/views/BrowseView.svelte`](../../frontend/src/views/BrowseView.svelte)
- [`frontend/src/lib/i18n/loaders/en.js`](../../frontend/src/lib/i18n/loaders/en.js) (neue `caseSpace.browse.*`-Keys)
- Backend-Route: `GET /api/v1/graph/global` ([`backend/api/routers/graph.py`](../../backend/api/routers/graph.py:293))

---

## Befund

Die **Browse**-View (Phase 4.9) wurde im Case-Space-Workspace-Plan als
*"Cross-tenant view of all your cases, debates, documents and tags"*
beworben — diese Beschreibung ist **falsch**. Tatsächlich ist die View
**tenant-scoped**:

- [`BrowseView.svelte:28`](../../frontend/src/views/BrowseView.svelte:28) liest
  `$currentTenant?.id` als Pflichtparameter.
- Der einzige API-Call geht an
  `GET /api/v1/graph/global?tenant_id=…&limit=…` ([`graph.py:293`](../../backend/api/routers/graph.py:293)).
- Die Backend-Route nimmt `tenant_id` als **Pflichtparameter** und
  filtert strikt auf diesen Tenant ([`_build_global_subgraph`](../../backend/api/routers/graph.py)).

Der Name "global" bezieht sich auf "global **innerhalb** des Tenants",
nicht auf "global über alle Tenants hinweg".

### Was die View **kann**
- Liest `/api/v1/graph/global` für den aktiven Tenant.
- Rendert die Knoten gruppiert nach Typ (case, debate, document, tag, user, audit, other).
- Click-to-Drill für `case` → Workspace und `debate` → Debate-View.
- Tab-Switch List / Graph (List = selbst gerendert, Graph = Cytoscape-Spike via Dynamic-Import).
- Detail-Drawer für andere Knotentypen (read-only).

### Was die View **nicht** kann
- Keine mandantenübergreifende Aggregation.
- Keine Schreiboperationen.
- Keine Filter über Typen hinaus (`limit` ist der einzige Parameter).
- Keine Aktionen für Tag/Document/Audit/User-Knoten.

---

## Sofortmaßnahme (durchgeführt)

1. **Inline-Subtitle-Fallback in [`BrowseView.svelte:115`](../../frontend/src/views/BrowseView.svelte:115) angepasst**:
   - alt: *"Cross-tenant view of all your cases, debates, documents and tags."*
   - neu: *"All cases, debates, documents and tags in this tenant."*
2. **i18n-Keys `caseSpace.browse.*` in [`en.js`](../../frontend/src/lib/i18n/loaders/en.js) ergänzt** — die View griff bisher auf Inline-Fallbacks zurück, jetzt sind die Strings im Katalog, damit Übersetzer / zukünftige Sprach-Loader sie finden.
3. **Code-Kommentar in `en.js`** dokumentiert, dass die "cross-tenant"-Bezeichnung Legacy ist und das echte Cross-Tenant-Feature ein geplantes Studio-Feature ist.

---

## Architekturplan: Cross-Tenant-Browse gehört in Danwa-Studio

### Warum
Im Monolithen ist die Inkosistenz harmlos — der User wechselt den Tenant
und bekommt "seinen" Browse. Aber die Bezeichnung ist irreführend, und im
aufgespaltenen Setup wird das deutlicher:

| Frontend | Was "Browse" zeigen sollte |
|---|---|
| **Endbenutzer-Frontend** | Tenant-interner Aggregator. Subtitle korrekt ("in this tenant"). Kein System-Admin-Zugriff. |
| **Danwa-Studio** | Echte cross-tenant Aggregation: "Alle Tenants, alle Cases, alle Debates, alle Tags, alle Audits" — für System-Administratoren, Builder, Developer. |

### Konkret für Danwa-Studio
1. **Neue Backend-Route**: `GET /api/v1/studio/graph/cross-tenant` (oder
   ähnlich) — aggregiert über alle Tenants, Admin-only. Pagination + Filter
   wie der bestehende `/graph/global`, aber **ohne** `tenant_id`-Parameter.
2. **Neue Frontend-Komponente** in Danwa-Studio, die diese Route nutzt
   (z. B. `StudioBrowseView.svelte` oder ein Tab im
   `InspectorGraphTab`-Pendant für Studio). Cytoscape-Renderer kann direkt
   übernommen werden.
3. **Move, don't copy**: Die aktuelle BrowseView im Endbenutzer-Frontend
   bleibt erhalten, zeigt aber korrekt "in this tenant". Die Studio-Variante
   ist eine **eigene** Komponente — kein Workaround, kein Conditional
   Rendering.

### Was im Monolithen bleibt
- Aktueller Workaround reicht aus: der irreführende Subtitle ist weg, der
  Code macht genau das, was er sagt. Beim Core/Studio-Split wird die
  Studio-Variante *zusätzlich* gebaut, nicht als Modifikation der
  bestehenden View.

---

## Verifikation

Im Monolithen, mit aktivem Tenant und Daten:
- Browse-Subtitle liest sich jetzt korrekt: "All cases, debates, documents
  and tags in this tenant."
- Tenant-Wechsel → Browse lädt Daten des neuen Tenants (unverändertes
  Verhalten, nur Text angepasst).
- `/api/v1/graph/global?tenant_id=…` antwortet weiterhin mit genau den
  Knoten/Kanten dieses Tenants (Backend-Logik unverändert).

---

## Siehe auch

- [`frontend/src/views/BrowseView.svelte`](../../frontend/src/views/BrowseView.svelte) — korrigierte View
- [`frontend/src/lib/api/graph.js`](../../frontend/src/lib/api/graph.js) — `getGlobalGraph()`-Wrapper
- [`backend/api/routers/graph.py`](../../backend/api/routers/graph.py) — `/graph/global` (tenant-scoped)
- [`plans/2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md) — Phase 4.9 Ursprung
- [`plans/2026-06-15_danwa-studio.md`](2026-06-15_danwa-studio.md) — übergeordneter Studio-Plan
- [`plans/2026-06-16_tenant-dropdown-workaround.md`](2026-06-16_tenant-dropdown-workaround.md) — verwandter Admin/Membership-Workaround
