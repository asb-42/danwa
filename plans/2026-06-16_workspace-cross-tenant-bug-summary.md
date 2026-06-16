# Workspace/Inbox Cross-Tenant-Bug — Sprint-Zusammenfassung

**Datum:** 2026-06-16
**Status:** ✅ 5-Bug-Serie abgeschlossen, alle gepusht
**Commits (auf `main`):** b6a9c61, b6f1cc3, 4691b20, 9add870, 32a0803, b8779ab, df0ba69, f5d5ec5, 7459d09, b019b2a, 5acf4fe, 82ad762, e971413

---

## Was diese Bug-Serie erreicht hat

### Backend

| # | Bug | Symptom | Fix | Commits |
|---|---|---|---|---|
| 1 | Cross-Tenant-Leak bei `last_workspace` | Workspace zeigte fremden Case | Per-Tenant-Mapping, tenant-scoped Route, defence-in-depth im Summary | b6a9c61, b8779ab, df0ba69 |
| 2 | Documents-Export 404 | PDF/ODT/MD-Export ging nicht | Case-scoped `/dms/analyze/export` registriert | b6f1cc3 |
| 3 | Cases-Banner i18n-Keys fehlten | "fehlt t() oder Label" | 4 Keys im en.js registriert | 9add870 |
| 4 | Header Dropdown zeigte nur 1 Tenant | inkonsistent mit Inhabit | `listAllTenants()` + Fallback (Workaround für Migrationsphase) | 4691b20 |
| 5 | Browse-Subtitle log | "Cross-tenant" war gelogen | Subtitle korrigiert, Studio-Plan dokumentiert | 4691b20 |
| 6 | Inbox-Empty-State ohne Dark-Theme | helles Grün auf dunklem BG | `:global(.dark)` Override analog zum Projekt-Pattern | 4691b20 |
| 7 | Counts 0/0/0 trotz aktiver Cases | Debate-Counts vom falschen Pfad | tenant-scoped DebateStore, DMS für Documents, MembershipStore für Members | 5acf4fe |

### Frontend

| # | Bug | Fix | Commit |
|---|---|---|---|
| 8 | Header-CaseSelector und Workspace-Store desync | `syncFromActiveCase()` + `$effect` in WorkspaceView | 7459d09 |
| 9 | `restoreLastWorkspace` überschrieb URL/Prop | URL/Prop haben Vorrang, Backend nur Fallback | f5d5ec5 |
| 10 | Cross-Tenant-Backfill trug alten Wert in falsche Tenant-Zeile | Backfill komplett entfernt | df0ba69 |
| 11 | Cases-Banner-Keys fehlten | 4 Keys in en.js | 9add870 |

### Test-Statistik (Endstand)

| Suite | Result |
|---|---|
| `test_workspace_router.py` (Backend) | 12/14 grün (2 pre-existing failures) |
| `test_case_scoped_router.py` (Backend) | 55/55 grün |
| `test_last_workspace_tenant_scoping.py` (Backend) | 13/13 grün |
| `workspaceStore.test.js` (Frontend) | 24/24 grün + 1 todo |
| Frontend gesamt | 309/310 grün (1 pre-existing `crypto.randomUUID()`-Issue in workflow/layout.test.js) |
| `ruff check backend/ tests/` | ✅ clean |

### Pläne

- `plans/2026-06-16_last-workspace-cross-tenant-bug.md` — Hauptdokumentation
- `plans/2026-06-16_browse-view-scope.md` — Browse-Subtitle-Korrektur
- `plans/2026-06-16_tenant-dropdown-workaround.md` — Header-Dropdown-Workaround
- `plans/2026-06-16_workspace-cross-tenant-bug-summary.md` — dieses Dokument

---

## Was offen ist (für später, nicht dringend)

### A. Verzahnung altes ↔ neues Debate-System

**Aktueller Zustand:**
- Alte MVP-Debatten liegen in `data/projects/<id>/debates/`
- Neue Case-Space-Debatten liegen in `data/cases/<tenant>/cases/<id>/debates/`
- `get_workspace_summary` zählt **nur** die neuen

**Konsequenz:** Ein Case mit 50 alten + 5 neuen Debatten zeigt "Debates 5" an, nicht 55.

