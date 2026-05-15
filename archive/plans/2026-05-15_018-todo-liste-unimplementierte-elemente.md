# To-do-Liste — Noch nicht implementierte Elemente

> Automatisch generiert durch Code-Analyse der gesamten Code-Basis.
> Stand: 2026-05-15 (nach `git pull` von `origin/main`)

---

## 🔴 Hohe Priorität (Core-Funktionalität fehlt)

### 1. MCP Input Plugin — komplett als Stub
- **Datei:** `backend/services/input/plugins/mcp_plugin.py`
- **Status:** `capture()` wirft immer `NotImplementedError`, `validate()` gibt immer `False` zurück, `is_available: false`
- **Beschreibung:** Das MCP (Model Context Protocol)-Plugin ist als Platzhalter implementiert. Es gibt kein funktionierendes Backend für MCP-Server/Client-Integration. Das Frontend zeigt eine Info-Box "MCP Stub" an (s. Punkt 11).
- **Aufwand:** Hoch — erfordert MCP-Protokoll-Implementierung (Server- und Client-Seite)

### 2. MetaWorkflowService — nur Dummy-Proposals
- **Datei:** `backend/services/meta_workflow.py`
- **Status:** `generate_proposal()` erzeugt statische Dummy-Texte ohne LLM-Analyse
- **Beschreibung:** Der Service soll in Zukunft eine LLM-gestützte Analyse des `DebateArtifact` durchführen und konkrete Workflow-Verbesserungen vorschlagen. Aktuell wird nur ein Platzhalter-Proposal mit hartcodiertem Text erzeugt.
- **Aufwand:** Hoch — erfordert LLM-Integration und Prompt-Engineering für Meta-Analyse

### 3. Consensus-Berechnung — lineare Heuristik statt LLM
- **Datei:** `backend/workflow/nodes.py`, Zeile ~635
- **Status:** `TODO: Replace with LLM-based consensus evaluation in a future sprint.`
- **Beschreibung:** Die aktuelle Konsensberechnung ist eine einfache lineare Progression (`current_round / max_rounds * threshold * 1.2`). Der Moderator-Agent soll in Zukunft die tatsächliche Konsensberechnung durchführen.
- **Aufwand:** Mittel — LLM-Call für Consensus-Scoring einbauen

### 4. STT Cloud-Provider nicht implementiert
- **Datei:** `backend/services/stt_service.py`
- **Status:** Nur `whisper-local` funktioniert. Cloud-Provider (`whisper-api`, `azure-stt`, `google-stt`) lösen `RuntimeError` aus.
- **Beschreibung:** Die Klasse `STTService` wirft für Cloud-Provider einen Fehler. Diese müssen implementiert werden.
- **Aufwand:** Mittel — API-Integration für jeden Cloud-Provider

---

## 🟡 Mittel-Priorität (Fehlende Integrationen & Features)

### 5. Optimierungsvorschläge — Benutzerkontext fehlt
- **Datei:** `backend/api/routers/optimization_proposals.py`, Zeile 238
- **Status:** `approved_by="user"` ist hartcodiert, sollte aus dem Auth-Kontext kommen (`# TODO: get from auth context`)
- **Beschreibung:** Das System hat keine Authentifizierung implementiert. Der `approved_by`-Wert ist ein Placeholder.
- **Aufwand:** Mittel — Authentifizierungssystem einbauen

### 6. TTS Script Engine — nur teilweise implementiert
- **Datei:** `backend/services/output/plugins/tts_script_engine.py`
- **Status:** Enthält nur leere Platzhalter-Methoden (`pass`), keine `render()`, `synthesize()` oder `list_voices()`-Methoden
- **Beschreibung:** Die Script-Engine für TTS wurde als Stub angelegt. STT-Plugins funktionieren, aber die Skriptverarbeitung fehlt.
- **Aufwand:** Mittel — muss implementiert werden für komplexe TTS-Produktionen

### 7. HITL-Workflow-Graph — ✅ implementiert
- **Datei:** `backend/workflow/hitl/graph.py` und `backend/workflow/hitl/nodes.py`
- **Status:** `extension_request_node` und `initialize_node` wurden implementiert und ausgerollt. `extension_request_node` wartet jetzt auf User-Antwort, wertet sie aus, und setzt `extension_granted` im State, damit die Routing-Funktion korrekt weiterläuft oder beendet.
- **Änderungen:**
  - `extension_request_node`: Wartet auf User-Antwort, erkennt Grant/Deny anhand von Schlüsselwörtern, setzt `extension_granted` im State
  - `initialize_node`: HITL-Felder (`hitl_enabled`, `hitl_mode`, `round_interrupt_count`, etc.) mit sicheren Defaults befüllt
  - `debate_id`-Inkonsistenz behoben: `session_id` wird einheitlich als `debate_id` verwendet
  - Timeout-Fallback: Extension wird bei Timeout verweigert
