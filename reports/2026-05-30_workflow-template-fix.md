# Workflow-Template "Transactional Drafting" — Analyse & Fixes

**Datum:** 2026-05-30  
**Symptom:** Bei Ausführung über "Run → New Debate" wird keine Debatte im UI angezeigt, obwohl LLM-Anfragen im Monitor sichtbar sind.

---

## 1. Wurzelursache

`start_workflow` (`workflow_exec.py:454`) erstellt **keinen Debate-Record** in `DebateStore` und setzt keine `debate_id` im State. Dadurch:

1. **Dashboard/Archive:** Debatte erscheint nicht in der Liste (kein Record)
2. **Frontend-Routing:** `InputComposerView.handleCreated()` routet zu `WorkflowExecutionView` (360px Seiten-Panel) statt zu `MvpDebateView` (volle Debate-Ansicht)
3. **Completion-Handler:** `run_workflow_background` kann Debate-Status nicht aktualisieren (keine `debate_id` im State)

Vergleich mit `start_mvp_debate` (Zeilen 380–423), das alle drei Schritte korrekt ausführt.

---

## 2. Durchgeführte Fixes

### Fix 1: Debate-Record-Erstellung in `start_workflow`

**Datei:** `backend/api/routers/workflow_exec.py`

- Erstellt `debate_id` via `uuid.uuid4()`
- Generiert Titel via `generate_debate_title()` (mit Fallback)
- Speichert Debate-Record in `DebateStore` mit `status=RUNNING`
- Setzt `initial_state["debate_id"] = debate_id`

### Fix 2: `debate_id` in `StartWorkflowResponse`

**Datei:** `backend/api/routers/workflow_exec.py`

- `StartWorkflowResponse` enthält jetzt `debate_id: str | None`
- Response wird mit `debate_id` gefüllt

### Fix 3: Frontend-Routing zu MvpDebateView

**Datei:** `frontend/src/views/InputComposerView.svelte`

- `handleCreated()` prüft `response.debate_id` vor `response.session_id`
- Wenn `debate_id` vorhanden → navigiere zu `mvp-debate/{debate_id}`

**Datei:** `frontend/src/views/BlueprintCanvasView.svelte`

- Nach `startWorkflow()` wird `result.debate_id` geprüft
- Wenn vorhanden → navigiere zu `mvp-debate/{debate_id}` statt Seiten-Panel zu öffnen

---

## 3. Datenfluss nach Fix

```
User klickt "Run → New Debate"
  → POST /api/v1/workflow-exec/{workflow_id}/start
    → Workflow kompilieren (LangGraph)
    → RAG-Kontext auflösen
    → Debate-Record erstellen (DebateStore)
    → debate_id in initial_state setzen
    → Background-Task dispatchen
    → Response: { session_id, debate_id, status: "running" }
  → Frontend: navigate('mvp-debate/' + debate_id)
  → MvpDebateView: SSE-Stream verbinden, Debate anzeigen
```

---

## 4. Verbleibende Probleme

| # | Problem | Severity | Status |
|---|---------|----------|--------|
| 1 | `current_node_id` ist `""` für System-Nodes (SSE-Events haben leere node_id) | Low | Nicht behoben — kosmetisch |
| 2 | Debate-Completion erfordert `debate_id` im State (jetzt gesetzt) | — | Behoben |
| 3 | `WorkflowExecutionView` wird nie erreicht wenn `debate_id` vorhanden | — | By Design — Debate-View ist die bessere UX |