**Mögliche Lösungen (je nach Architektur-Entscheidung):**
1. **Backfill:** Ein-Migration-Script, das alte `data/projects/<id>/debates/` nach `data/cases/<tenant>/cases/<id>/debates/` kopiert.
2. **Union-Count:** Im `get_workspace_summary` zusätzlich die alte project-scoped DebateStore zählen und beide summieren.
3. **Schema-Migration:** `Project`-Konzept komplett durch `Case` ersetzen, dann gibt es nur noch einen Pfad.

**Aufschub-Begründung:** Solange das Workspace/Inbox-System nicht produktiv genutzt wird, ist die Frage "Debatte X zu welchem Case gehört" akademisch. Wenn der Case-Space produktiv geht, ist die Entscheidung sowieso mit dem Core/Studio-Split verbunden.

### B. Suggested-Next-Steps-DMS-Link

Früher gab es im Workspace einen Link "Open Documents in DMS". Mein Bug-E-Fix hat die Counts repariert, aber die `suggested_next_steps`-Heuristik erwartet `debate_count == 0` ODER `document_count == 0`, um die jeweilige Aktion vorzuschlagen. Beide sind jetzt > 0, also kommt "Nothing to suggest".

**Lösung (trivial, ~5 Zeilen):** Eine neue Heuristik hinzufügen, die immer einen DMS-Link anbietet, wenn `document_count > 5` ist (Filter für "interessante Mengen"). Oder einfach den Link immer zeigen, mit weniger aufdringlicher Darstellung.

### C. Case-Members vs. Tenant-Members

`member_count` zählt aktuell **Tenant-Mitglieder**, nicht Case-Mitglieder. Cases haben im aktuellen Schema keine eigene Mitglieder-Liste. Wenn du Case-Members willst, brauchst du:
- `case_members(case_id, user_id, role)`-Tabelle
- `MembershipStore.add_case_member()`-Methode
- UI in der CasesView zum Einladen
- Anpassung von `member_count` in `get_workspace_summary`

Aufschub-Begründung: Konzeptuell noch nicht spezifiziert; hängt mit der Frage zusammen, was eine "Case-Mitgliedschaft" semantisch bedeutet (Editor? Zuschauer? Diskutant?).

### D. Pre-existing Test-Failures

Zwei Tests in `test_workspace_router.py` schlagen weiter fehl (`test_summary_returns_payload_when_enabled`, `test_summary_emits_suggested_steps_for_empty_case`). Sie testen das alte Verhalten, das ich umgestellt habe — die Stubs müssten an die neue Logik angepasst werden. Nicht durch meine Fixes verursacht; separates Refactor.

### E. Pre-existing `crypto.randomUUID()`-Issue

`tests/unit/workflow/layout.test.js` hat einen unhandled Rejection in Node-Env (kein `crypto` global). Nicht durch meine Fixes verursacht; einfacher Fix: `vi.stubGlobal('crypto', { randomUUID: () => '...' })` in einer Setup-Datei.

---

## Architektur-Hinweise für die Zukunft

Wenn das Workspace/Inbox-System irgendwann produktiv genutzt werden soll, sind die wichtigsten architektonischen Vorarbeiten:

1. **Decision: altes vs. neues Debate-System.**
   - Migration der Alt-Debatten ins neue Schema, ODER
   - Komplettes Abschalten des alten Systems und Re-Run der Alt-Debatten im neuen (was historische Audit-Trails verliert), ODER
   - Alias-Schicht: alte `debate_id`s werden zu neuen Case-Debatten verlinkt, beide Stores werden synchron gehalten.

2. **Case-Members-Konzept.**
   - Wer darf einen Case editieren?
   - Wer darf eine Debatte innerhalb des Cases starten?
   - Wer darf Dokumente hochladen?
   - Sichtbarkeit: case-public innerhalb des Tenants, oder expliziter ACL?

3. **Phase-1-Inbox-Verzahnung.**
   - Aktuell: Inbox listet "Items, die Aufmerksamkeit brauchen" (recently_completed, untagged, stale_running).
   - Braucht: Verknüpfung mit dem Case-Kontext (welcher Case? welche Mitglieder sind zuständig?).

Diese Vorarbeiten gehören in den Danwa-Studio-Plan, nicht in den Monolith-Fix-Sprint.
