import pytest
from unittest.mock import patch
from src.dms.database import DMSDB
from src.dms.project_manager import ProjectManager


@pytest.fixture
def pm(tmp_path):
    with patch("src.dms.database.DB_PATH", tmp_path / "test_dms.db"):
        db = DMSDB()
        mgr = ProjectManager(db)
        yield mgr
        db.close()


def test_create_project(pm):
    project = pm.create_project("Alpha", "First project")
    assert project["name"] == "Alpha"
    assert project["description"] == "First project"
    assert len(project["id"]) == 8
    assert project["created_at"] is not None


def test_get_project(pm):
    created = pm.create_project("Beta")
    fetched = pm.get_project(created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]
    assert fetched["name"] == "Beta"


def test_get_project_not_found(pm):
    assert pm.get_project("nonexist") is None


def test_list_projects(pm):
    pm.create_project("A")
    pm.create_project("B")
    pm.create_project("C")
    projects = pm.list_projects()
    assert len(projects) == 3


def test_list_projects_empty(pm):
    assert pm.list_projects() == []


def test_update_project_name_only(pm):
    project = pm.create_project("Old Name", "desc")
    updated = pm.update_project(project["id"], name="New Name")
    assert updated is not None
    assert updated["name"] == "New Name"
    assert updated["description"] == "desc"


def test_update_project_description_only(pm):
    project = pm.create_project("Name", "Old Desc")
    updated = pm.update_project(project["id"], description="New Desc")
    assert updated is not None
    assert updated["name"] == "Name"
    assert updated["description"] == "New Desc"


def test_update_project_both(pm):
    project = pm.create_project("X", "Y")
    updated = pm.update_project(project["id"], name="A", description="B")
    assert updated is not None
    assert updated["name"] == "A"
    assert updated["description"] == "B"


def test_update_project_no_fields(pm):
    project = pm.create_project("Same", "Same")
    updated = pm.update_project(project["id"])
    assert updated is not None
    assert updated["name"] == "Same"
    assert updated["description"] == "Same"


def test_update_project_nonexistent(pm):
    assert pm.update_project("nonexist", name="X") is None


def test_delete_project(pm):
    project = pm.create_project("To Delete")
    result = pm.delete_project(project["id"])
    assert result is True
    assert pm.get_project(project["id"]) is None
    assert pm.list_projects() == []


def test_delete_project_cascades_to_documents(pm):
    project = pm.create_project("Cascade")
    doc = pm.db.add_document(project["id"], "file.pdf")
    pm.db.add_chunk(doc["id"], 0, "chunk text")
    pm.delete_project(project["id"])
    assert pm.db.list_documents(project["id"]) == []
    assert pm.db.list_chunks(doc["id"]) == []
