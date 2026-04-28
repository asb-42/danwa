import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .debate_engine import DebateState

logger = logging.getLogger(__name__)
DB_PATH = Path("memory/debates.db")

class SessionDB:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT,
                profile TEXT,
                max_rounds INTEGER,
                consensus REAL,
                context_preview TEXT,
                trace_path TEXT,
                report_docx TEXT,
                report_pdf TEXT,
                validated INTEGER
            )
        """)
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        cursor = self.conn.execute("PRAGMA table_info(sessions)")
        existing = {row[1] for row in cursor.fetchall()}
        for col in ("project_id TEXT", "document_ids TEXT"):
            name = col.split()[0]
            if name not in existing:
                self.conn.execute(f"ALTER TABLE sessions ADD COLUMN {col}")
        self.conn.commit()

    def save_session(self, state: DebateState, profile: str, 
                     trace_path: str = "", report_docx: str = "", report_pdf: str = ""):
        self.conn.execute("""
            INSERT OR REPLACE INTO sessions 
            (session_id, created_at, profile, max_rounds, consensus, context_preview, trace_path, report_docx, report_pdf, validated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state.session_id, state.created_at, profile, len(state.rounds),
            state.final_consensus, state.context[:150].replace("\n", " "),
            trace_path, report_docx, report_pdf, 1 if state.validation_report else 0
        ))
        self.conn.commit()

    def list_sessions(self, limit=10, offset=0, min_consensus: Optional[float] = None) -> List[Dict]:
        base = "SELECT * FROM sessions"
        where = " WHERE consensus >= ?" if min_consensus is not None else ""
        order = " ORDER BY created_at DESC"
        lim = " LIMIT ? OFFSET ?"
        
        params = [min_consensus] if min_consensus is not None else []
        params += [limit, offset]
        
        cursor = self.conn.execute(f"{base}{where}{order}{lim}", params)
        return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()
        logger.info(f"🗑️ DB-Eintrag gelöscht: {session_id}")
        return True

    def cleanup_old_entries(self, days: int = 90) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        res = self.conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
        self.conn.commit()
        deleted = res.rowcount
        if deleted:
            logger.info(f"🧹 DB-Cleanup: {deleted} alte Einträge entfernt (>{days} Tage)")
        return deleted

    def close(self):
        self.conn.close()