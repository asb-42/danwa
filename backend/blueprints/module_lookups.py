"""Module-based entity lookups for blueprint models.

Replaces removed repository CRUD reads for RoleType, RoleDefinition, and
PromptTemplate with module-sourced data.
"""

from __future__ import annotations

import logging

from backend.blueprints.models import (
    PromptTemplate,
    RoleDefinition,
    RoleType,
)

logger = logging.getLogger(__name__)


def resolve_role_type(role_type_id: str) -> RoleType | None:
    """Resolve a RoleType by ID from module role-type modules.

    Args:
        role_type_id: The RoleType ID to look up.

    Returns:
        RoleType instance or ``None`` if not found in modules.
    """
    try:
        from backend.services.module_profile_sync import get_role_types_from_modules

        for rt in get_role_types_from_modules():
            if rt.get("id") == role_type_id:
                return RoleType(
                    id=rt["id"],
                    name=rt.get("name", role_type_id),
                    description=rt.get("description", ""),
                    icon=rt.get("icon", "👤"),
                    color=rt.get("color", "#8b5cf6"),
                    category=rt.get("category", "functional"),
                    default_max_rounds=rt.get("default_max_rounds", 5),
                    default_consensus_threshold=rt.get("default_consensus_threshold", 0.9),
                    tags=rt.get("tags", []),
                    is_active=rt.get("is_active", True),
                )
    except Exception:
        logger.debug("Module lookup for RoleType '%s' failed", role_type_id, exc_info=True)
    return None


def resolve_role_definition(role_def_id: str) -> RoleDefinition | None:
    """Resolve a RoleDefinition by ID from module agent-persona modules.

    Matches by persona ID or role field.

    Args:
        role_def_id: The RoleDefinition ID to look up.

    Returns:
        RoleDefinition instance or ``None`` if not found in modules.
    """
    try:
        from backend.services.module_profile_sync import get_agent_personas_from_modules

        for persona in get_agent_personas_from_modules():
            persona_id = persona.get("id", "")
            persona_role = persona.get("role", "")
            if persona_id == role_def_id or persona_role == role_def_id:
                return RoleDefinition(
                    id=role_def_id,
                    name=persona.get("name", role_def_id),
                    role_type_id=persona_role or role_def_id,
                    description=persona.get("description", ""),
                    max_rounds=persona.get("max_rounds", 5),
                    consensus_threshold=persona.get("consensus_threshold", 0.9),
                    tags=persona.get("tags", []),
                )
    except Exception:
        logger.debug("Module lookup for RoleDefinition '%s' failed", role_def_id, exc_info=True)
    return None


def resolve_prompt_template(template_id: str) -> PromptTemplate | None:
    """Resolve a PromptTemplate by ID from module prompt-variant modules.

    Args:
        template_id: The PromptTemplate ID to look up.

    Returns:
        PromptTemplate instance or ``None`` if not found in modules.
    """
    try:
        from backend.services.module_profile_sync import get_prompt_templates_from_modules

        for pt in get_prompt_templates_from_modules():
            if pt.get("id") == template_id:
                content = pt.get("content", "")
                if not content.strip():
                    continue
                return PromptTemplate(
                    id=pt["id"],
                    name=pt.get("name", template_id),
                    role=pt.get("role", "strategist"),
                    content=content,
                    language=pt.get("language", "en"),
                    variant=pt.get("variant", "default"),
                    description=pt.get("description", ""),
                    tags=pt.get("tags", []),
                )
    except Exception:
        logger.debug("Module lookup for PromptTemplate '%s' failed", template_id, exc_info=True)
    return None
