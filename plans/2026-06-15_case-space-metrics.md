# Case-Space Metriken — Definitionen und Auswertungs-Skizzen

> Gehört zu: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md) §6.3 + Erfolgskriterien §16
> Phase: 6.3 (Phase 6 — Aufräumen)
> Status: Doku-Skelett; konkrete Dashboard-Komponente ist Phase 7+ Polish
> Sprache: Deutsch

Dieses Dokument definiert die Metriken, mit denen der Erfolg der
Case-Space-Einführung gemessen wird.  Die Roh-Events werden in
[Commit `3d49d1d`](../../frontend/src/views/) in [`feedbackStore.logActivity()`](../../frontend/src/lib/stores/feedback.svelte.js:75) emittiert (Phase 6.2).  Dieses Dokument
beschreibt, wie daraus die im Plan genannten KPIs abgeleitet werden.

---

## 1. Roh-Events (Phase 6.2)

Alle Events tragen `type='case-space'`, der `source` identifiziert die
Aktion und `details` enthält strukturierte Payload.  Quelle:
[`frontend/src/views/WorkspaceView.svelte`](../../frontend/src/views/WorkspaceView.svelte) und
[`frontend/src/views/InboxView.svelte`](../../frontend/src/views/InboxView.svelte).

| Event | Wann | Source | details |
|---|---|---|---|
| `workspace_view` | `WorkspaceView.onMount` | `workspace-view` | `{ hasInitialCaseId: boolean }` |
| `inbox_open` | `InboxView.onMount` | `inbox-view` | `{ tenantId: string|null }` |
| `graph_view` | Graph-Tab in `WorkspaceView` aktiviert | `graph-view` | `{ entityType: 'case' }` |
| `bulk_action_used` | `doMove` / `onTagInput` / `doArchive` | `inbox-bulk` | `{ kind: 'move'\|'tag'\|'archive', count: number, target?: string, tagCount?: number }` |

Zusätzlich existieren Events außerhalb des Case-Space-Scopes (nicht
hier ausgewertet): `workflow`, `llm`, `node`, `gate`, `error`.  Diese
verwenden andere `type`-Werte und sind in `feedbackStore` mit
eigenen Source-Namespaces getrennt.

---

## 2. Abgeleitete Metriken

### 2.1 Inbox-Quote (Plan §16)

**Definition:** Anteil der Arbeitstage, an denen ein*e Nutzer*in
eine leere Inbox hat (`inbox_open` mit `summary.is_all_clear = true`).

**Berechnung:**

```sql
SELECT
  date_trunc('day', timestamp) AS day,
  count(*) FILTER (WHERE source = 'inbox-view') AS opens,
  -- 'all clear' kann nicht aus dem ActivityLog allein abgeleitet
  -- werden; muss aus dem Backend-Response gespeichert werden.
  count(*) FILTER (WHERE source = 'inbox-view' AND details->>'allClear' = 'true') AS clear_opens
FROM activity_log
WHERE type = 'case-space'
GROUP BY 1;
```

**Aktuell:** Backend liefert `is_all_clear` in der Inbox-Response,
aber das wird nicht ins ActivityLog zurückgespielt.  Phase-7-Item:
im `InboxView` nach `load()` einen weiteren
`feedbackStore.logActivity('case-space', 'inbox-view-loaded', '...',
{ allClear: Boolean }, 'info')` emittieren, der den Status erfasst.

**Ziel:** > 80 % der Arbeitstage mit `clear_opens > 0`.

### 2.2 Graph-Akzeptanz (Plan §16)

**Definition:** Anteil der Power-User-Sessions, in denen
`graph_view` mindestens einmal emittiert wurde.

**Aktuell:** `graph_view` wird in `WorkspaceView.svelte` beim
Aktivieren des Graph-Tabs emittiert.  Visit-Count: zähle
`source='graph-view'` im Verhältnis zu `source='workspace-view'`
über einen 30-Tage-Rolling-Window.

**Ziel:** ≥ 20 % der Sessions (Power-User = ≥ 10 `workspace_view`/Tag).

### 2.3 Session-Page-Count (Plan §16 Erfolgskriterium 2)

**Definition:** Mittlere Anzahl distinkter Routes pro Login-Session.

**Aktuell:** `feedbackStore` hat keinen Login-Event.  Phase-7-Item:
in `auth.svelte.js` `setAuth()` einen
`feedbackStore.logActivity('session', 'login', '...')` einhängen
und auf `clearAuth()` einen `logout`-Event.  Page-Count = Anzahl
verschiedener Route-View-Mounts zwischen Login- und Logout-Event.

**Ziel:** ≥ 30 % Reduktion vs. Legacy-UI (vorher ~10 Pages/Session,
Case-Space-Ziel: ≤ 7 Pages/Session).

### 2.4 Bulk-Action-Nutzung (Plan §6.2)

**Definition:** Verhältnis `bulk_action_used`-Events zu `inbox_open`-Events.

**Berechnung:**

```sql
SELECT
  count(*) FILTER (WHERE source = 'inbox-bulk') AS bulk_events,
  count(*) FILTER (WHERE source = 'inbox-view') AS opens,
  count(*) FILTER (WHERE source = 'inbox-bulk')::float
    / nullif(count(*) FILTER (WHERE source = 'inbox-view'), 0) AS ratio
FROM activity_log
WHERE type = 'case-space'
  AND timestamp > now() - interval '30 days';
```

**Erwartung:** Mit wachsender Vertrautheit der Nutzer*innen sollte
der Anteil steigen (Bulk > Single-Item-Aktionen).

