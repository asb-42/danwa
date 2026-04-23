import hashlib
import re
from pathlib import Path
from typing import Tuple

class PromptRegistry:
    def __init__(self, prompt_dir: Path):
        self.dir = prompt_dir

    def load(self, role: str) -> Tuple[str, str, str]:
        """Lädt Prompt, extrahiert Version (YAML-Frontmatter oder Default), berechnet SHA256-Hash"""
        path = self.dir / f"{role}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt nicht gefunden: {path}")
        
        content = path.read_text(encoding="utf-8")
        
        # Version aus Frontmatter oder Fallback
        version_match = re.search(r"^version:\s*([v\w.-]+)", content, re.MULTILINE)
        version = version_match.group(1) if version_match else "unversioned"
        
        # Kurz-Hash für Trace
        prompt_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        
        return content, version, prompt_hash