import sqlite3
import logging
import json
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
                     trace_path: str = "", report_docx: str = "", report_pdf: str = "",
                     project_id: str = None, document_ids: List[str] = None):
        proj_id = project_id if project_id is not None else ""
        if document_ids is not None:
            doc_ids_str = json.dumps(document_ids)
        else:
            doc_ids_str = ""
        self.conn.execute("""
            INSERT OR REPLACE INTO sessions 
            (session_id, created_at, profile, max_rounds, consensus, context_preview, trace_path, report_docx, report_pdf, project_id, document_ids, validated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state.session_id, state.created_at, profile, len(state.rounds),
            state.final_consensus, state.context[:150].replace("\n", " "),
            trace_path, report_docx, report_pdf, proj_id, doc_ids_str, 1 if state.validation_report else 0
        ))
        self.conn.commit()

    def load_session(self, session_id: str) -> Optional[Dict]:
        cursor = self.conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        session = dict(row)
        doc_ids_raw = session.get("document_ids", "")
        if doc_ids_raw:
            try:
                session["document_ids"] = json.loads(doc_ids_raw)
            except json.JSONDecodeError:
                session["document_ids"] = []
        else:
            session["document_ids"] = []
        session.setdefault("project_id", None)
        return session

    def list_sessions(self, limit=10, offset=0, min_consensus: Optional[float] = None, project_id: str | None = None) -> List[Dict]:
        base = "SELECT * FROM sessions"
        clauses = []
        params = []
        if min_consensus is not None:
            clauses.append("consensus >= ?")
            params.append(min_consensus)
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order = " ORDER BY created_at DESC"
        lim = " LIMIT ? OFFSET ?"
        
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
