import logging
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import chromadb
from chromadb.config import Settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .debate_engine import DebateState

logger = logging.getLogger(__name__)
MEMORY_DIR = Path("memory")
MEMORY_DIR.mkdir(exist_ok=True)


class DebateMemory:
    def __init__(self, collection_name: str = "debate_precedents"):
        self.client = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma_db"))
        self.collection = self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"📦 Memory geladen: {self.collection.count()} Präzedenzfälle")

    def _format_document(self, state: "DebateState") -> str:
        """Kompakter, semantisch dichter String für Vector-Suche"""
        return (
            f"Thema/Kontext: {state.context[:300].strip()}\n"
            f"Konsens-Score: {state.final_consensus:.2f}\n"
            f"Ergebnis: {state.output[:500].strip()}"
        )

    def store_debate(self, state: "DebateState") -> None:
        if not state.output:
            return
        try:
            self.collection.add(
                documents=[self._format_document(state)],
                metadatas=[
                    {
                        "session_id": state.session_id,
                        "consensus": state.final_consensus,
                        "timestamp": state.created_at,
                        "rounds": len(state.rounds),
                        "validated": bool(state.validation_report),
                    }
                ],
                ids=[state.session_id],
            )
            logger.info(f"💾 Präzedenzfall gespeichert: {state.session_id}")
        except Exception as e:
            logger.error(f"Memory-Speicherung fehlgeschlagen: {e}")

    def search_precedents(self, query: str, top_k: int = 3) -> List[Dict]:
        if self.collection.count() == 0:
            return []
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            precedents = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                precedents.append(
                    {
                        "document": doc,
                        "metadata": meta,
                        "relevance_score": max(
                            0.0, 1.0 - dist
                        ),  # Distance → Similarity
                    }
                )
            return sorted(precedents, key=lambda x: x["relevance_score"], reverse=True)
        except Exception as e:
            logger.warning(f"Memory-Suche fehlgeschlagen: {e}")
            return []
