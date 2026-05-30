"""Seed RoleTypes, RoleDefinitions, and AgentBlueprints for transactional drafting.

Creates the builder (Constructor), pragmatist (Reality Filter), and
angel's advocate roles so they appear in the TemplateInstantiateModal
dropdowns and can be used in Transactional Drafting workflows.

Usage:
    uv run python -m scripts.seed_transactional_roles
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.blueprints.models import AgentBlueprint, RoleDefinition, RoleType
from backend.blueprints.repository import BlueprintRepository

logger = logging.getLogger(__name__)

LLM_PROFILE_ID = "xiaomi-mimo-v2.5-pro"


def update_role_types(repo: BlueprintRepository) -> None:
    now = datetime.now(UTC)
    roles = [
        RoleType(
            id="builder",
            name="Builder (Constructor)",
            description="Aus Kritik entsteht ein konkretes, implementierbares Artefakt.",
            icon="🔨",
            color="#22c55e",
            default_max_rounds=5,
            default_consensus_threshold=0.9,
            category="functional",
            tags=["transactional"],
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        RoleType(
            id="pragmatist",
            name="Pragmatist (Reality Filter)",
            description="Machbarkeits-Filter für Builder-Vorschläge.",
            icon="⚖️",
            color="#6366f1",
            default_max_rounds=5,
            default_consensus_threshold=0.9,
            category="functional",
            tags=["transactional"],
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        RoleType(
            id="angels-advocate",
            name="Angel's Advocate",
            description="Verteidigt das Überbleibende einer Lösung gegenüber Kritik.",
            icon="🛡️",
            color="#f59e0b",
            default_max_rounds=5,
            default_consensus_threshold=0.9,
            category="functional",
            tags=["transactional"],
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
    ]
    for rt in roles:
        repo.save_role_type(rt)
        logger.info("RoleType %s: %s", rt.id, rt.name)


def create_role_definitions(repo: BlueprintRepository) -> dict[str, str]:
    """Create RoleDefinitions and return {role_type_id: role_def_id}."""
    now = datetime.now(UTC)
    defs = [
        RoleDefinition(
            id="builder-default",
            name="Builder (Constructor)",
            role_type_id="builder",
            description=(
                "Du bist ein Senior-Drafting-Associate. Der Partner hat Mängel gerügt. "
                "Du lieferst keine Kommentare, sondern revidierte Klauseln/Strategien."
            ),
            mode="builder_constructor",
            max_rounds=5,
            consensus_threshold=0.9,
            tags=["transactional", "default"],
            created_at=now,
            updated_at=now,
        ),
        RoleDefinition(
            id="pragmatist-default",
            name="Pragmatist (Reality Filter)",
            role_type_id="pragmatist",
            description=(
                "Du bewertest nicht die Theorie, sondern Prozessrisiko, Kosten, Zeit und "
                "Evidenzlast. Ein Vorschlag ist nur dann gut, wenn er vor Gericht / vor dem "
                "Kunden / unter Zeitdruck funktioniert."
            ),
            mode="pragmatist_reality_filter",
            max_rounds=5,
            consensus_threshold=0.9,
            tags=["transactional", "default"],
            created_at=now,
            updated_at=now,
        ),
        RoleDefinition(
            id="angels-advocate-default",
            name="Angel's Advocate",
            role_type_id="angels-advocate",
            description=("Finde drei Elemente am aktuellen Stand, die beibehalten werden müssen, selbst wenn alles andere verworfen wird."),
            mode="angels_advocate",
            max_rounds=5,
            consensus_threshold=0.9,
            tags=["transactional", "default"],
            created_at=now,
            updated_at=now,
        ),
    ]
    mapping = {}
    for rd in defs:
        repo.save_role_definition(rd)
        mapping[rd.role_type_id] = rd.id
        logger.info("RoleDefinition %s: %s", rd.id, rd.name)
    return mapping


def create_agent_blueprints(repo: BlueprintRepository, role_def_map: dict[str, str]) -> None:
    now = datetime.now(UTC)
    blueprints = [
        AgentBlueprint(
            id="bp-builder",
            name="Builder (Constructor)",
            description="Standard-Builder für Transactional Drafting",
            llm_profile_id=LLM_PROFILE_ID,
            role_definition_id=role_def_map["builder"],
            tags=["transactional", "default"],
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        AgentBlueprint(
            id="bp-pragmatist",
            name="Pragmatist (Reality Filter)",
            description="Standard-Pragmatist für Transactional Drafting",
            llm_profile_id=LLM_PROFILE_ID,
            role_definition_id=role_def_map["pragmatist"],
            tags=["transactional", "default"],
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        AgentBlueprint(
            id="bp-angels-advocate",
            name="Angel's Advocate",
            description="Standard-Angel's Advocate für Transactional Drafting",
            llm_profile_id=LLM_PROFILE_ID,
            role_definition_id=role_def_map["angels-advocate"],
            tags=["transactional", "default"],
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
    ]
    for bp in blueprints:
        repo.save_blueprint(bp)
        logger.info("AgentBlueprint %s: %s", bp.id, bp.name)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    repo = BlueprintRepository()

    logger.info("=== Seeding transactional-drafting roles ===")
    update_role_types(repo)
    role_def_map = create_role_definitions(repo)
    create_agent_blueprints(repo, role_def_map)
    logger.info("=== Done ===")


if __name__ == "__main__":
    main()
