# Case-Space Walkthrough — 90-Sekunden-Skript

> Begleit-Doku zu [`2026-06-14_case-space-workspace.md`](../plans/2026-06-14_case-space-workspace.md)
> Phase: 6.5 (Phase 6 — Aufräumen)
> Zielgruppe: Endnutzer*innen (Debate-Ersteller*innen)
> Verwendung: Skript für eine max. 90 s Video-Tour, kann auch als reiner Text-Walkthrough gelesen werden.

Dieses Dokument führt in 7 Szenarien durch die neue
Case-Space-Oberfläche.  Jedes Szenario ist in **0:00–0:90** als
einzelne Filmsequenz mit Voice-Over-Untertiteln konzipiert.

---

## Szenario 1 — Erste Anmeldung (0:00–0:15)

> *"Sie loggen sich ein.  Auf dem Dashboard sehen Sie oben eine
> Welcome-Card mit drei Klick-Pfaden.  Kein Modal-Wizard, kein
> Zwang — Sie entscheiden, was Sie zuerst tun möchten."*

**Was zu sehen ist:**
- Login-Bildschirm
- Dashboard nach Login
- Welcome-Card mit drei Buttons

**Voice-Over-Punkte:**
1. Welcome-Card taucht nur auf, wenn der Tenant **keine Cases** hat
2. Dismiss-Button in der Card-Ecke → Card verschwindet
3. Card kommt **nicht** zurück, solange der Tenant keine Cases hat

---

## Szenario 2 — Ihren ersten Case anlegen (0:15–0:30)

> *"Klick auf 'Create your first Case'.  Sie landen in der
> Cases-View mit fokussiertem Eingabefeld.  Tippen Sie einen
> Titel, Enter — der Case ist angelegt und im Header als
> aktiver Case markiert."*

**Was zu sehen ist:**
- Welcome-Card → Klick "Create Case"
- Cases-View mit Inline-Eingabefeld
- Tippen + Enter
- Header: Case-Selector zeigt neuen Case als aktiv

**Voice-Over-Punkte:**
1. Der Case wird automatisch zum **aktiven Case** — WorkspaceView fokussiert ihn
2. Der Case bleibt in `last_workspace` (User-Setting) — beim nächsten Login wieder da
3. Optional: Tags können hier vergeben oder später nachgepflegt werden

---

## Szenario 3 — Im Workspace arbeiten (0:30–0:50)

> *"Sie sind jetzt im Workspace — Ihrer Heimat für diesen Case.
> Drei Karten: This Case zeigt alle Debatten und Dokumente;
> Suggested Next Steps sagt Ihnen, was als nächstes fehlt;
> Recent Activity zeigt, was zuletzt passiert ist."*

**Was zu sehen ist:**
- WorkspaceView mit drei Karten
- Klick "Start a debate" in der This-Case-Karte

**Voice-Over-Punkte:**
1. This Case = alle Inhalte des aktuellen Cases
2. Suggested Next Steps = kontextuelle Hinweise (leer = alles gut)
3. Recent Activity = letzte 5 Audit-Events mit Phase + Round Spalten
4. Klick auf eine Zeile in Recent Activity → Audit-View gefiltert auf diese Debatte

---

## Szenario 4 — Disambiguierung beim Anlegen einer Debatte (0:50–1:05)

> *"Sie klicken 'Start a debate'.  Das System fragt: existierender
> oder neuer Case?  Standard ist der aktive Case — ein Klick.  Sie
> geben das Thema ein, Enter.  Fertig."*

**Was zu sehen ist:**
- Modal "New Debate" öffnet sich
- Default = bestehender Case, ein Klick
- Themen-Eingabe
- Submit → neue Debatte

**Voice-Over-Punkte:**
1. **Niemand startet eine Debatte ohne Case-Bezug** — das System fragt
2. Tags des aktuellen Cases werden als Quick-Buttons vorgeschlagen
3. Klick auf einen Tag-Vorschlag übernimmt ihn sofort
4. Nach Submit: Wechsel zur Debatte, Workspace-Counter aktualisiert sich

---

## Szenario 5 — Inbox für offene Aufgaben (1:05–1:20)

> *"Im Workspace fehlt nichts — aber die Inbox ist Ihr Sicherheitsnetz.
> Hier landen ungetaggte Debatten, kürzlich abgeschlossene, und
> lange laufende.  Bulk-Aktionen erlauben es, mehrere auf einmal
> zu taggen, zu verschieben oder zu archivieren."*

**Was zu sehen ist:**
- Sidebar → Inbox
- Tabs: All / Untagged / Recently Completed / Stale Running
- Bulk-Bar am unteren Rand

**Voice-Over-Punkte:**
1. Sidebar-Badge zeigt Anzahl offener Items
2. Tabs filtern nach Kategorie
3. Checkbox + Bulk-Bar → Move / Tag / Archive für mehrere
4. "All clear" = positive Verstärkung, nicht "0 items"

---

## Szenario 6 — Browse mit Graph-Toggle (1:20–1:30)

> *"Browse ist für Power-User.  Hier sehen Sie alle Cases,
> Dokumente, Debatten und Audit-Events im Tenant.  Mit dem
> List/Graph-Toggle wechseln Sie in die Graph-Ansicht — Cytoscape
> rendert die Beziehungen, oder die Liste als Fallback."*

**Was zu sehen ist:**
- BrowseView
- Toggle "List / Graph"
- Cytoscape-Graph oder Listen-Ansicht

**Voice-Over-Punkte:**
1. Filter (Tenant, Case, Tag, Status) bleiben für beide Modi
2. List-Modus ist Default und lädt sofort
3. Graph-Modus lädt Cytoscape lazy (~440 kB gz)
4. Knoten-Klick öffnet Inspector — gleicher Inspector wie im Workspace

---

## Szenario 7 — URL als Deep-Link (1:30–1:40)

> *"Sie können jeden Case, jede Debatte, jeden Audit-Eintrag
> per URL teilen.  Beim Login wird Ihr letzter Workspace
> automatisch wiederhergestellt — kein Klick nötig."*

**Was zu sehen ist:**
- URL-Änderung beim Case-Wechsel
- Reload des Browsers → Case ist noch da
- Logout/Login → Workspace wieder da

**Voice-Over-Punkte:**
1. URL-Format: `#/workspace?case=…`
2. `last_workspace` ist ein User-Setting — pro Browser, pro Login
3. Mehrere Tabs mit unterschiedlichen Cases möglich

---

## Aufnahme-Checkliste (für Video-Produktion)

- [ ] Demo-Tenant mit 3 Cases, 8 Debatten, 12 Docs, 6 Tags
  vorbereiten (siehe [`2026-06-14_case-space-impl-todos.md`](../plans/2026-06-14_case-space-impl-todos.md) Item 0.7 — optional, Phase-6-Item)
- [ ] Browser-Tab "In Private Window" (keine Lesezeichen-Sidebar)
- [ ] Bildschirmauflösung 1920×1080
- [ ] Audio: Mono, ~ -16 LUFS, klare Aussprache
- [ ] Untertitel: Deutsch + Englisch parallel
- [ ] Branding: Logo nur in den letzten 3 s

---

## Dauer-Monitoring

Jedes Szenario hat ein Zeitfenster.  Wenn ein Szenario länger
braucht, **nicht** den Inhalt kürzen — stattdessen den
vorherigen Szenario kürzen.  Die 7 Szenarien decken 80 % der
typischen Anwendungsfälle ab; weitere Details finden sich in
den jeweiligen Kapiteln des `user_manual.md`.
