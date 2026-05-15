# Plan 19 — Follow-up-Debatte: Ergebnis als Ausgangspunkt

> **Status:** Planung  
> **Priorität:** Hoch  
> **Abhängigkeiten:** Plan 18 (Backup-Strategie) abgeschlossen  
> **Ersteller:** Kilo (KI-Assistent)  
> **Datum:** 2026-05-15  

---

## Kontext

Nach Abschluss einer Debatte liegt das Ergebnis als strukturiertes JSON in `data/debates/<debate_id>.json` vor. Es enthält Titel, Falltext, alle Runden mit Agent-Aussagen, den finalen Konsensgrad und (seit Sprint 18) auch eine Audit-Trail-Historie. Der Nutzer kann die Debatte aktuell als PDF/MD exportieren — muss aber den Inhalt manuell kopieren, um ihn als Grundlage für eine neue Debatte zu nutzen.

Die folgende Implementierung automatisiert diesen Prozess und fügt das System nahtlos neue Funktionen hinzu.

---

## Vorschläge P0–P4

### P0 — "Continue Debate" (Direkte Fortsetzung) — **MVP**

**Ziel:** Der Nutzer kann eine abgeschlossene Debatte direkt fortsetzen. Die bisherigen Ergebnisse werden als Kontext in den Falltext der neuen Debatte eingefügt.

#### Backend

##### 1. Neuer API-Endpoint

```
POST /api/v1/debate/{debate_id}/continue
```

**Request-Body:**
```json
{
  "new_title": "Fortsetzung: ...",
  "focus_topic": "Vertiefung des Konsenspunkts X"
}
```

**Response:**
```json
{
  "debate_id": "neue-uuid",
  "title": "Fortsetzung: ...",
  "case_text": "..."
}
```

##### 2. Service-Schicht (`debate_workflow.py`)

```python
def build_followup_case(debate_id: str, focus_topic: str | None = None) -> str:
    """Baut einen neuen case_text aus den Ergebnissen der Vordebatte."""
    debate = debate_store.get(debate_id)
    transcript = report_generator._build_transcript(debate)

    # Die stärksten Argumente pro Rolle extrahieren
    summaries = []
    for round_data in transcript["rounds"]:
        for output in round_data["agent_outputs"]:
            if output.get("role") in ("strategist", "moderator"):
                summaries.append(f"[{output['role']}]: {output['content'][:250]}")

    prompt = (
        f"Kontext aus der vorherigen Debatte (ID: {debate_id}):\n\n"
        f"Die Debatte '{debate['title']}' wurde nach "
        f"{transcript['current_round']} Runden mit einem "
        f"Konsensgrad von {transcript['final_consensus']*100:.0f}% abgeschlossen.\n\n"
        f"Wichtigste Argumente:\n"
        + "\n\n".join(summaries[-10:])
        + f"\n\nNeuer Fokus: {focus_topic or 'Vertiefung des Themas'}\n\n"
        "Führe diese Debatte fort und baue auf den vorherigen Ergebnissen auf."
    )
    return prompt
```

##### 3. Endpoint-Handler (`config.py` oder neuer Router `debate`)

```python
@router.post("/debate/{debate_id}/continue", response_model=dict)
def continue_debate(
    debate_id: str,
    body: DebateContinueBody,
):
    """Startet eine neue Debatte basierend auf einer abgeschlossenen."""
    followup_prompt = build_followup_case(debate_id, body.focus_topic)

    # Original-Debatte als Referenz beibehalten
    new_case = {
        "text": followup_prompt,
    }

    # ... Standard-DebateCreateRequest mit vorbefüllten Einstellungen
    # (gleiche Agent-Personas, LLM-Profil, Prompt-Variant, Sprache)
```

##### 4. Neues Pydantic-Modell

```python
class DebateContinueBody(BaseModel):
    new_title: str | None = None
    focus_topic: str | None = None
```

#### Frontend (`ConfigView.svelte` und `DebateView.svelte`)

