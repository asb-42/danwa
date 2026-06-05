# Workflow-Pipeline: wiederverwendbare Visualisierung

Status: Entwurf
Betrifft: `frontend/src/components/DashboardWorkflowGraph.svelte` (Ablösung),
`frontend/src/components/WorkflowGraph.svelte` + `workflow/WorkflowCanvas.svelte` (Harmonisierung)

## Ziel

Eine einzige, datengetriebene Visualisierungskomponente, die
- im **Dashboard** den exemplarischen Ablauf der letzten abgeschlossenen Debatte zeigt,
- in **`DebateView`** den Live-Ablauf einer laufenden Debatte rendert (ggf. parallel zum bestehenden `WorkflowCanvas`),
- optional in **Audit-/Replay-Views** und der **Modul-Verwaltung** einsetzbar ist.

Die aktuell hartcodierte `DashboardWorkflowGraph` (feste `NODES`/`ALL_EDGES`-Konstanten, generische `status`-Prop ohne Datenbezug) wird ersetzt.

---

## 1. Komponenten-Architektur

```
frontend/src/components/workflow/
  WorkflowPipeline.svelte          ← Öffentliche API (einziger Import-Punkt für Consumer)
  pipeline/
    PipelineNode.svelte            ← Einzelner Knoten (Icon, Label, Status, Metriken)
    PipelineEdge.svelte            ← Kante (Vorwärts / Feedback, Beschriftung, Animation)
    PipelineLegend.svelte          ← Legende (Status, Retry)
    PipelineMetrics.svelte         ← Metrik-Badge (Tokens, Dauer, Consensus) auf Knoten
    PipelineEmptyState.svelte      ← Leerzustand ("Starte eine Debatte …")
    pipeline-utils.js              ← ELK-Layout, Geometrie, Farb-Mapping
  pipeline.css                     ← Geteilte Styles (Status-Farben, Glow, Pulse)
```

`DashboardWorkflowGraph.svelte` wird gelöscht.
`WorkflowGraph.svelte` bleibt als dünner Wrapper bestehen, der `WorkflowPipeline` im `live`-Modus einbettet (Rückwärtskompatibilität für `DebateView.svelte:862`).

---

## 2. Komponenten-Vertrag (Props)

```ts
// WorkflowPipeline.svelte
type NodeStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped';

type PipelineNode = {
  id: string;
  label: string;            // Lokalisierter Anzeigename
  icon?: string;            // Emoji oder URL
  color?: string;           // Akzentfarbe (default: aus palette)
  status: NodeStatus;
  metrics?: {
    tokens?: number;
    durationMs?: number;
    consensusScore?: number; // 0..1, nur für Moderator/Synthesis
    round?: number;
  };
  meta?: Record<string, unknown>; // freie Felder für künftige Erweiterungen
};

type PipelineEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
  kind?: 'forward' | 'feedback';
  active?: boolean;         // gerade durchlaufen
};

type WorkflowMeta = {
  id: string;               // z. B. debateId oder workflowProfileId
  name: string;             // "MVP-Debatte", "Bidirektional" …
  description?: string;
  source: 'live' | 'replay' | 'static' | 'definition';
};

type Props = {
  meta: WorkflowMeta;
  nodes: PipelineNode[];
  edges: PipelineEdge[];
  activeNodeId?: string | null;
  mode?: 'live' | 'replay' | 'static';   // default: 'static'
  compact?: boolean;                      // kompakte Dashboard-Variante
  interactive?: boolean;                  // Klick → onNodeClick
  showMetrics?: boolean;                  // default: true in 'live'/'replay'
  onNodeClick?: (node: PipelineNode) => void;
  onEdgeClick?: (edge: PipelineEdge) => void;
};
```

`bind:activeNodeId` ist als Bindable geplant, damit `DebateView` den vom SSE-Stream gelieferten Knoten reaktiv durchreichen kann.

---

## 3. Datenquellen

### 3.1 Live (laufende Debatte)
- Bestehende SSE-Infrastruktur (`workflowSSE.js`) bleibt.
- Neue Helfer-Funktion `subscribeWorkflowNodes(debateId, onUpdate)` mappt die SSE-Events (`onNodeStart`, `onLLMCallStarted`, `onNodeComplete`, `onError`) auf das oben definierte `PipelineNode[]`-Format.
- Adapter lebt in `frontend/src/lib/workflowPipelineAdapter.js`, ist von `WorkflowPipeline` unabhängig testbar.

### 3.2 Letzte abgeschlossene Debatte (Dashboard)
- Neue Backend-Route `GET /api/v1/debates?status=completed&limit=1&include=workflow_state` liefert die jüngste abgeschlossene Debatte inklusive finalem `node_outputs` und `workflow_definition`.
- Frontend-Hook `useLastCompletedDebatePipeline()` kombiniert:
  1. Debatte laden,
  2. Workflow-Profil/Definition laden,
  3. Knoten mit `status: 'done'` und `metrics: {tokens, durationMs}` aus `node_outputs` befüllen,
  4. Sortierung gemäß Definition (Topo-Sort),
  5. Retry-Kanten anhand `current_round > 1` aktivieren.