### 2.5 Workspace-Akzeptanz

**Definition:** Anteil der Logins, die zu einem `workspace_view`
geführt haben (vs. direkt zu `dashboard` oder `cases`).

**Berechnung:** `count(workspace_view) / count(login)`.

**Ziel:** ≥ 60 % (Case-Space ist Default-UI).

### 2.6 5-Klick-Regel (Plan §16 Erfolgskriterium 1)

**Definition:** Median der Klick-Anzahl vom Login bis zur ersten
Debatte (gemessen anhand einer `first_debate_created`-Sequenz).

**Aktuell:** Nicht messbar — wir tracken keine Klick-Sequenzen.
Phase-7-Item: Click-Tracker mit `feedbackStore.logActivity('click',
'audit', ...)` einhängen und Sessions rekonstruieren.  Vorerst
stichprobenartig manuell prüfen (User-Tests).

**Ziel:** Median ≤ 5 Klicks.

---

## 3. Erfassungs-Strategie (heute)

| Quelle | Wo | Was |
|---|---|---|
| `feedbackStore.activityLog` | In-Memory, Frontend | 500 neueste Events, verloren bei Reload |
| Backend-Audit-Log | DB (`audit.db`) | Persistente Events mit Korrelations-IDs |
| `requestId` | Frontend | SSE-Korrelation für Workflow-Events |

**Aktuell:** `feedbackStore.activityLog` ist flüchtig.  Für die
Phase-6-Retrospektive (6.7) muss der Store entweder:
- (a) bei `logActivity` zusätzlich `POST /api/v1/audit/activity`
  feuern (kostet einen API-Call pro Event), oder
- (b) das ActivityLog wird regelmäßig (z.B. alle 30 s) als Bulk
  ans Backend gesendet.

**Empfehlung Phase 7:** Option (b) — Bulk-Flush alle 30 s in einer
einzigen `POST`-Anfrage, 50 Events pro Batch.

---

## 4. Dashboard-Visualisierung (Phase 7+)

Empfohlene Komponenten:

- **MetricsCard.svelte** — KPI-Kachel (Titel, Wert, Trend-Pfeil)
- **TimeSeriesChart.svelte** — Sparkline mit 30-Tage-Verlauf
- **TopActionsList.svelte** — Top-10 `bulk_action_used` Targets

Layout-Idee:

```
┌─────────────────────────────────────────────────────┐
│ Case-Space Metrics                  [Last 30 days ▾]│
├───────────────┬───────────────┬────────────────────┤
│ Inbox-Quote   │ Graph-Adoption│ Bulk-Action-Rate   │
│   87%  ↗     │   23%   ↗    │   0.42  ↗          │
│ sparkline     │ sparkline     │ sparkline          │
├───────────────┴───────────────┴────────────────────┤
│ Top 5 Bulk-Action-Targets                           │
│  1. case-42  ........  17 events                   │
│  2. case-7   ........  12 events                   │
│  ...                                                │
└─────────────────────────────────────────────────────┘
```

**Reichweite Phase 7:**
- Backend-Endpoint `GET /api/v1/metrics/case-space` aggregiert die
  Daten aus der `audit.db`-Tabelle
- Frontend-Route `/metrics` mit dem Dashboard
- Permission: `admin`-Rolle oder Tenant-Owner

---

## 5. Auswertungs-Skript (manuell, Phase 6.7)

Bis das Dashboard steht, kann die Auswertung manuell erfolgen.
Dazu wird die `audit.db` (oder eine exportierte JSON-Datei) mit
folgendem Python-Snippet analysiert:

```python
import sqlite3, json
from collections import Counter, defaultdict

con = sqlite3.connect("data/audit.db")
events = con.execute(
    "SELECT timestamp, type, source, details FROM activity_log "
    "WHERE type = 'case-space' "
    "ORDER BY timestamp DESC LIMIT 10000"
).fetchall()

opens = sum(1 for _,_,s,_ in events if s == "inbox-view")
graph = sum(1 for _,_,s,_ in events if s == "graph-view")
bulk  = sum(1 for _,_,s,_ in events if s == "inbox-bulk")
bulk_kinds = Counter(json.loads(d or "{}").get("kind","?")
                     for _,_,s,d in events if s == "inbox-bulk")

print(f"Inbox opens (30d): {opens}")
print(f"Graph views (30d): {graph}")
print(f"Bulk events (30d): {bulk}")
print(f"Bulk kinds:        {dict(bulk_kinds)}")
if opens:
    print(f"Bulk-per-open:     {bulk/opens:.2f}")
```

Dieses Skript wird in [`reports/case-space-metrics-30d.md`](../../reports/)
abgelegt, sobald die erste 30-Tage-Periode vorbei ist (Phase 6.7).

---

## 6. Bekannte Lücken

- **Kein persistenter Speicher** für ActivityLog: Page-Reload löscht
  die Events.  Phase 7 muss einen Bulk-Flush implementieren.
- **Kein Login-/Logout-Event**: Page-Count-Metrik (2.3) kann aktuell
  nicht aus dem Log allein abgeleitet werden.
- **Kein Klick-Tracker**: 5-Klick-Regel (2.6) erfordert
  Click-Event-Erfassung; aktuell nur View-Mount-Events.
- **Kein A/B-Testing**: Welcome-Card-Akzeptanz (Plan-Risiko-Tabelle)
  kann nicht gemessen werden, weil es keine Kontrollgruppe gibt.

Diese Lücken sind explizit als Phase-7+ Folge-Items vermerkt.