- **Neuer Button:** "Debatte fortsetzen" neben dem Löschen-Button in der Backup/Transcript-Ansicht
- **Modal:** Optionales Eingabefeld für Fokus-Thema
- **API-Call:** `continueDebate(debateId, { focus_topic })` → leitet zur neuen Debatte weiter

#### Akzeptanzkriterien (P0)

- [x] "Debatte fortsetzen"-Button erscheint nur bei `status: completed`
- [x] Neue Debatte erhält den Kontext als Falltext
- [x] Agent-Personas und LLM-Profil werden vom Original übernommen (editierbar)
- [x] Debatte startet sofort im `init`-Status

---

### P1 — Strukturierter Prompt für Follow-up-Debatten

**Ziel:** Die Qualität der Fortführung steigt, wenn das LLM klare Anweisungen zur Nutzung des Kontexts erhält.

#### Backend (`debate_workflow.py`)

```python
def build_followup_prompt(previous_debate: dict, new_topic: str) -> str:
    """Erstellt einen strukturierten Prompt mit Rollen-Anweisungen."""

    # Extrahiere die stärksten Argumente pro Rolle
    strongest = {}
    for round_data in previous_debate.get("rounds", []):
        for output in round_data.get("agent_outputs", []):
            role = output.get("role", "unknown")
            if role not in strongest:
                strongest[role] = []
            strongest[role].append(output.get("content", "")[:200])

    prompt_parts = [
        f"""Du bist Teil eines Multi-Agenten-Debattensystems.

## Kontext
Eine vorherige Debatte zum Thema "{previous_debate.get('title', '')}" 
wurde nach {previous_debate.get('current_round', '?')} Runden mit einem 
Konsensgrad von {previous_debate.get('final_consensus', 0)*100:.0f}% abgeschlossen.
""",
    ]

    for role, contents in strongest.items():
        prompt_parts.append(f"\n### {role.upper()} — Wichtigste Argumente:\n")
        for c in contents[-3:]:
            prompt_parts.append(f"- {c}")

    prompt_parts.extend([
        f"\n## Neue Aufgabe",
        f"Diskutiere nun: **{new_topic}**",
        "",
        "Richtlinien:",
        "1. Baue auf den vorherigen Erkenntnissen auf",
        "2. Widerlege oder bestätige frühere Schlussfolgerungen",
        "3. Bringe neue Perspektiven ein, die in der Origin-Debatte fehlten",
    ])

    return "\n".join(prompt_parts)
```

#### Akzeptanzkriterien (P1)

- [x] Prompt enthält Rollen-Spezialisierung
- [x] Vorherige Konsenspunkte werden referenziert
- [x] Neue Fragestellung ist klar vom Kontext getrennt
- [x] Prompt-Länge bleibt unter 4.000 Tokens

---

### P2 — "Konsens → Neues Thema" (Ein-Klick-Follow-up)

**Ziel:** Ein Knopfdlick erzeugt eine neue Debatte, die den Konsens der alten als Ausgangspunkt nutzt.

#### Backend

##### 1. Neuer Composite-Endpoint

```
POST /api/v1/debate/{debate_id}/fork-from-consensus
```

**Logik:**
1. Lade Original-Debatte
2. Extrahiere `final_consensus` und top-3-Argumente pro Rolle
3. Generiere Falltext:
   ```
   "Die Debatte über [Titel] ergab als Konsens: [Zusammenfassung]. 
   Erweitere dieses Thema nun in Richtung [neues Thema]."
   ```
4. Erstelle `DebateRequest` mit den gleichen Agent-Personas
5. Starte den Debate-Workflow

##### 2. Zusätzliches Modell

```python
class ForkFromConsensusBody(BaseModel):
    new_title: str
    new_topic: str
    max_rounds: int = 3
    consensus_threshold: float = 0.8
```

#### Frontend

- **Neuer Button:** "Neue Debatte aus Konsens" (nur bei completed-Debatten)
- **Modal:** Eingabefelder für neuen Titel + Thema
- **Option:** "Gleiche Agenten & LLMs übernehmen" (Toggle)

#### Akzeptanzkriterien (P2)