- **Verbleibend:** Integrationstest, Frontend-Anbindung für Extension-Antworten

### 8. AuthContext / Authentifizierungssystem
- **Datei:** `backend/api/routers/optimization_proposals.py`, diverse Stellen
- **Status:** System hat kein Benutzer-Authentifizierungssystem; `approved_by` und Audit-Logs verwenden hartcodierte Werte
- **Beschreibung:** Für Produktionsbetrieb ist Authentifizierung zwingend erforderlich.
- **Aufwand:** Hoch — umfassendes Auth-System nötig

---

## 🟢 Niedrige Priorität (Klempnerarbeit & Cleanup)

### 9. Veraltete Engine v1 — noch im Repository
- **Datei:** `src/core/debate_engine.py_v1`
- **Status:** Alte Engine-Version (ca. 72 Zeilen) existiert noch im Codebase, wird aber nicht referenziert
- **Beschreibung:** Legacy-Code der entfernt werden kann, nachdem bestätigt wurde, dass keine Abhängigkeiten mehr bestehen.
- **Aufwand:** Gering — Entfernen nach Verifikation

### 10. pass-Anweisungen in Exception-Handlern — ✅ korrigiert (12 Stellen)
- **Dateien:** 10 Dateien im `backend/`-Verzeichnis
- **Status:** Alle `pass`-Statements in Exception-Handlern wurden durch sinnvolles Logging ersetzt. Einrückungsfehler in 5 Dateien korrigiert.
- **Details:**
  - `backend/services/debate_workflow.py` — `build_rag_preview` Fehler geloggt
  - `backend/services/translation_service.py` — SQLite-Cache-Update Fehler geloggt
  - `backend/modules/installer.py` — Dependency-Check + Manifest-Lese Fehler geloggt
  - `backend/modules/service.py` — Modul-Registry Fehler geloggt
  - `backend/api/routers/debate.py` — LLM-Profil-Auflösung gewarnt
  - `backend/api/routers/dms.py` — OCR-Engine-Fallback debug-geloggt
  - `backend/persistence/project_store.py` — Datetime-Parsing debug-geloggt
  - `backend/persistence/debate_store.py` — Status-Normalisierung debug-geloggt
  - `backend/services/prompt_service.py` — Prompt-Template-Fallback debug-geloggt
  - `backend/workflow/nodes.py` — LLM-Profil-Auswahl debug-geloggt

### 11. Frontend: MCP-Info-Box ist statisch
- **Datei:** `frontend/src/views/InputComposerView.svelte`, Zeile ~377
- **Status:** Zeigt nur den Text "Model Context Protocol integration is available as a stub plugin. Full MCP support will be enabled in a future release."
- **Beschreibung:** Kein funktionaler Inhalt, nur Informationstext.
- **Aufwand:** Gering — entfernt werden, wenn MCP implementiert ist

### 12. Phasen-Kommentare im Frontend
- **Datei:** `frontend/src/views/InputComposerView.svelte`
- **Status:** Kommentare wie "Phase 3: A2A Pending Job Polling", "Phase 4: Pre-select first workflow template if none selected"
- **Beschreibung:** Hinweise auf geplante, aber noch nicht vollständig umgesetzte Features.
- **Aufwand:** Variabel — je nach Featureumfang

---

## 📋 Zusammenfassung

| Kategorie | Anzahl | Geschätzter Aufwand |
|-----------|--------|---------------------|
| 🔴 Hohe Priorität | 4 | Hoch |
| 🟡 Mittel-Priorität | 4 | Mittel |
| 🟢 Niedrige Priorität | 4 | Gering |
| **Gesamt** | **12** | — |

### Top-3 dringendste Aufgaben:
1. **MCP Plugin implementieren** — Integration mit externen MCP-Servern
2. **MetaWorkflowService mit LLM** — echte Workflow-Optimierungsvorschläge
3. **Consensus-Berechnung verbessern** — LLM-basierte statt linearer Heuristik