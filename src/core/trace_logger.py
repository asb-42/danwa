"""Trace logger — persists full prompt/response pairs for reproducibility.

IMPORTANT: Stores full prompt and response text (not just hashes or previews)
so that complete debate traces can be reconstructed for debugging, auditing,
and replay.
"""

import json
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")


class TraceLogger:
    def __init__(self, session_id: str):
        LOG_DIR.mkdir(exist_ok=True)
        self.file = LOG_DIR / f"{session_id}.jsonl"

    def log(
        self,
        step: str,
        agent: str,
        prompt: str,
        response: str,
        metadata: dict,
        prompt_version: str = "unknown",
        prompt_hash: str = "unknown",
        prompt_variant: str = "A",
    ):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "step": step,
            "agent": agent,
            "prompt_variant": prompt_variant,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "prompt": prompt,
            "response": response,
            "metadata": metadata,
        }
        with open(self.file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_session_log(self):
        if not self.file.exists():
            return []
        with open(self.file, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f]
