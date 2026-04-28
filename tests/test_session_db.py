import pytest
from unittest.mock import patch
from src.core.session_db import SessionDB
from src.core.debate_engine import DebateState
import tempfile
from pathlib import Path


@pytest.fixture
def db(tmp_path):
    with patch("src.core.session_db.DB_PATH", tmp_path / "test.db"):
        return SessionDB()


def test_db_initialization(db):
    assert db is not None
    sessions = db.list_sessions()
    assert isinstance(sessions, list)


def test_save_and_list_session(db):
    state = DebateState()
    state.final_consensus = 0.85
    state.context = "Test topic for debate"
    
    db.save_session(state, "test_profile", "logs/trace.jsonl", "reports/report.docx", "reports/report.pdf")
    
    sessions = db.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == state.session_id
    assert sessions[0]["consensus"] == 0.85
    assert sessions[0]["profile"] == "test_profile"


def test_list_sessions_with_limit(db):
    for i in range(5):
        state = DebateState()
        db.save_session(state, "profile", "", "", "")
    
    sessions = db.list_sessions(limit=3)
    assert len(sessions) == 3


def test_list_sessions_with_offset(db):
    for i in range(5):
        state = DebateState()
        db.save_session(state, "profile", "", "", "")
    
    sessions = db.list_sessions(limit=2, offset=2)
    assert len(sessions) == 2


def test_list_sessions_filter_consensus(db):
    state1 = DebateState()
    state1.final_consensus = 0.95
    db.save_session(state1, "p", "", "", "")
    
    state2 = DebateState()
    state2.final_consensus = 0.60
    db.save_session(state2, "p", "", "", "")
    
    sessions = db.list_sessions(min_consensus=0.80)
    assert len(sessions) == 1
    assert sessions[0]["consensus"] == 0.95


def test_delete_session(db):
    state = DebateState()
    db.save_session(state, "p", "", "", "")
    
    assert len(db.list_sessions()) == 1
    
    db.delete_session(state.session_id)
    
    assert len(db.list_sessions()) == 0


def test_delete_nonexistent_session(db):
    result = db.delete_session("nonexistent")
    assert result == True


def test_cleanup_old_entries(db):
    state = DebateState()
    db.save_session(state, "p", "", "", "")
    
    deleted = db.cleanup_old_entries(days=0)
    assert deleted >= 1
    assert len(db.list_sessions()) == 0


def test_save_session_with_validation_flag(db):
    state = DebateState()
    state.validation_report = [{"claim": "test"}]
    
    db.save_session(state, "p", "", "", "")
    
    sessions = db.list_sessions()
    assert sessions[0]["validated"] == 1
    
    state2 = DebateState()
    db.save_session(state2, "p", "", "", "")
    
    sessions = db.list_sessions()
    assert sessions[1]["validated"] == 0
