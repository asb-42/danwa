"""Tests for P4.5+ §4.5 — audit logger makes insert failures visible.

Before this change, a failing ``_insert`` propagated the exception
up to the workflow node body, which the runner caught with a
generic ``except Exception`` and discarded.  A whole workflow
session could lose every audit event with a single ``logger.debug``
line for the operator.  This made silent audit loss impossible to
spot until the operator ran a forensic query and noticed gaps.

The fix:

  * a single ``logger.error`` per workflow session for the first
    failure, then ``logger.debug`` for subsequent failures (so
    the operator gets one loud signal per session, not one per
    node);
  * the cached connection is dropped on every failure, so a
    transient file-lock / rotation / WAL-error self-heals on the
    next call;
  * a process-local counter is incremented on every failure and
    exposed via ``get_insert_failure_count()`` for tests and
    health checks;
  * ``close()`` failures are promoted from ``debug`` to
    ``warning`` because a close failure almost always means the
    DB file is gone or the process is in a bad state.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.workflow.audit_logger import AuditLogger


@pytest.fixture()
def audit(tmp_path: Path) -> AuditLogger:
    return AuditLogger(tmp_path / "audit.db")


class TestInsertFailureIsNonFatal:
    """P4.5+ §4.5 — _insert failures must not raise."""

    def test_dead_connection_does_not_raise(self, audit: AuditLogger, caplog: pytest.LogCaptureFixture) -> None:
        """A broken ``conn.execute`` is swallowed and logged, not raised."""
        with caplog.at_level(logging.ERROR, logger="backend.workflow.audit_logger"):
            with patch.object(
                audit,
                "_get_conn",
                side_effect=sqlite3.OperationalError("database is locked"),
            ):
                # Must not raise.
                audit._insert(
                    session_id="sess-A",
                    workflow_id="wf",
                    workflow_version=1,
                    event_type="node_started",
                )
        # The first failure for sess-A was logged at error level.
        assert any(rec.levelno == logging.ERROR and "sess-A" in rec.getMessage() for rec in caplog.records), caplog.records

    def test_failure_counter_increments(self, audit: AuditLogger) -> None:
        """``get_insert_failure_count`` is bumped on every failed insert."""
        assert audit.get_insert_failure_count() == 0
        with patch.object(
            audit,
            "_get_conn",
            side_effect=sqlite3.OperationalError("db is locked"),
        ):
            for _ in range(3):
                audit._insert(
                    session_id="sess-B",
                    workflow_id="wf",
                    workflow_version=1,
                    event_type="node_started",
                )
        assert audit.get_insert_failure_count() == 3

    def test_cached_connection_is_dropped_on_failure(self, audit: AuditLogger) -> None:
        """A dead cached connection must be cleared so the next call reopens."""
        # Force a real (working) connection first.
        _ = audit._get_conn()
        assert audit._conn is not None
        with patch.object(
            audit,
            "_get_conn",
            side_effect=sqlite3.OperationalError("db is locked"),
        ):
            audit._insert(
                session_id="sess-C",
                workflow_id="wf",
                workflow_version=1,
                event_type="node_started",
            )
        assert audit._conn is None


class TestPerSessionErrorThrottling:
    """P4.5+ §4.5 — only the first failure per session is loud."""

    def test_first_failure_per_session_logs_error(self, audit: AuditLogger, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="backend.workflow.audit_logger"):
            with patch.object(
                audit,
                "_get_conn",
                side_effect=sqlite3.OperationalError("db is locked"),
            ):
                audit._insert(
                    session_id="sess-D",
                    workflow_id="wf",
                    workflow_version=1,
                    event_type="node_started",
                )
        # Exactly one error record mentioning sess-D.
        errors = [r for r in caplog.records if r.levelno == logging.ERROR and "sess-D" in r.getMessage()]
        assert len(errors) == 1, [r.getMessage() for r in caplog.records]

    def test_subsequent_failures_drop_to_debug(self, audit: AuditLogger, caplog: pytest.LogCaptureFixture) -> None:
        """A 2nd, 3rd, … failure for the same session must be ``debug``."""
        with caplog.at_level(logging.DEBUG, logger="backend.workflow.audit_logger"):
            with patch.object(
                audit,
                "_get_conn",
                side_effect=sqlite3.OperationalError("db is locked"),
            ):
                for _ in range(5):
                    audit._insert(
                        session_id="sess-E",
                        workflow_id="wf",
                        workflow_version=1,
                        event_type="node_started",
                    )
        # Only one error, even though we failed 5 times.
        errors = [r for r in caplog.records if r.levelno == logging.ERROR and "sess-E" in r.getMessage()]
        assert len(errors) == 1, [r.getMessage() for r in caplog.records]
        # The 2nd-5th were at debug level.
        debugs = [r for r in caplog.records if r.levelno == logging.DEBUG and "sess-E" in r.getMessage() and "suppressed" in r.getMessage()]
        assert len(debugs) == 4, [r.getMessage() for r in caplog.records]

    def test_different_sessions_each_get_their_own_error(self, audit: AuditLogger, caplog: pytest.LogCaptureFixture) -> None:
        """Two failing sessions produce two error lines, not one."""
        with caplog.at_level(logging.DEBUG, logger="backend.workflow.audit_logger"):
            with patch.object(
                audit,
                "_get_conn",
                side_effect=sqlite3.OperationalError("db is locked"),
            ):
                audit._insert(
                    session_id="sess-F1",
                    workflow_id="wf",
                    workflow_version=1,
                    event_type="node_started",
                )
                audit._insert(
                    session_id="sess-F2",
                    workflow_id="wf",
                    workflow_version=1,
                    event_type="node_started",
                )
        error_sessions = {r.getMessage().split("for session ", 1)[1].split(";")[0] for r in caplog.records if r.levelno == logging.ERROR}
        assert error_sessions == {"sess-F1", "sess-F2"}


class TestCloseFailureIsLoud:
    """P4.5+ §4.5 — close() failures are warning, not debug."""

    def test_close_failure_logs_warning(self, audit: AuditLogger, caplog: pytest.LogCaptureFixture) -> None:
        # Force ``close()`` on the cached connection to raise by
        # replacing the cached connection with a Mock that raises
        # on .close().  We can't patch ``sqlite3.Connection.close``
        # directly because it's an immutable C-level attribute.
        from unittest.mock import MagicMock

        fake_conn = MagicMock()
        fake_conn.close.side_effect = RuntimeError("close boom")
        audit._conn = fake_conn
        with caplog.at_level(logging.WARNING, logger="backend.workflow.audit_logger"):
            audit.close()
        assert any(r.levelno == logging.WARNING and "closing audit logger" in r.getMessage() for r in caplog.records), [
            r.getMessage() for r in caplog.records
        ]
        # The connection is still cleared so the next call reopens.
        assert audit._conn is None