- [x] Ein-Klick-Erstellung einer Folge-Debatte
- [x] Konsens-Wert wird im neuen Falltext referenziert
- [x] Agent-Zuordnung ist optional mit einem Klick übertragbar
- [x] Neue Debatte erscheint in der Projekt-Liste

---

### P3 — RAG-Integration vorheriger Debattenergebnisse

**Ziel:** Ergebnisse abgeschlossener Debatten stehen automatisch als RAG-Kontext für neue Debatten zur Verfügung.

#### Backend

##### 1. Automatisches Dokument bei Debate-Abschluss

Erweitere `debate_workflow.py` — Callback nach `completed`-Status:

```python
async def on_debate_completed(debate_id: str, project_id: str):
    """Erzeugt automatisch ein DMS-Dokument mit den Debattenergebnissen."""
    debate = debate_store.get(debate_id)
    transcript = report_generator._build_transcript(debate)

    document_text = generate_rag_friendly_summary(transcript)

    # DMS: Dokument erstellen mit Typ "debate_result"
    doc_id = await dms_service.create_document(
        project_id=project_id,
        title=f"Debatte: {debate['title']}",
        content=document_text,
        doc_type="debate_result",
        metadata={
            "source_debate_id": debate_id,
            "consensus_score": transcript["final_consensus"],
            "num_rounds": transcript["current_round"],
        },
    )
    return doc_id
```

##### 2. RAG-Kontext-Erweiterung

```python
def resolve_rag_context(
    project_id: str,
    case_text: str,
    document_ids=None, rag_auto_retrieve=False,
    include_debate_results: bool = True,
):
    """Erweitert RAG-Kontext um vorherige Debattenergebnisse."""
    all_chunks = []

    # ... bestehende RAG-Logik ...

    # Zusätzlich: Debattenergebnisse als Kontext einbeziehen
    if include_debate_results:
        debate_docs = dms_service.get_documents_by_type(project_id, "debate_result")
        for doc in debate_docs[:5]:  # Max. 5 vorherige Ergebnisse
            chunks = dms_service.metadata_index.get_chunks_by_document(doc["id"])
            all_chunks.extend(chunks[:3])

    return "\n\n---\n\n".join(all_chunks), len(all_chunks)
```

##### 3. Frontend-Toggle

- **Checkbox** im "Neue Debatte"-Dialog: "Ergebnisse vorheriger Debatten als Kontext einbeziehen"
- Default: `true` bei Projekten mit > 2 abgeschlossenen Debatten

#### Akzeptanzkriterien (P3)

- [x] Automatische Dokument-Erstellung bei Debate-Abschluss
- [x] Dokumente sind über DMS abrufbar und versioniert
- [x] RAG-Kontext enthält bis zu 5 vorherige Ergebnisse
- [x] Toggle im Frontend funktioniert korrekt
- [x] Keine Verdopplung — gleiche Debate-ID nicht zweimal als Quelle

---

### P4 — "Fork Debate" (Debatte forken)

**Ziel:** Erstelle eine exakte Kopie einer Debatte an einem bestimmten Zeitpunkt, mit der Möglichkeit, ab einer bestimmten Runde neu zu starten.

#### Datenmodell-Erweiterung

```python
class DebateState(BaseModel):
    parent_debate_id: str | None = None
    fork_round: int | None = None
    fork_reason: str | None = None  # enum: "consensus_breakdown", "new_perspective", "branching"
```

#### Backend

##### 1. Fork-Endpoint

```
POST /api/v1/debate/{debate_id}/fork
```

**Anfrage:**
```json
{
  "new_title": "Gegen-Debatte: ...",
  "fork_from_round": 2,
  "fork_reason": "new_perspective",
  "modified_personas": {
    "critic": "neue-persona-id"
  },
  "modified_prompt_variant": "variant-id"
}
```

**Logik:**
1. Lade Original-Debatte
2. Erstelle Deep-Copy mit neuer `debate_id`
3. Setze `parent_debate_id` und `fork_round`
4. Falls `fork_from_round` angegeben: Entferne alle Runden > fork_from_round
5. Falls `modified_personas`: Ersetze Personas
6. Falls `modified_prompt_variant`: Ersetze Prompt-Variante
7. Speichere als neue Debatte im `created`-Status

