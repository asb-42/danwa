import logging
import json
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "src": f"{record.module}:{record.funcName}:{record.lineno}",
            "msg": record.getMessage(),
            "exc": record.exc_text if record.exc_info else None
        }
        return json.dumps(entry, ensure_ascii=False)

def setup_logging(level: str = "INFO"):
    Path("logs").mkdir(exist_ok=True)
    
    fmt = JSONFormatter()
    file_handler = RotatingFileHandler(
        "logs/app.jsonl", maxBytes=10*1024*1024, backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.WARNING)  # Nur Warnungen/Fehler auf Console
    
    logging.basicConfig(level=level, handlers=[file_handler, console])
    
    # Externe Library-Logs eindämmen
    logging.getLogger("litellm").setLevel(logging.WARNING)