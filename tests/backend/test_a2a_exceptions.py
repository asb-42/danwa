"""Tests for Phase 8 Group B — A2A Exception Hierarchy."""

from __future__ import annotations

from backend.a2a.exceptions import (
    A2AAgentError,
    A2AConnectionError,
    A2AError,
    A2AProtocolError,
    A2ATimeoutError,
    A2AValidationError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_a2a_error(self):
        assert issubclass(A2ATimeoutError, A2AError)
        assert issubclass(A2AConnectionError, A2AError)
        assert issubclass(A2AProtocolError, A2AError)
        assert issubclass(A2AValidationError, A2AError)
        assert issubclass(A2AAgentError, A2AError)

    def test_base_error_carries_data(self):
        err = A2AError("test", endpoint="http://example.com", task_id="t1", error_code=500)
        assert str(err) == "test"
        assert err.endpoint == "http://example.com"
        assert err.task_id == "t1"
        assert err.error_code == 500

    def test_timeout_error(self):
        err = A2ATimeoutError("timeout", endpoint="http://agent.com")
        assert "timeout" in str(err)
        assert err.endpoint == "http://agent.com"

    def test_connection_error(self):
        err = A2AConnectionError("conn failed")
        assert "conn failed" in str(err)

    def test_validation_error(self):
        err = A2AValidationError("bad url")
        assert "bad url" in str(err)

    def test_protocol_error(self):
        err = A2AProtocolError("invalid json-rpc")
        assert "invalid json-rpc" in str(err)

    def test_agent_error(self):
        err = A2AAgentError("agent returned error")
        assert "agent returned error" in str(err)