### 3.3 Statisch (Modul-Verwaltung, Onboarding)
- Reine Definition ohne Laufzeitdaten: `status: 'pending'` für alle Knoten, `activeNodeId=null`.
- Verwendet das neue `GET /api/v1/workflows/{id}/definition`-Endpoint (falls noch nicht vorhanden, dann aus `workflowSSE.js`/`blueprint_registry` ableiten).

---

## 4. UI-Verhalten

### 4.1 Visuelle Hierarchie
- **Knoten-Zustände** haben klar getrennte Farbgebung:
  - `pending` → Outline grau, halbtransparent
  - `running` → Akzentfarbe, Glow, Pulse (jetzt schon vorhanden, wiederverwenden)
  - `done` → grünes Häkchen + dezenter Glow
  - `failed` → rote Outline, ⚠️-Badge
  - `skipped` → gestrichelter Rahmen
- **Kanten-Zustände**:
  - `forward` Standard, grau
  - `active` (Daten fließen gerade) animierter Partikel-Strom, gleicher Look wie heute
  - `feedback` weiterhin gestrichelt in Amber
- **Konsistente Terminologie** (Punkt 7): i18n-Keys werden in **einer** Datei gepflegt (`frontend/src/lib/i18n/loaders/<lang>.js` unter `workflowPipeline.*`). Die aktuelle Vermischung "Strategist/Strategy" wird aufgelöst — pro Workflow-Profil wählbar (`roleLabels`-Override).

### 4.2 Interaktion (Punkt 5)
- `interactive=true` → Knoten erhalten `role="button"`, `tabindex=0`, `aria-label`.
- `onNodeClick(node)` wird nach oben gereicht; Default in `DebateView`: Navigation zu Round/Node-Detail.
- Tastaturbedienung: `Enter`/`Space` aktiviert, `Tab` fokussiert.
- `aria-live="polite"`-Region für Statuswechsel (Screenreader).

### 4.3 Metriken (Punkt 4)
- `showMetrics=true` rendert `PipelineMetrics` auf jedem Knoten:
  - Tokens (`formatNumber`)
  - Dauer (`formatDuration`)
  - Consensus-Score (nur Moderator/Synthesis, wenn vorhanden)
- Bei `compact=true` (Dashboard) nur Konsens- und Token-Zahl, kein Dauer-Label — reduziert visuelle Last.

### 4.4 Modus-spezifisches Verhalten
| Modus      | Auto-Update | Partikel-Animation | Klick | Empty-State |
|------------|-------------|--------------------|-------|-------------|
| `live`     | via SSE     | ja                 | ja    | ausgeblendet, wenn `!meta.id` |
| `replay`   | via Replay-Controls | ja          | ja    | "Kein Replay verfügbar" |
| `static`   | nein        | nein               | optional | PipelineEmptyState |

### 4.5 Multi-Workflow-Support (Punkt 6)
- Falls mehrere Profile installiert sind, blendet `WorkflowPipeline` einen schmalen Profil-Pill **über** der Visualisierung ein:
  ```
  [ MVP-Debatte ▾ ]
  ```
  Auswahl wechselt die `nodes`/`edges`/`meta` (Empfänger: `onProfileChange`-Callback).
- Im Dashboard ist die Auswahl Read-only (zeigt das Profil der letzten abgeschlossenen Debatte).

### 4.6 Leerzustand (Punkt 8)
- `WorkflowPipeline` ohne Daten rendert `PipelineEmptyState`:
  - Primär: "Starte eine Debatte, um den Workflow zu sehen."
  - Sekundär: Button "Neue Debatte starten" (nur sichtbar wenn `navigate` injiziert ist)
- Hat den **gleichen visuellen Stil** wie die volle Pipeline (Karten-Container, Padding, Border), damit der Übergang nahtlos ist.

---

## 5. Migration der bestehenden Aufrufe

| Datei | Aktuell | Neu |
|-------|---------|-----|
| `views/Dashboard.svelte:262–263` | `<DashboardWorkflowGraph status=… activeNodeId=… />` | `<WorkflowPipeline {meta} {nodes} {edges} compact interactive={false} showMetrics />` — Daten via `useLastCompletedDebatePipeline()` |
| `views/DebateView.svelte:862` | `<WorkflowGraph {debateId} isRunning=… />` | unverändert; `WorkflowGraph` reicht intern an `WorkflowPipeline` weiter (Modus `live`) |
| `views/MvpDebateView.svelte` | (kein Graph) | Optional: `WorkflowPipeline` im Header-Bereich (Modus `live`, `compact=true`) — Vorschlag, nicht Pflicht |
| `components/DashboardWorkflowGraph.svelte` | — | **gelöscht** |

`WorkflowGraph.svelte` wird zu folgendem Wrapper reduziert:

