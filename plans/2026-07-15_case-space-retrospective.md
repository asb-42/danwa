# Case-Space 30-Tage-Retrospektive (Template)

> Gehört zu: [`2026-06-14_case-space-workspace.md`](2026-06-14_case-space-workspace.md) §6.7
> Phase: 6.7 (Phase 6 — Aufräumen, **30 Tage nach Roll-out auszufüllen**)
> Geplantes Ausfülldatum: **2026-07-15**
> Sprache: Deutsch
> Status: Template (noch leer)

> Hinweis: Dieses Dokument ist ein Template.  Am 2026-07-15
> sollen die hier definierten Abschnitte mit echten Messwerten
> ausgefüllt werden.  Die Methodik ist im Schwesterdokument
> [`2026-06-15_case-space-metrics.md`](2026-06-15_case-space-metrics.md)
> beschrieben.

---

## 1. Roll-out-Daten

| Datum | Ereignis |
|-------|----------|
| 2026-06-15 | Flags `enable_case_space*` auf `True` als Default |
| 2026-06-15 | Telemetrie-Hooks aktiv (Commit `3d49d1d`) |
| 2026-06-15 | i18n-Keys für Graph-View ergänzt (Commit `d5d4ad7`) |
| 2026-07-15 | **Retrospektive — dieses Dokument** |

**Anzahl Nutzer*innen im 30-Tage-Fenster:** ___
**Anzahl aktiver Tenants:** ___
**Anzahl aktiver Cases:** ___

---

## 2. KPIs aus dem Metrik-Katalog (Phase 6.3)

### 2.1 Inbox-Quote (Ziel: > 80 %)

| Tag | `inbox_open` | `allClear=true` | Quote |
|-----|--------------|------------------|-------|
| Tag 1 | ___ | ___ | ___% |
| Tag 7 | ___ | ___ | ___% |
| Tag 14 | ___ | ___ | ___% |
| Tag 21 | ___ | ___ | ___% |
| Tag 30 | ___ | ___ | ___% |

**Gesamt-Quote (30 Tage):** ____ % — **Ziel erreicht? ☐ ja ☐ nein**

**Notizen / Anomalien:**

