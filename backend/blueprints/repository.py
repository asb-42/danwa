"""Blueprint Canvas — SQLite repository for blueprints and canvas layouts.

Follows the pattern of ``backend.repositories.profile_repo.ProfileRepository``
— SQLite connection per operation, ``row_factory = sqlite3.Row``.

This module re-exports ``BlueprintRepository`` which inherits from all
domain-specific repository mixins so that existing ``from
backend.blueprints.repository import BlueprintRepository`` imports continue
to work unchanged.
"""

from __future__ import annotations

from backend.blueprints.repo_base import BaseRepo
from backend.blueprints.repo_blueprints import BlueprintRepo
from backend.blueprints.repo_misc import MiscRepository
from backend.blueprints.repo_profiles import ProfileRepository
from backend.blueprints.repo_workflows import WorkflowRepository


class BlueprintRepository(
    ProfileRepository,
    BlueprintRepo,
    WorkflowRepository,
    MiscRepository,
    BaseRepo,
):
    """SQLite-backed storage for Agent Blueprints and Canvas Layouts.

    Combines all domain-specific repository mixins into a single class
    so that existing code using ``BlueprintRepository()`` continues to work.
    """

    pass


__all__ = ["BlueprintRepository"]
