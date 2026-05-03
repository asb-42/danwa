"""Dependency injection for FastAPI routes.

Provides shared services (audit, graph, settings) as FastAPI dependencies.
"""

from __future__ import annotations

from functools import lru_cache

from backend.core.config import Settings, settings
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.workflow.debate_graph import debate_graph


@lru_cache
def get_settings() -> Settings:
    return settings


@lru_cache
def get_audit_service() -> AuditService:
    return AuditService()


@lru_cache
def get_debate_store() -> DebateStore:
    return DebateStore()


def get_debate_graph():
    return debate_graph
