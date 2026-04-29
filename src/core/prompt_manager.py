import re
import yaml
import hashlib
import threading
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PromptManager:
    def __init__(self, config_path: Path = Path("config/prompt_variants.yaml")):
        self.config_path = config_path
        self.config_dir = config_path.parent
        self.cache: Dict[str, Dict] = {}
        self.lock = threading.RLock()
        self.variants_config = {}
        self.default_variant = "A"
        self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Prompt-Varianten-Konfig nicht gefunden: {self.config_path}")
        with open(self.config_path, encoding="utf-8") as f:
            self.variants_config = yaml.safe_load(f)
        self.default_variant = self.variants_config.get("default_variant", "A")
        logger.info(f"📜 Prompt-Varianten geladen: {list(self.variants_config.get('variants', {}).keys())}")

    def _parse_prompt(self, rel_path: str) -> Dict:
        path = self.config_dir / rel_path
        if not path.exists():
            raise FileNotFoundError(f"Prompt-Datei fehlt: {path}")
        content = path.read_text(encoding="utf-8")
        m = re.search(r"^version:\s*([v\w.-]+)", content, re.MULTILINE)
        version = m.group(1) if m else "unversioned"
        return {
            "content": content,
            "version": version,
            "hash": hashlib.sha256(content.encode()).hexdigest()[:16],
            "mtime": path.stat().st_mtime,
            "path": str(path)
        }

    def get(self, role: str, variant: Optional[str] = None) -> Dict:
        variant = variant or self.default_variant
        try:
            rel_path = self.variants_config["variants"][variant][role]
        except KeyError:
            raise ValueError(f"Kein Prompt-Mapping für role={role}, variant={variant}")

        cache_key = f"{role}_{variant}"
        target = self.config_dir / rel_path
        current_mtime = target.stat().st_mtime if target.exists() else 0

        with self.lock:
            cached = self.cache.get(cache_key)
            if cached and cached["mtime"] == current_mtime:
                return cached
            # Hot-Reload bei mtime-Änderung oder fehlendem Cache
            new_data = self._parse_prompt(rel_path)
            self.cache[cache_key] = new_data
            logger.info(f"🔄 Hot-Reload: {role} ({variant})")
            return new_data

    def assign_variant(self, session_id: str) -> str:
        """Deterministische, reproduzierbare Zuweisung via Hash"""
        variants = list(self.variants_config.get("variants", {}).keys())
        if not variants:
            return getattr(self, 'default_variant', 'A')
        idx = int(hashlib.md5(session_id.encode()).hexdigest(), 16) % len(variants)
        return variants[idx]

    def get_system_prompt(
        self,
        role: str,
        variant: Optional[str] = None,
        rag_context: Optional[str] = None
    ) -> str:
        if rag_context and rag_context.strip() and "dms" in self.variants_config.get("variants", {}):
            variant = "dms"
        prompt_data = self.get(role, variant)
        content = prompt_data["content"]
        if rag_context and rag_context.strip():
            rag_section = f"\n\n## Retrieved Document Context\n{rag_context}\n\nUse the provided RAG context to inform your argument."
            content += rag_section
        return content