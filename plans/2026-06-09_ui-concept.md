# UI-Konzept: Unified Entity Management

> Status: Draft | Autor: opencode | Datum: 2026-06-09

## 1. Problem-Analyse

**Ist-Zustand — Fragmentierte Navigation:**
- Tenants, Cases, Tags, Documents, Archive, Audit Trail liegen als 6 separate Views verstreut
- Keine Übersicht über Beziehungen (welche Docs gehören zu welchem Case? welche Debatten haben welche Tags?)
- Verschieben von Debatten zwischen Cases: Umweg über Archive → Move-Aktion
- Audit Trail: unter CONFIG versteckt, manuelle Debate-ID-Eingabe erforderlich
- Keine Entity-Hierarchie sichtbar (Tenant → Case → Debate)

## 2. Zielbild: Workspace mit Entity Explorer

```
┌──────────────────────────────────────────────────────────────────────┐
│  Header: Tenant-Selector ▾  │  Case-Selector ▾  │  🔍 Search...    │
├──────────┬──────────────────────────────────────┬────────────────────┤
│          │                                      │                    │
│ EXPLORER │         MAIN PANEL                   │   DETAIL PANEL     │
│          │                                      │                    │
│ 🏢Tenant1│  (context-dependent content)         │  Properties        │
│   📁Case1│                                      │  Tags              │
│     📋D1 │                                      │  Relationships     │
│     📋D2 │                                      │  Quick Actions     │
│   📁Case2│                                      │                    │
│     📋D3 │                                      │                    │
│   🏷Tags │                                      │                    │
│ 🏢Tenant2│                                      │                    │
│          │                                      │                    │
├──────────┴──────────────────────────────────────┴────────────────────┤
│  Status Bar: Tenant: X │ Case: Y │ Debates: 12 │ Docs: 45 │ Tags: 8│
└──────────────────────────────────────────────────────────────────────┘
```

## 3. Drei Hauptbereiche

### 3.1 Explorer (linke Seitenleiste)

Ersetzt die aktuelle flache Sidebar für Admin-Views durch einen **Baum-Navigator**:

```
▼ WORKSPACE
  🏢 Tenant: Acme Corp (default)
    📁 Case: "AI Ethics Research"
      📋 Debate: "Teaching AI Human Values"  ✅ completed
      📋 Debate: "Climate Policy Debate"     🔄 running
      📄 Doc: "research_paper.pdf"
      📄 Doc: "interview_transcript.docx"
    📁 Case: "Legal Review"
      📋 Debate: "GDPR Compliance"           ✅ completed
      📄 Doc: "compliance_checklist.xlsx"
    🏷 Tags (8)
  🏢 Tenant: Research Lab
    📁 Case: "..."
```

**Interaktionen:**
- **Klick auf Case** → Main Panel zeigt Case-Übersicht (Debatten + Docs)
- **Klick auf Debate** → Main Panel zeigt Debate-Details / navigiert zu DebateView
- **Drag & Drop** → Debate von Case A nach Case B verschieben
- **Rechtsklick** → Kontextmenü (Rename, Delete, Move, New Debate)
- **Suche** → Filtert den Baum in Echtzeit

### 3.2 Main Panel (zentral)

Kontextabhängig — zeigt je nach Selection:

**When Tenant selected:**
```
┌─ Tenant: Acme Corp ──────────────────────────────────────┐
│                                                           │
│  ┌─ Cases (3) ──────────────┐  ┌─ Recent Activity ─────┐ │
│  │ 📁 AI Ethics (12 debates)│  │ 📋 "Teaching AI..."  │ │
│  │ 📁 Legal Review (5)      │  │    completed, 2h ago  │ │
│  │ 📁 Product Launch (8)    │  │ 📋 "GDPR..."          │ │
│  └──────────────────────────┘  │    running, now       │ │
│                                └───────────────────────┘ │
│  ┌─ Tags ──────────────────┐  ┌─ Documents (45) ───────┐ │
│  │ 🏷 ethics (12)          │  │ 📄 research_paper.pdf  │ │
│  │ 🏷 legal (8)            │  │ 📄 transcript.docx     │ │
│  │ 🏷 urgent (3)           │  │ 📄 checklist.xlsx      │ │
│  └──────────────────────────┘  └───────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

**When Case selected:**
```
┌─ Case: "AI Ethics Research" ─────────────────────────────┐
│                                                           │
│  Tags: [ethics] [research] [+ add]                       │
│  Description: Research on AI ethical frameworks...        │
│                                                           │
│  ┌─ Debates (12) ──────────────────────────────────────┐ │
│  │ Title              Status    Tags        Updated    │ │
│  │ ─────────────────────────────────────────────────── │ │
│  │ Teaching AI...     ✅ done   ethics      2h ago     │ │
│  │ Climate Policy     🔄 run    urgent      now        │ │
│  │ Bias in ML         ⏸ paused  research    1d ago     │ │
│  │ [+ New Debate]                                    │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌─ Documents (5) ─────────────────────────────────────┐ │
│  │ 📄 research_paper.pdf  [View] [Analyze] [Move...]  │ │
│  │ 📄 transcript.docx     [View] [Edit]   [Move...]  │ │
│  │ [+ Upload Document]                                │ │
│  └──────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

### 3.3 Detail Panel (rechts)

Zeigt Details für das ausgewählte Entity:

