"""Dependency injection for FastAPI routes.

Provides shared services (audit, graph, settings) as FastAPI dependencies.
"""

from __future__ import annotations

from functools import lru_cache

from debate_engine.core.config import Settings, settings
from debate_engine.persistence.audit import AuditService
from debate_engine.workflow.debate_graph import debate_graph


@lru_cache
def get_settings() -> Settings:
    return settings


@lru_cache
def get_audit_service() -> AuditService:
    return AuditService()


def get_debate_graph():
    return debate_graph