##### 2. Fork-Historie (optional)

Füge jedem Debate-Objekt ein Feld hinzu:
```json
{
  "fork_history": [
    {"parent_id": "deb-001", "fork_round": 2, "reason": "new_perspective"},
    {"parent_id": "deb-001", "fork_round": 1, "reason": "consensus_breakdown"},
  ]
}
```

#### Frontend

- **Dropdown-Button** neben dem "Fortsetzen"-Button
- **Modal** mit Optionen:
  - Ab welcher Runde forken? (Dropdown: Runde 1 bis N)
  - Neue Agent-Personas zuweisen (optional)
  - Andere Prompt-Variante wählen (optional)
  - Fork-Grund (Dropdown)

#### Akzeptanzkriterien (P4)

- [x] "Fork"-Button nur bei completed-Debatten
- [x] Auswahl der Fork-Runde funktioniert
- [x] Agent-Persona-Ersetzung funktioniert
- [x] Prompt-Variante ist änderbar
- [x] Fork erzeugt eine editierbare Kopie
- [x] Verknüpfung zum Original ist in der Detailansicht sichtbar

---

## API-Übersicht (neue Endpunkte)

| Methode | Endpoint | Beschreibung | Plan |
|---------|----------|-------------|------|
| `POST` | `/api/v1/debate/{id}/continue` | Neue Debatte mit Kontext aus Vordebatte | P0 |
| `POST` | `/api/v1/debate/{id}/fork-from-consensus` | Ein-Klick-Follow-up aus Konsens | P2 |
| `POST` | `/api/v1/debate/{id}/fork` | Fork mit modifizierten Parametern | P4 |
| `POST` | `/api/v1/debate/on-completed` | Interner Hook: DMS-Dokument erstellen | P3 |

## Datenmodell-Erweiterungen

| Tabelle/Datei | Änderung | Plan |
|---------------|----------|------|
| `Debate`-SQLAlchemy-Modell | `parent_debate_id`, `fork_round`, `fork_reason` | P4 |
| `Debate.debate_json` | `fork_history`-Array | P4 |
| `debate_store.py` | `list_by_parent(debate_id)` — Abfrage aller Forks | P4 |
| DMS-Metadaten | `debate_result` als `doc_type` | P3 |

## Frontend-Komponenten

| Komponente | Datei | Änderung | Plan |
|------------|-------|----------|------|
| `DebateView.svelte` | Button "Fortsetzen" + "Fork"-Dropdown | Neue Aktions-Buttons | P0, P4 |
| `DebateCreatePanel.svelte` | Checkbox "Vorherige Ergebnisse als Kontext" | RAG-Toggle | P3 |
| `DebateList.svelte` | Spalte "Forks" + Link | Anzeige der Fork-Historie | P4 |
| `api.js` | Neue Funktionen | `continueDebate`, `forkDebate`, `createFromConsensus` | P0–P4 |

## Umsetzungsreihenfolge

```
Sprint N+1:   P0 + P1  (Grundfunktionalität + Prompt-Qualität)
Sprint N+2:   P2 + P3  (Ein-Klick + RAG-Integration)
Sprint N+3:   P4       (Fork-System)
```

## Risiken & Hinweise

1. **Token-Limits:** Fortsetzungs-Prompts können lang werden. Token-Budget prüfen und ggf. ältere Runden zusammenfassen.
2. **Datenspeicherung:** Automatische DMS-Dokumente (P3) erhöhen den Speicherbedarf. Cleanup-Retention-Policy aus Plan 18 nutzen.
3. **Versionierung:** Fork-Debatten teilen initial das gleiche JSON — Copy-on-Write bei der ersten Änderung implementieren (analog zu Git).
4. **Zirkuläre Referenzen:** Verhindern, dass eine Debatte als Vorfahre von sich selbst dient (Guard im Backend).

---

*Erstellt am 2026-05-15 als Nachfolger von Plan 18 (Backup-Strategie).*