**Debate selected:**
```
┌─ Properties ────────────────┐
│ Title: Teaching AI...       │
│ Status: ✅ completed        │
│ Rounds: 4                   │
│ Created: 2026-06-08 14:30   │
│ Duration: 12m 34s           │
│                             │
│ Tags:                       │
│   [ethics] [research] [+ ]  │
│                             │
│ Relationships:              │
│   Case: AI Ethics Research  │
│   Docs: 3 linked            │
│                             │
│ Quick Actions:              │
│   [▶ View Debate]           │
│   [📋 Audit Trail]          │
│   [🔀 Fork]                 │
│   [📦 Archive]              │
│   [➡️ Move to Case...]      │
│   [🗑 Delete]               │
└─────────────────────────────┘
```

**Document selected:**
```
┌─ Properties ────────────────┐
│ Name: research_paper.pdf    │
│ Type: PDF (2.3 MB)          │
│ Case: AI Ethics Research    │
│                             │
│ Tags: [ethics] [+ ]        │
│                             │
│ RAG Status: indexed ✅      │
│ Chunks: 45                  │
│                             │
│ Quick Actions:              │
│   [👁 View] [✏️ Edit Text]  │
│   [🔍 RAG Search]           │
│   [📊 Analyze]              │
│   [➡️ Move to Case...]      │
│   [🗑 Delete]               │
└─────────────────────────────┘
```

## 4. Key Workflows

### 4.1 Debate zwischen Cases verschieben

**Aktuell:** Archive → Suche → Move → Case auswählen → OK (4 Klicks, nicht intuitiv)

**Neu:**
1. **Drag & Drop** im Explorer: Debate von Case A nach Case B ziehen
2. Oder: Debate auswählen → Detail Panel → "Move to Case..." → Dropdown

### 4.2 Tag-Management im Kontext

**Aktuell:** Separater Tags-Bearbeitungsview, disconnected von den Entities

**Neu:**
- Tags direkt an Entities zuweisen (Case-Detail, Debate-Detail, Document-Detail)
- Tag-Filter im Main Panel (z.B. "zeige alle Debatten mit Tag 'urgent'")
- Tag-Hierarchie im Explorer sichtbar
- Bulk-Tagging: Mehrere Debatten auswählen → gemeinsam taggen

### 4.3 Audit Trail ohne manuelle ID-Eingabe

**Aktuell:** Man muss Debate-ID kennen und manuell eingeben

**Neu:**
- Debate auswählen → Detail Panel → "Audit Trail" Klick → öffnet AuditView mit vorbefüllter ID
- Oder: Rechtsklick auf Debate → "Show Audit Trail"
- Audit Events werden als Timeline im Detail Panel angezeigt (Inline, ohne Navigation)

### 4.4 DMS-Dokumente im Case-Kontext

**Aktuell:** DocumentsView zeigt alle Docs, nicht nach Case gruppiert

**Neu:**
- Case auswählen → nur Docs dieses Cases sichtbar
- DocumentsView bleibt als "alle Dokumente" Ansicht erhalten
- Neue Spalte "Case" in der Document-Liste
- Schnellfilter: "Unlinked Documents" (Docs ohne Case-Zuordnung)

### 4.5 Bulk-Operationen

Mehrere Items auswählen (Checkboxen) für:
- Mehrere Debatten verschieben
- Mehrere Docs einem Case zuordnen
- Mehrere Debatten gleichzeitig taggen
- Mehrere Items archivieren/löschen

## 5. Neue Sidebar-Struktur

```
📊 Dashboard

─── WORKSPACE ──────────────────
  🏢 Tenants & Cases           (neuer Unified Explorer)
  🏷️ Tags                      (bleibt, erweitert)

─── RUN ───────────────────────
  💬 Debate / MVP Debate
  ⚡ Live Execution
  📄 Documents
  📚 Archive

─── BUILD ─────────────────────
  🧩 Blueprints
  🔧 Manage
  🧩 Modules
  🧩 Bundle Composer
  🌐 Translation

─── CONFIG ────────────────────
  📋 Audit Trail
  ⚙️ Configure

─── ADMIN ─────────────────────
  👥 Users
  🖥️ Server Health

─── EVOLVE ────────────────────
  🔍 Proposals
```

Die `Tenants & Cases` View (neuer Unified Explorer) ersetzt die separaten `Tenant Settings` und `Cases` Views durch eine integrierte Baumansicht.

## 6. Technische Schlüssel-Entscheidungen

| Aspekt | Empfehlung |
|--------|-----------|
| Explorer-State | Svelte stores für expanded/noded/selected |
| Drag & Drop | `svelte-dnd-action` oder native HTML5 DnD |
| Bulk-Auswahl | Checkboxen + Action-Bar am unteren Rand |
| Inline Audit | In Debate-Detail Panel einbetten (keine Navigation nötig) |
| Tag-Filter | Query-Parameter an Listen-Komponenten (debounce) |
| Responsive | Bei < 1024px: Explorer als Overlay/Drawer |

## 7. Priorisierung

| Phase | Features | Aufwand |
|-------|----------|---------|
| **P1** | Unified Explorer (Tenant→Case→Debate/Doc Baum) | Hoch |
| **P1** | Debate Move via Detail Panel + Drag & Drop | Mittel |
| **P1** | Audit Trail vorbefüllt aus Debate-Detail | Niedrig |
| **P2** | Bulk-Operationen (Multi-Select + Action-Bar) | Mittel |
| **P2** | Tag-Filter in Listen | Niedrig |
| **P2** | Inline Audit im Detail Panel | Mittel |
| **P3** | Context Menu (Rechtsklick) | Niedrig |
| **P3** | Responsive Drawer für Explorer | Niedrig |
