import os
import logging
from pathlib import Path
from typing import List
import chromadb.api.types
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class DomainEmbeddingFunction(chromadb.api.types.EmbeddingFunction):
    """
    Lädt ein domain-spezifisches Embedding-Modell. 
    Optimiert für deutsche/rechtliche Texte (E5-Architektur).
    """
    def __init__(
        self, 
        model_name: str = "intfloat/multilingual-e5-small",
        cache_dir: str = "memory/embeddings"
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(self.cache_dir)
        
        # E5-Modelle benötigen Prefixes für optimale Retrieval-Performance
        self.requires_prefix = "e5" in model_name.lower()
        
        try:
            logger.info(f"📥 Lade Embedding-Modell: {model_name} (CPU)")
            self.model = SentenceTransformer(
                model_name, 
                cache_folder=str(self.cache_dir), 
                device="cpu",
                trust_remote_code=True
            )
            # Normalisierung für Cosine-Similarity
            self.model.to(device="cpu")
            logger.info("✅ Embedding-Modell erfolgreich geladen & cached")
        except Exception as e:
            logger.error(f"⚠️ Embedding-Modell fehlgeschlagen: {e}")
            self.model = None

    def __call__(self, input: List[str]) -> List[List[float]]:
        if self.model is None:
            raise RuntimeError("Embedding-Modell nicht geladen. Prüfe logs/ oder nutze Default-Embeddings.")
            
        texts = input
        if self.requires_prefix:
            # E5-Konvention: Alle Inputs als "query:" prefixen für konsistente Vektorräume
            texts = [f"query: {t}" for t in input]
            
        embeddings = self.model.encode(
            texts, 
            convert_to_numpy=True, 
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings.tolist()