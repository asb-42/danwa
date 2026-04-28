import pytest
from unittest.mock import patch
from src.dms.database import DMSDB
from src.core.session_db import SessionDB


@pytest.fixture
def db(tmp_path):
    with patch("src.dms.database.DB_PATH", tmp_path / "test_dms.db"):
        d = DMSDB()
        yield d
        d.close()


@pytest.fixture
def session_db(tmp_path):
    with patch("src.core.session_db.DB_PATH", tmp_path / "test_sessions.db"):
        d = SessionDB()
        yield d
        d.close()


def test_create_project(db):
    project = db.create_project("Test Project", "A test description")
    assert project["name"] == "Test Project"
    assert project["description"] == "A test description"
    assert len(project["id"]) == 8
    assert project["created_at"] is not None


def test_get_project(db):
    created = db.create_project("Lookup")
    fetched = db.get_project(created["id"])
    assert fetched["id"] == created["id"]
    assert fetched["name"] == "Lookup"


def test_get_project_not_found(db):
    assert db.get_project("nonexist") is None


def test_list_projects(db):
    db.create_project("A")
    db.create_project("B")
    db.create_project("C")
    projects = db.list_projects()
    assert len(projects) == 3


def test_list_projects_empty(db):
    assert db.list_projects() == []


def test_delete_project(db):
    project = db.create_project("To Delete")
    db.delete_project(project["id"])
    assert db.get_project(project["id"]) is None
    assert db.list_projects() == []


def test_delete_project_cascades(db):
    project = db.create_project("Cascade")
    doc = db.add_document(project["id"], "file.pdf")
    db.add_chunk(doc["id"], 0, "chunk text")
    db.delete_project(project["id"])
    assert db.list_documents(project["id"]) == []
    assert db.list_chunks(doc["id"]) == []


def test_add_document(db):
    project = db.create_project("DocProject")
    doc = db.add_document(
        project["id"],
        "report.pdf",
        file_path="/tmp/report.pdf",
        file_type="pdf",
        page_count=10,
        word_count=5000,
        char_count=30000,
        ocr_used=True,
    )
    assert doc["filename"] == "report.pdf"
    assert doc["project_id"] == project["id"]
    assert doc["ocr_used"] == 1
    assert doc["page_count"] == 10
    assert len(doc["id"]) == 8


def test_list_documents(db):
    project = db.create_project("P")
    db.add_document(project["id"], "a.pdf")
    db.add_document(project["id"], "b.pdf")
    docs = db.list_documents(project["id"])
    assert len(docs) == 2


def test_list_documents_empty(db):
    project = db.create_project("Empty")
    assert db.list_documents(project["id"]) == []


def test_list_documents_scoped_to_project(db):
    p1 = db.create_project("P1")
    p2 = db.create_project("P2")
    db.add_document(p1["id"], "a.pdf")
    db.add_document(p2["id"], "b.pdf")
    assert len(db.list_documents(p1["id"])) == 1
    assert len(db.list_documents(p2["id"])) == 1


def test_delete_document(db):
    project = db.create_project("P")
    doc = db.add_document(project["id"], "x.pdf")
    db.add_chunk(doc["id"], 0, "text")
    db.delete_document(doc["id"])
    assert db.list_documents(project["id"]) == []
    assert db.list_chunks(doc["id"]) == []


def test_add_chunk(db):
    project = db.create_project("P")
    doc = db.add_document(project["id"], "f.pdf")
    chunk = db.add_chunk(doc["id"], 0, "Hello world", embedding_id="emb-001", page=1)
    assert chunk["document_id"] == doc["id"]
    assert chunk["chunk_index"] == 0
    assert chunk["text"] == "Hello world"
    assert chunk["embedding_id"] == "emb-001"
    assert chunk["page"] == 1


def test_list_chunks(db):
    project = db.create_project("P")
    doc = db.add_document(project["id"], "f.pdf")
    db.add_chunk(doc["id"], 0, "first")
    db.add_chunk(doc["id"], 1, "second")
    db.add_chunk(doc["id"], 2, "third")
    chunks = db.list_chunks(doc["id"])
    assert len(chunks) == 3
    assert chunks[0]["chunk_index"] == 0
    assert chunks[2]["chunk_index"] == 2


def test_list_chunks_ordered(db):
    project = db.create_project("P")
    doc = db.add_document(project["id"], "f.pdf")
    db.add_chunk(doc["id"], 2, "third")
    db.add_chunk(doc["id"], 0, "first")
    db.add_chunk(doc["id"], 1, "second")
    chunks = db.list_chunks(doc["id"])
    assert [c["chunk_index"] for c in chunks] == [0, 1, 2]


def test_add_rag_context(db):
    ctx = db.add_rag_context("sess-001", "doc-001")
    assert ctx["session_id"] == "sess-001"
    assert ctx["document_id"] == "doc-001"
    assert ctx["added_at"] is not None


def test_list_rag_context(db):
    db.add_rag_context("sess-001", "doc-a")
    db.add_rag_context("sess-001", "doc-b")
    db.add_rag_context("sess-002", "doc-c")
    contexts = db.list_rag_context("sess-001")
    assert len(contexts) == 2


def test_remove_rag_context(db):
    db.add_rag_context("sess-001", "doc-a")
    db.add_rag_context("sess-001", "doc-b")
    db.remove_rag_context("sess-001", "doc-a")
    contexts = db.list_rag_context("sess-001")
    assert len(contexts) == 1
    assert contexts[0]["document_id"] == "doc-b"


def test_remove_rag_context_nonexistent(db):
    result = db.remove_rag_context("nope", "nope")
    assert result is True


def test_rag_context_upsert(db):
    db.add_rag_context("sess-001", "doc-a")
    db.add_rag_context("sess-001", "doc-a")
    contexts = db.list_rag_context("sess-001")
    assert len(contexts) == 1


def test_session_db_migration(session_db):
    cursor = session_db.conn.execute("PRAGMA table_info(sessions)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "project_id" in columns
    assert "document_ids" in columns


def test_session_db_migration_idempotent(tmp_path):
    with patch("src.core.session_db.DB_PATH", tmp_path / "test_idem.db"):
        db1 = SessionDB()
        db1.close()
        db2 = SessionDB()
        cursor = db2.conn.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "project_id" in columns
        assert "document_ids" in columns
        db2.close()
