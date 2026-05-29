# RAG-System Stabilisierung — Analyse & Fixes

**Datum:** 2026-05-29  
**Scope:** DMS → Chunking → Vektorspeicher → RAG-Auflösung → Agent-Prompt-Injection  
**Status:** Analyse abgeschlossen, Fixes implementiert

---

## 1. Datenfluss-Übersicht

```
Upload → DMS.upload_document()
  → DocumentProcessor.process_file() (Text-Extraktion, optional OCR)
  → TextChunker.chunk() (tiktoken, 512 Tokens, 51 Overlap)
  → DMSVectorStore.add_chunks() (ChromaDB, pro Projekt isoliert)
  → DMSDB.add_chunk() (SQLite, pro Projekt isoliert)

Debate Start → resolve_rag_context()
  → get_dms_for_project() (pro Projekt DMS-Instance)
  → metadata_index.get_chunks_by_document() ODER auto_retrieve_for_topic()
  → RAGContextFormatter.format() (max 50K Zeichen)
  → state["rag_context"]

Agent Node → agent_node_factory()
  → user_prompt += "\n\n--- DOCUMENT CONTEXT ---\n{rag_context}"
```

---

## 2. Projekt-Isolation (Spillover-Analyse)

| Schicht | Isolationsmechanismus | Status |
|---------|----------------------|--------|
| ChromaDB-Speicher | Separates `chroma_db`-Verzeichnis pro Projekt | ✅ Solid |
| Vektorsuche | `where={"project_id": ...}` Filter | ✅ Solid |
| SQLite-DB | Separate `dms.db` pro Projekt | ✅ Solid |
| DMS-Instanzen | Gecacht pro `project_id` in `_dms_cache` | ✅ Solid |
| Dokumentenanalyse | Projekt-Level-Datei (geteilt zwischen Debatten) | ⚠️ Cross-Debate-Leak |
| Debate-Results-RAG | Projekt-scoped DebateStore | ⚠️ Default-Store-Fallback |

**Fazit:** Cross-Projekt-Isolation ist solid. Cross-Debate-Leak innerhalb desselben Projekts via Dokumentenanalyse ist der Hauptkritikpunkt.

---

## 3. Identifizierte Probleme

### BUG 1 (HIGH): `resolve_rag_context_with_debate_results` ignoriert übergebenen `project_store`

**Datei:** `debate_rag.py:245-253`

```python
if store is None:
    store = DebateStore()  # ← Default Store, nicht projekt-scoped

ps = ProjectStore()  # ← Erstellt neuen Default statt übergebenen zu nutzen
project_dir = ps.get_project_dir(project_id)
```

Die Funktion erstellt einen neuen `ProjectStore()` statt den übergebenen Parameter zu nutzen. Wenn ein custom `project_store` übergeben wird, wird er ignoriert.

### BUG 2 (HIGH): Stiller Fehler wenn Dokumente nicht indexiert sind

**Datei:** `debate_rag.py:102-106`

```python
if not all_chunks:
    logger.warning("Explicit document_ids %s returned zero chunks ...")
```

Wenn ChromaDB-Indexierung fehlgeschlagen ist (z.B. Processing-Timeout), wird die Debatte **ohne RAG-Kontext** fortgesetzt. Der User sieht keinen Fehler.

### BUG 3 (MEDIUM): 200K Zeichen-Limit für explizite Dokumente zu hoch

**Datei:** `debate_rag.py:181`

```python
rag_context = dms.format_rag_context(unique_chunks, max_chars=200_000)
```

200K Zeichen ≈ 50K Tokens. Für Modelle mit 32K oder 128K Kontextfenster bleibt zu wenig Raum für System-Prompt + User-Prompt + Agent-Output.

### BUG 4 (MEDIUM): BM25-Korpus wird pro Query geladen

**Datei:** `hybrid_retriever.py:82-84`

```python
def _fetch_chunks(self, project_id):
    return self.metadata_index.get_chunks_by_project(project_id)
```

Jede Suche lädt alle Projekt-Chunks in den Speicher. Kein Caching. O(n) Speicher- und CPU-Kosten pro Query.

### BUG 5 (LOW): BM25 verwendet Whitespace-Tokenisierung

**Datei:** `hybrid_retriever.py:111`

```python
tokenized_corpus = [text.split() for text in corpus]
```

Einfache `str.split()` Tokenisierung. Keine Stopwort-Entfernung, kein Stemming, keine Kleinschreibung. Für deutschen Text mit Komposita ("Rechtsstreitigkeiten") funktioniert die Suche schlecht.

### BUG 6 (LOW): `get_manual_rag_context` ist document-order-biased

**Datei:** `service.py:386-389`

```python
def get_manual_rag_context(self, k: int = 5) -> list[dict]:
    all_chunks = []
    for doc_id in self._manual_rag_docs:
        chunks = self.metadata_index.get_chunks_by_document(doc_id)
        all_chunks.extend(chunks)
    return all_chunks[:k]
```

Nimmt die ersten `k` Chunks sortiert nach `chunk_index`. Bei mehreren Dokumenten werden alle Chunks des ersten Dokuments und keine des zweiten zurückgegeben.

---

## 4. Durchgeführte Fixes

### Fix 1: `resolve_rag_context_with_debate_results` — project_store korrekt nutzen

### Fix 2: Stiller Fehler → Propagation mit Fallback-Text

### Fix 3: Context-Limit auf 80K Zeichen reduziert (≈20K Tokens)

### Fix 4: BM25-Korpus-Cache mit TTL

### Fix 5: BM25-Tokenisierung mit Lowercase + Mindestwortlänge

### Fix 6: Manual RAG Context — round-robin statt document-order

---

## 5. Empfohlene nächste Schritte

1. **Per-Model Context-Awareness:** RAG-Limit dynamisch basierend auf dem verwendeten LLM-Profil setzen
2. **Chunking-Verbesserung:** Sentence-boundary-aware Chunking statt reine Token-Grenzen
3. **Dokumentenanalyse pro Debatte:** Statt projekt-weiter Analyse eine debate-spezifische Version erstellen
4. **BM25 für Deutsch:** `german-stopwords` Paket + Compound-Word-Handling
