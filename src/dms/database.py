import sqlite3
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
DB_PATH = Path("memory/dms.db")


class DMSDB:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT,
                metadata_json TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                filename TEXT,
                file_path TEXT,
                file_type TEXT,
                page_count INTEGER,
                word_count INTEGER,
                char_count INTEGER,
                uploaded_at TEXT,
                ocr_used INTEGER DEFAULT 0,
                metadata_json TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER,
                text TEXT,
                embedding_id TEXT,
                page INTEGER,
                metadata_json TEXT,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_context (
                session_id TEXT,
                document_id TEXT,
                added_at TEXT,
                PRIMARY KEY(session_id, document_id)
            )
        """)
        self.conn.commit()

    # -- projects --

    def create_project(self, name: str, description: str = "", metadata_json: str = "") -> Dict:
        project_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO projects (id, name, description, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, description, now, metadata_json),
        )
        self.conn.commit()
        return self.get_project(project_id)  # type: ignore[return-value]

    def get_project(self, project_id: str) -> Optional[Dict]:
        cursor = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_projects(self) -> List[Dict]:
        cursor = self.conn.execute("SELECT * FROM projects ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def delete_project(self, project_id: str) -> bool:
        self.conn.execute("DELETE FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE project_id = ?)", (project_id,))
        self.conn.execute("DELETE FROM documents WHERE project_id = ?", (project_id,))
        self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.conn.commit()
        return True

    # -- documents --

    def add_document(
        self,
        project_id: str,
        filename: str,
        file_path: str = "",
        file_type: str = "",
        page_count: int = 0,
        word_count: int = 0,
        char_count: int = 0,
        ocr_used: bool = False,
        metadata_json: str = "",
    ) -> Dict:
        doc_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO documents 
            (id, project_id, filename, file_path, file_type, page_count, word_count, char_count, uploaded_at, ocr_used, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, project_id, filename, file_path, file_type, page_count, word_count, char_count, now, int(ocr_used), metadata_json),
        )
        self.conn.commit()
        return self.get_document(doc_id)  # type: ignore[return-value]

    def get_document(self, doc_id: str) -> Optional[Dict]:
        cursor = self.conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_documents(self, project_id: str) -> List[Dict]:
        cursor = self.conn.execute("SELECT * FROM documents WHERE project_id = ? ORDER BY uploaded_at DESC", (project_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_document(self, doc_id: str) -> bool:
        self.conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        self.conn.commit()
        return True

    # -- document_chunks --

    def add_chunk(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        embedding_id: str = "",
        page: int = 0,
        metadata_json: str = "",
    ) -> Dict:
        chunk_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            """INSERT INTO document_chunks 
            (id, document_id, chunk_index, text, embedding_id, page, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chunk_id, document_id, chunk_index, text, embedding_id, page, metadata_json),
        )
        self.conn.commit()
        return {"id": chunk_id, "document_id": document_id, "chunk_index": chunk_index, "text": text, "embedding_id": embedding_id, "page": page, "metadata_json": metadata_json}

    def list_chunks(self, document_id: str) -> List[Dict]:
        cursor = self.conn.execute("SELECT * FROM document_chunks WHERE document_id = ? ORDER BY chunk_index", (document_id,))
        return [dict(row) for row in cursor.fetchall()]

    # -- rag_context --

    def add_rag_context(self, session_id: str, document_id: str) -> Dict:
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO rag_context (session_id, document_id, added_at) VALUES (?, ?, ?)",
            (session_id, document_id, now),
        )
        self.conn.commit()
        return {"session_id": session_id, "document_id": document_id, "added_at": now}

    def list_rag_context(self, session_id: str) -> List[Dict]:
        cursor = self.conn.execute("SELECT * FROM rag_context WHERE session_id = ? ORDER BY added_at", (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def remove_rag_context(self, session_id: str, document_id: str) -> bool:
        self.conn.execute("DELETE FROM rag_context WHERE session_id = ? AND document_id = ?", (session_id, document_id))
        self.conn.commit()
        return True

    def close(self):
        self.conn.close()
