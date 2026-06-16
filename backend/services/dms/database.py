"""DMS SQLite database — documents, chunks, and RAG context.

Migrated from src/dms/database.py. Now accepts db_path as constructor parameter.
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DMSDB:
    """SQLite-backed storage for DMS documents and chunks."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialise DMSDB."""
        if db_path is None:
            db_path = Path("memory/dms.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        """Init db the instance."""
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
                original_filename TEXT,
                file_path TEXT,
                file_type TEXT,
                file_size INTEGER DEFAULT 0,
                page_count INTEGER,
                word_count INTEGER,
                char_count INTEGER,
                uploaded_at TEXT,
                updated_at TEXT,
                ocr_used INTEGER DEFAULT 0,
                metadata_json TEXT
            )
        """)
        # Migrate existing databases: add columns if missing
        self._migrate_documents_table()
        # Drop the obsolete FK on documents.project_id -- see
        # _drop_documents_project_fk for the rationale.
        self._drop_documents_project_fk()
        # Same dance for the FK on document_chunks.document_id,
        # which after the previous migration can point to a
        # dropped table ("documents__legacy_fk") and therefore
        # breaks every chunk insert.  See _drop_chunks_document_fk.
        self._drop_chunks_document_fk()
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER,
                text TEXT,
                embedding_id TEXT,
                page INTEGER,
                metadata_json TEXT
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

    def _migrate_documents_table(self) -> None:
        """Add missing columns to existing documents table."""
        cursor = self.conn.execute("PRAGMA table_info(documents)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        if "original_filename" not in existing_cols:
            self.conn.execute("ALTER TABLE documents ADD COLUMN original_filename TEXT")
        if "file_size" not in existing_cols:
            self.conn.execute("ALTER TABLE documents ADD COLUMN file_size INTEGER DEFAULT 0")
        if "updated_at" not in existing_cols:
            self.conn.execute("ALTER TABLE documents ADD COLUMN updated_at TEXT")

    def _drop_documents_project_fk(self) -> None:
        """Recreate the documents table without the obsolete FK.

        SQLite does not support ALTER TABLE ... DROP CONSTRAINT, so
        we use the standard create-new / copy / swap / drop recipe.
        The copy preserves every column and every row; only the
        table-level FOREIGN KEY clause is lost.

        The migration is guarded by a sentinel row in a dedicated
        schema_meta table so it runs at most once per DB.
        Idempotent: subsequent invocations are a no-op.
        """
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (  key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            done = self.conn.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                ("drop_documents_project_fk",),
            ).fetchone()
            if done and done["value"] == "1":
                return

            # Detect the FK by inspecting the table SQL. Only
            # proceed to recreate when the legacy constraint is
            # still present -- otherwise the migration is a no-op.
            row = self.conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'documents'").fetchone()
            table_sql = row["sql"] if row else ""
            if "REFERENCES projects(id)" not in (table_sql or ""):
                self.conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                    ("drop_documents_project_fk", "1"),
                )
                self.conn.commit()
                return

            logger.info("Migrating DMS documents table: dropping obsolete FOREIGN KEY(project_id) REFERENCES projects(id)")
            self.conn.execute("PRAGMA foreign_keys = OFF")
            try:
                self.conn.execute("ALTER TABLE documents RENAME TO documents__legacy_fk")
                self.conn.execute(
                    """
                    CREATE TABLE documents (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        filename TEXT,
                        original_filename TEXT,
                        file_path TEXT,
                        file_type TEXT,
                        file_size INTEGER DEFAULT 0,
                        page_count INTEGER,
                        word_count INTEGER,
                        char_count INTEGER,
                        uploaded_at TEXT,
                        updated_at TEXT,
                        ocr_used INTEGER DEFAULT 0,
                        metadata_json TEXT
                    )
                    """
                )
                self.conn.execute("INSERT INTO documents SELECT * FROM documents__legacy_fk")
                self.conn.execute("DROP TABLE documents__legacy_fk")
                self.conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                    ("drop_documents_project_fk", "1"),
                )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            finally:
                self.conn.execute("PRAGMA foreign_keys = ON")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not drop obsolete documents.project_id FK: %s. "
                "Existing DMS databases may continue to reject uploads "
                "until the migration succeeds.",
                exc,
            )

    def _drop_chunks_document_fk(self) -> None:
        """Recreate document_chunks without the obsolete FK.

        SQLite's ALTER TABLE RENAME does NOT update FK references
        in other tables.  After ``_drop_documents_project_fk``
        renames and re-creates ``documents`` (and drops the
        ``documents__legacy_fk`` alias), any pre-existing FK in
        ``document_chunks`` that referenced the old name is now
        dangling -- the table does not exist -- and every chunk
        insert fails with ``no such table: main.documents__legacy_fk``.

        The fix mirrors the documents migration: detect the
        dangling FK by inspecting the table SQL; if it references
        the legacy alias (or any name other than the current
        ``documents``), recreate the table without the FK.  The
        copy preserves every column and every row.

        Idempotent via the same ``schema_meta`` sentinel table.
        """
        try:
            sentinel_key = "drop_chunks_document_fk"
            done = self.conn.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                (sentinel_key,),
            ).fetchone()
            if done and done["value"] == "1":
                return

            row = self.conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'document_chunks'").fetchone()
            table_sql = row["sql"] if row else ""
            needs_fix = "documents__legacy_fk" in (table_sql or "") or "FOREIGN KEY(document_id) REFERENCES documents(id)" in (table_sql or "")
            if not needs_fix:
                self.conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                    (sentinel_key, "1"),
                )
                self.conn.commit()
                return

            logger.info("Migrating DMS document_chunks table: dropping obsolete FOREIGN KEY(document_id) -> documents")
            self.conn.execute("PRAGMA foreign_keys = OFF")
            try:
                self.conn.execute("ALTER TABLE document_chunks RENAME TO document_chunks__legacy_fk")
                self.conn.execute(
                    """
                    CREATE TABLE document_chunks (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        chunk_index INTEGER,
                        text TEXT,
                        embedding_id TEXT,
                        page INTEGER,
                        metadata_json TEXT
                    )
                    """
                )
                self.conn.execute("INSERT INTO document_chunks SELECT * FROM document_chunks__legacy_fk")
                self.conn.execute("DROP TABLE document_chunks__legacy_fk")
                self.conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                    (sentinel_key, "1"),
                )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            finally:
                self.conn.execute("PRAGMA foreign_keys = ON")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not drop obsolete document_chunks.document_id FK: %s. "
                "Existing DMS databases may continue to reject chunk inserts "
                "until the migration succeeds.",
                exc,
            )

    # -- projects --

    def create_project(self, name: str, description: str = "", metadata_json: str = "") -> dict:
        """Create and return a new project."""
        project_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO projects (id, name, description, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, description, now, metadata_json),
        )
        self.conn.commit()
        return self.get_project(project_id)  # type: ignore[return-value]

    def get_project(self, project_id: str) -> dict | None:
        """Retrieve and return project."""
        cursor = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_projects(self) -> list[dict]:
        """Return a list of projects."""
        cursor = self.conn.execute("SELECT * FROM projects ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def delete_project(self, project_id: str) -> bool:
        """Delete project."""
        self.conn.execute(
            "DELETE FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE project_id = ?)",
            (project_id,),
        )
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
        file_size: int = 0,
        original_filename: str = "",
        page_count: int = 0,
        word_count: int = 0,
        char_count: int = 0,
        ocr_used: bool = False,
        metadata_json: str = "",
    ) -> dict:
        """Add document."""
        doc_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        if not original_filename:
            original_filename = filename
        self.conn.execute(
            """INSERT INTO documents
            (id, project_id, filename, original_filename, file_path, file_type, file_size,
             page_count, word_count, char_count, uploaded_at, updated_at, ocr_used, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id,
                project_id,
                filename,
                original_filename,
                file_path,
                file_type,
                file_size,
                page_count,
                word_count,
                char_count,
                now,
                now,
                int(ocr_used),
                metadata_json,
            ),
        )
        self.conn.commit()
        return self.get_document(doc_id)  # type: ignore[return-value]

    def get_document(self, doc_id: str) -> dict | None:
        """Retrieve and return document."""
        cursor = self.conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_documents(self, project_id: str) -> list[dict]:
        """Return a list of documents."""
        cursor = self.conn.execute("SELECT * FROM documents WHERE project_id = ? ORDER BY uploaded_at DESC", (project_id,))
        return [dict(row) for row in cursor.fetchall()]

    def delete_document(self, doc_id: str) -> bool:
        """Delete document."""
        try:
            self.conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
            self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def update_document_metadata(self, doc_id: str, **kwargs) -> None:
        """Update specific metadata fields on a document.

        Allowed fields: updated_at, word_count, char_count, filename, file_size.
        Raises ValueError if no valid fields are provided.
        """
        allowed = {"updated_at", "word_count", "char_count", "filename", "file_size"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [doc_id]
        self.conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", values)
        self.conn.commit()

    def delete_document_chunks(self, doc_id: str) -> None:
        """Delete all chunks for a document (keeps the document record)."""
        self.conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        self.conn.commit()

    # -- document_chunks --

    def add_chunk(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        embedding_id: str = "",
        page: int = 0,
        metadata_json: str = "",
    ) -> dict:
        """Add chunk."""
        chunk_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            """INSERT INTO document_chunks
            (id, document_id, chunk_index, text, embedding_id, page, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chunk_id, document_id, chunk_index, text, embedding_id, page, metadata_json),
        )
        self.conn.commit()
        return {
            "id": chunk_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": text,
            "embedding_id": embedding_id,
            "page": page,
            "metadata_json": metadata_json,
        }

    def list_chunks(self, document_id: str) -> list[dict]:
        """Return a list of chunks."""
        cursor = self.conn.execute(
            "SELECT * FROM document_chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # -- rag_context --

    def add_rag_context(self, session_id: str, document_id: str) -> dict:
        """Add rag context."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO rag_context (session_id, document_id, added_at) VALUES (?, ?, ?)",
            (session_id, document_id, now),
        )
        self.conn.commit()
        return {"session_id": session_id, "document_id": document_id, "added_at": now}

    def list_rag_context(self, session_id: str) -> list[dict]:
        """Return a list of rag context."""
        cursor = self.conn.execute("SELECT * FROM rag_context WHERE session_id = ? ORDER BY added_at", (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def remove_rag_context(self, session_id: str, document_id: str) -> bool:
        """Remove rag context."""
        self.conn.execute(
            "DELETE FROM rag_context WHERE session_id = ? AND document_id = ?",
            (session_id, document_id),
        )
        self.conn.commit()
        return True

    def close(self) -> None:
        """Close the resource and release any held connections."""
        self.conn.close()