```svelte
<script>
  import { useLiveWorkflowPipeline } from '../../lib/workflowPipelineAdapter.js';
  import WorkflowPipeline from './WorkflowPipeline.svelte';
  let { debateId = null, isRunning = false } = $props();
  const { meta, nodes, edges, activeNodeId } = useLiveWorkflowPipeline(debateId);
</script>

<WorkflowPipeline
  {meta} {nodes} {edges} {activeNodeId}
  mode="live"
  interactive
  onNodeClick={(n) => /* navigate to node detail */}
/>
```

---

## 6. Backend-Anforderungen

Falls nicht vorhanden, werden folgende Endpoints benötigt (Änderung am Backend getrennt von diesem Plan zu prüfen):

1. `GET /api/v1/debates?status=completed&limit=1&expand=workflow_state` — jüngste abgeschlossene Debatte inkl. `node_outputs`.
2. `GET /api/v1/workflows/{profile_id}/definition` — Knoten- und Kanten-Definition eines Workflow-Profils.
3. Bestehende SSE-Endpoints auf `events: node_started / node_completed / node_failed` prüfen und ggf. um ein explizites `node_status`-Event ergänzen, damit der Adapter ohne implizite Heuristik auskommt.

Open-Point: Klärung mit Backend-Team, ob (1) und (2) bereits unter anderer URL existieren (z. B. `/api/v1/debate/{id}/state`).

---

## 7. Schritte zur Umsetzung

1. **Branch** `feature/reusable-workflow-pipeline` (basierend auf `main`).
2. **Skelett** anlegen:
   - `workflow/WorkflowPipeline.svelte` (Props + Slot für Toolbar)
   - `workflow/pipeline/{PipelineNode,PipelineEdge,PipelineLegend,PipelineMetrics,PipelineEmptyState}.svelte`
   - `workflow/pipeline/pipeline-utils.js` (ELK-Wrapper, Geometrie, Status-Farben)
3. **Adapter** für Live- und Static-Modus:
   - `frontend/src/lib/workflowPipelineAdapter.js` mit `useLiveWorkflowPipeline` und `useLastCompletedDebatePipeline`.
4. **Dashboard**-Integration:
   - `useLastCompletedDebatePipeline()` in `Dashboard.svelte` einhängen.
   - `DashboardWorkflowGraph.svelte` ersetzen.
5. **DebateView**-Integration:
   - `WorkflowGraph.svelte` → `WorkflowPipeline`-Wrapper umbauen.
   - Sicherstellen, dass `OOBInputPanel` weiterhin funktioniert.
6. **A11y & i18n**:
   - Alle Strings in `workflowPipeline.*`-Namespace.
   - `aria-live` + Tastaturbedienung verifizieren.
7. **Tests**:
   - Unit: `pipeline-utils.js` (Layout, Farb-Mapping).
   - Component: `WorkflowPipeline.test.js` (Reactive Status, Mode-Wechsel).
   - E2E: `tests/e2e/workflow-pipeline.spec.js` (Dashboard mit Mock-Debatte, DebateView live).
8. **Cleanup**:
   - `DashboardWorkflowGraph.svelte` löschen.
   - Veraltete i18n-Keys (`dashboard.workflowLegend.*`) entfernen oder migrieren.
9. **Docs**:
   - `docs/architecture/workflow-pipeline.md` mit Beispiel-Nutzung und Props-Tabelle.
10. **Review & Merge** nach `main`.

---

## 8. Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|--------|---------------|
| Backend liefert `node_outputs` in anderer Struktur | Adapter mit Mapping-Tests abfedern, früh gegen echte API prüfen |
| ELK-Bundle-Größe in `compact`-Modus unnötig | `compact=true` nutzt vorberechnete Layouts (Re-use) oder reines CSS-Grid |
| SSE-Eventnamen unterscheiden sich zwischen Profilen | Adapter normalisiert auf kanonische Events, Mapping dokumentieren |
| Visuelle Regression bei `WorkflowCanvas`-Migration | `WorkflowGraph`-Wrapper parallel halten, Feature-Flag zum Umschalten |
| Bundle-Size durch Aufteilung in Subkomponenten | Tree-Shaking verifizieren, Komponenten klein halten |

---

## 9. Erwarteter Mehrwert

- **Eine** Komponente für alle Workflow-Visualisierungen → konsistente UX, ein Styleguide, eine Fehlerstelle.
- Dashboard bekommt endlich **echten** Datenbezug (Punkt 1–3 abgehakt) ohne die schicke Optik zu verlieren.
- Diskussionen über "Strategist vs. Strategy" hören auf (Punkt 7).
- Debatte-Header in `MvpDebateView` kann optional ebenfalls ein Mini-Pipeline einblenden — Mehrwert für laufende Sitzungen.
- Grundlage für künftige Erweiterungen (Re-Run-Vergleich, A/B-Workflow-Profile, Audit-Replay) ist gelegt.
