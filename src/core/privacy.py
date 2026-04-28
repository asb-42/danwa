import re
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# DSGVO-konforme PII-Regex (erweiterbar)
PII_PATTERNS = {
    "email": re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'),
    "ipv4": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    "phone_de": re.compile(r'(\+49|0049|0)[\s\-/]?(\(0\))?[\s\-/]?[1-9]\d{1,4}[\s\-/]?\d{3,9}'),
    "id_number": re.compile(r'\b[A-Z]{1,2}\d{6,9}[A-Z]?\b'),  # DE Personalausweis/Pass-Schema
}

class PrivacyGuard:
    def __init__(self, strict_mode: bool = False, retention_days: int = 90, redact_traces: bool = False):
        self.strict_mode = strict_mode
        self.retention_days = retention_days
        self.redact_traces = redact_traces

    def redact_text(self, text: str) -> str:
        """Ersetzt PII durch Platzhalter. Idempotent & sicher für Logs/Traces."""
        for name, pattern in PII_PATTERNS.items():
            text = pattern.sub(f"[REDACTED_{name.upper()}]", text)
        return text

    def enforce_retention(self, base_dir: str = "."):
        """Löscht Logs/Reports/Memory älter als retention_days."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for dir_name in ["logs", "reports", "memory/chroma_db"]:
            path = Path(base_dir) / dir_name
            if not path.exists(): continue
            for item in path.iterdir():
                if item.is_file() and datetime.fromtimestamp(item.stat().st_mtime) < cutoff:
                    item.unlink()
                    logger.info(f"🗑️ Retention: {item} gelöscht")
        logger.info(f"🛡️ Retention-Prüfung abgeschlossen ( cutoff: {cutoff.isoformat()} )")