> (z.B. "Quote fällt am Wochenende ab — Nutzer*innen arbeiten
> nur an Wochentagen, Inbox bleibt über das Wochenende offen")

### 2.2 Graph-Akzeptanz (Ziel: ≥ 20 % der Power-User-Sessions)

| Power-User-Klasse | Sessions | Mit `graph_view` | Quote |
|--------------------|----------|-------------------|-------|
| ≥ 10 `workspace_view`/Tag | ___ | ___ | ___% |
| ≥ 5 `workspace_view`/Tag | ___ | ___ | ___% |
| alle Sessions | ___ | ___ | ___% |

**Ziel erreicht? ☐ ja ☐ nein**

**Notizen:**

> (z.B. "List-Mode ist überwältigend bevorzugt — Graph wird
> nur von Power-Usern angetastet, die es einmal gesehen haben")

### 2.3 Session-Page-Count (Ziel: ≤ 7 vs. Legacy ~10)

| Methode | Vor Roll-out (Legacy) | Nach Roll-out | Differenz |
|----------|------------------------|---------------|-----------|
| Mittel | ___ | ___ | ___% |
| Median | ___ | ___ | ___% |
| p95 | ___ | ___ | ___% |

**30 % Reduktion erreicht? ☐ ja ☐ nein**

**Caveat:** Aktuell nicht messbar (kein Login-Event in
`feedbackStore`).  Phase 7 muss das ergänzen; bis dahin
gilt diese Metrik als **placeholder**.

### 2.4 Bulk-Action-Nutzung (kein fixiertes Ziel, Trendanzeige)

```
bulk_action_used Events: ___
inbox_open Events:        ___
bulk-per-open Ratio:     ___
```

**Trend (W1 → W4):** ___ → ___ → ___ → ___

### 2.5 Workspace-Akzeptanz (Ziel: ≥ 60 %)

| Metrik | Wert |
|--------|------|
| `workspace_view` Events | ___ |
| davon unique Sessions (Schätzung) | ___ |
| `login`-Events (TODO Phase 7) | ___ |
| **Quote** | ____ % |

### 2.6 5-Klick-Regel (Ziel: Median ≤ 5 Klicks)

> Manuell gemessen (siehe `walkthrough.md` Aufnahme-Checkliste
> für Demo-Tenant).  Stichprobe von 5 Power-Usern.

| Proband | Klicks bis zur ersten Debatte |
|---------|--------------------------------|
| P1 | ___ |
| P2 | ___ |
| P3 | ___ |
| P4 | ___ |
| P5 | ___ |

**Median:** ___  — **Ziel erreicht? ☐ ja ☐ nein**

---

## 3. Qualitatives Feedback

### 3.1 Positive Rückmeldungen

> (3–5 Zitate aus User-Interviews oder Support-Tickets)

1. ___
2. ___
3. ___

### 3.2 Schmerzpunkte

> (3–5 dokumentierte Probleme mit Workarounds)

1. ___
2. ___
3. ___

### 3.3 Feature-Wünsche

> (Top-5, mit Stimmen-Anzahl)

1. ___ (N Stimmen)
2. ___ (N Stimmen)
3. ___ (N Stimmen)

---

## 4. Technische Beobachtungen

### 4.1 Performance

| View | Avg Load Time (ms) | p95 (ms) | Ziel < 500 ms |
|------|---------------------|----------|---------------|
| WorkspaceView (cold) | ___ | ___ | ☐ |
| WorkspaceView (warm, cache hit) | ___ | ___ | ☐ |
| InboxView | ___ | ___ | ☐ |
| BrowseView List | ___ | ___ | ☐ |
| BrowseView Graph (Cytoscape mount) | ___ | ___ | ☐ |

### 4.2 Fehler-Häufigkeit

| Error-Klasse | Anzahl (30d) | Top-Endpoint |
|--------------|---------------|----------------|
| 5xx | ___ | ___ |
| 4xx (außer 404) | ___ | ___ |
| Feature-Flag-404 | ___ | ___ (erwartet) |

### 4.3 Cytoscape-Adoption

| Browser | Cytoscape mount erfolgreich | Mount-Fehler |
|---------|------------------------------|--------------|
| Chrome | ___ | ___ |
| Firefox | ___ | ___ |
| Safari | ___ | ___ |

---

## 5. Lieferumfang vs. Plan

| Plan-Item | Status | Commits |
|-----------|--------|---------|
| Phase 1 Workspace | ✅ done | `83173d0`, `c8af2d9`, `dc692a8`, `fa2d58d` |
| Phase 2 Inbox | ✅ done | n/a (vor Mainline-Merge) |
| Phase 3.1+3.3+3.4 Onboarding | ✅ done | `9654efd` |
| Phase 3.5 Tag-Vorschläge | ✅ done | `2e78228` |
| Phase 3.6 Inline-Audit | ✅ done | `7f52e96`, `cb3bd85` |
| Phase 3.7 NewDebateForm | ✅ done | `e8006c7` |
| Phase 3.8 DocumentUploader | ✅ done | `c04028a` |
| Phase 4 Graph Backend | ✅ done | (vor Mainline-Merge) |
| Phase 4.5-4.7 Cytoscape | ✅ done | `0b6f1de` |
| Phase 4.9 BrowseView Toggle | ✅ done | `c95f601` |
| Phase 5.4 Inspector Graph Tab | ✅ done | `0552e6b` |
| Phase 5.6 CasesView read-only | ✅ done | `0a2c593` |
| **Phase 6.2 Telemetrie** | ✅ done | `3d49d1d` |
| **Phase 6.3 Metriken-Doku** | ✅ done | `8a5382a` |
| **Phase 6.4 i18n-Keys** | ✅ done (graph-Keys) | `d5d4ad7` |
| **Phase 6.5 User-Doku** | ✅ done | `6a01c6f` |
| **Phase 6.6 Plan-Archivierung** | ✅ done | `df8a48a` |
| **Phase 6.7 Retrospektive** | ⏳ dieses Dokument | n/a |
| Phase 1.14/2.12 Playwright E2E | ⏸ zurückgestellt | n/a |
| Phase 4.6 graphStore.svelte.js | ⏸ zurückgestellt | n/a |
| Phase 4.10 Saved-Views | ⏸ zurückgestellt | n/a |
| Phase 5.2 graph_edge_cache | ⏸ zurückgestellt | n/a |

---

## 6. Empfehlungen für Phase 7+

> Diese Sektion wird am 2026-07-15 befüllt.  Sie soll drei
> konkrete Empfehlungen enthalten: "Weiter so", "Anpassen",
> "Aufgeben".

1. **Weiter so:** ___
2. **Anpassen:** ___
3. **Aufgeben:** ___

---

## 7. Anhang — Methodik

### Datenerhebung

- **Telemetrie-Quelle:** `feedbackStore.activityLog` (Commit
  `3d49d1d`)
- **Persistenz:** aktuell nur In-Memory; Phase 7 muss einen
  Bulk-Flush ans Backend implementieren (siehe
  `2026-06-15_case-space-metrics.md` §3)
- **Auswertungs-Skript:** siehe `2026-06-15_case-space-metrics.md` §5

### Datenlücken

- `last_workspace`-Wiederherstellung misst nur Erfolg der
  `restoreLastWorkspace()`-Funktion, nicht UX
- Login/Logout-Events fehlen (Phase 7-Item) — Page-Count nur
  schätzbar
- 5-Klick-Regel nur manuell messbar
- Welcome-Card-Akzeptanz nicht messbar (kein A/B-Testing)

### Reproduzierbarkeit

Alle Datenpunkte in diesem Bericht sind aus den Telemetrie-Hooks
in `WorkspaceView.svelte` und `InboxView.svelte` ableitbar.  Das
Python-Snippet in `2026-06-15_case-space-metrics.md` §5 erlaubt
die Reproduktion ohne Dashboard.

---

*Template erstellt 2026-06-15 — auszufüllen am 2026-07-15.*
