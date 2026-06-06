"""MVP Debate Canvas — minimal WorkflowDefinition factory.

Creates a 4-agent debate workflow (strategist → critic → optimizer → moderator)
where each agent has its own dedicated LLM profile.  This bypasses the complex
CanvasToWorkflowConverter and builds the WorkflowDefinition directly.

Usage:
    from backend.blueprints.mvp_debate_canvas import build_mvp_debate_workflow
    wf = build_mvp_debate_workflow(repo, llm_profile_ids={...})
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from backend.blueprints.models import (
    AgentBlueprint,
    BlueprintLLMProfile,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    TerminationCondition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)

logger = logging.getLogger(__name__)

#: Default agent roles in execution order.
MVP_DEBATE_ROLES: list[str] = ["strategist", "critic", "optimizer", "moderator"]

#: Default LLM profile assignments (role → profile_id).
#: If not overridden, all agents share the same profile.
DEFAULT_LLM_ASSIGNMENTS: dict[str, str] = {}


_PLACEHOLDER_API_KEY_ENVS = frozenset(
    {
        "YOUR_API_KEY_ENV_VAR",
        "YOUR_API_KEY",
        "REPLACE_ME",
        "CHANGEME",
        "",
    }
)


def _ensure_llm_profile_in_db(repo: BlueprintRepository, profile_id: str) -> None:
    """Ensure an LLM profile exists in the DB. Sync from module if needed.

    Also updates stale ``api_key_env`` placeholder values in the DB
    with the current module manifest value.
    """
    existing = repo.get_llm_profile(profile_id)

    from backend.services.module_profile_sync import get_llm_profiles_from_modules

    module_profile = None
    for mp in get_llm_profiles_from_modules():
        if mp.get("id") == profile_id:
            module_profile = mp
            break

    if existing is not None:
        # Update stale placeholder api_key_env from module source
        if (
            module_profile
            and existing.api_key_env in _PLACEHOLDER_API_KEY_ENVS
            and module_profile.get("api_key_env", "") not in _PLACEHOLDER_API_KEY_ENVS
        ):
            existing.api_key_env = module_profile["api_key_env"]
            repo.save_llm_profile(existing)
            logger.info(
                "Updated stale api_key_env for profile '%s' from module manifest",
                profile_id,
            )
        return

    if module_profile:
        profile = BlueprintLLMProfile(
            id=module_profile["id"],
            name=module_profile.get("name", profile_id),
            provider=module_profile.get("provider", "local"),
            model=module_profile.get("model", profile_id),
            api_base=module_profile.get("api_base"),
            api_key_env=module_profile.get("api_key_env", "OPENROUTER_API_KEY"),
            max_tokens=module_profile.get("max_tokens", 4096),
            context_window=module_profile.get("context_window"),
            temperature=module_profile.get("temperature", 0.7),
            timeout=module_profile.get("timeout", 600),
            profile_type=module_profile.get("profile_type", "text"),
        )
        repo.save_llm_profile(profile)
        logger.info("Synced LLM profile '%s' from module to DB", profile_id)
        return

    raise ValueError(f"LLM profile '{profile_id}' not found in DB or modules")


def _ensure_blueprint(
    repo: BlueprintRepository,
    role: str,
    llm_profile_id: str,
) -> AgentBlueprint:
    """Ensure an AgentBlueprint exists for the given role + LLM profile.

    If the blueprint already exists but has a different LLM profile,
    update it to use the requested profile.
    """
    blueprint_id = f"mvp-{role}"
    existing = repo.get_blueprint(blueprint_id)
    if existing:
        if existing.llm_profile_id != llm_profile_id:
            existing.llm_profile_id = llm_profile_id
            repo.save_blueprint(existing)
            logger.info(
                "Updated AgentBlueprint '%s' LLM profile from '%s' to '%s'",
                blueprint_id,
                existing.llm_profile_id,
                llm_profile_id,
            )
        return existing

    _ensure_llm_profile_in_db(repo, llm_profile_id)

    blueprint = AgentBlueprint(
        id=blueprint_id,
        name=f"{role.title()} (MVP)",
        description=f"MVP {role} agent with LLM '{llm_profile_id}'",
        llm_profile_id=llm_profile_id,
        role_definition_id=role,
        is_active=True,
    )
    repo.save_blueprint(blueprint)
    logger.info("Created AgentBlueprint '%s' with LLM '%s'", blueprint_id, llm_profile_id)
    return blueprint


def build_mvp_debate_workflow(
    repo: BlueprintRepository,
    llm_profile_ids: dict[str, str] | None = None,
    max_rounds: int = 5,
    consensus_threshold: float = 0.9,
    name: str = "MVP Debate",
    description: str = "4-agent debate with per-agent LLM profiles",
) -> WorkflowDefinition:
    """Build a minimal debate WorkflowDefinition with 4 agent nodes.

    Each agent node references its own AgentBlueprint with a distinct LLM profile.

    Args:
        repo: BlueprintRepository for resolving/creating entities.
        llm_profile_ids: Mapping of role → llm_profile_id.
            Roles not in this dict get the first available LLM profile.
            Example: {"strategist": "llm-cloud-openrouter", "critic": "llm-local-gemma"}
        max_rounds: Maximum debate rounds.
        consensus_threshold: Consensus threshold for early termination.
        name: Workflow name.
        description: Workflow description.

    Returns:
        WorkflowDefinition ready for compilation via WorkflowCompiler.
    """
    llm_profile_ids = llm_profile_ids or {}

    # If no LLM profile IDs provided, use the first available one for all agents
    if not llm_profile_ids:
        all_profiles = repo.list_llm_profiles()
        if not all_profiles:
            raise ValueError("No LLM profiles available. Create at least one LLM profile first.")
        default_id = all_profiles[0].id
        llm_profile_ids = {role: default_id for role in MVP_DEBATE_ROLES}

    # Ensure all referenced LLM profiles exist (DB or module)
    from backend.services.module_profile_sync import get_llm_profiles_from_modules

    module_profiles = {p["id"]: p for p in get_llm_profiles_from_modules()}
    for role, profile_id in llm_profile_ids.items():
        profile = repo.get_llm_profile(profile_id)
        if profile is None and profile_id not in module_profiles:
            available = sorted(set([p.id for p in repo.list_llm_profiles(limit=200)] + list(module_profiles.keys())))
            raise ValueError(f"LLM profile '{profile_id}' not found for role '{role}'. Available: {', '.join(available)}")

    # Create/ensure blueprints for each role
    blueprints: dict[str, AgentBlueprint] = {}
    for role in MVP_DEBATE_ROLES:
        profile_id = llm_profile_ids.get(role)
        if profile_id:
            blueprints[role] = _ensure_blueprint(repo, role, profile_id)

    # Build workflow nodes
    nodes: list[WorkflowNode] = []
    for role in MVP_DEBATE_ROLES:
        node_type = f"wf-{role}"
        node_id = f"node-{role}"
        nodes.append(
            WorkflowNode(
                id=node_id,
                type=node_type,  # type: ignore[arg-type]
                label=role.title(),
                agent_blueprint_id=blueprints[role].id,
                position={"x": MVP_DEBATE_ROLES.index(role) * 250, "y": 100},
            )
        )

    # Build sequential edges: strategist → critic → optimizer → moderator
    edges: list[WorkflowEdge] = []
    for i in range(len(MVP_DEBATE_ROLES) - 1):
        source_id = f"node-{MVP_DEBATE_ROLES[i]}"
        target_id = f"node-{MVP_DEBATE_ROLES[i + 1]}"
        edges.append(
            WorkflowEdge(
                id=f"edge-{MVP_DEBATE_ROLES[i]}-{MVP_DEBATE_ROLES[i + 1]}",
                source=source_id,
                target=target_id,
                type="sequential",
            )
        )

    # Feedback edge: moderator → strategist (for next round)
    edges.append(
        WorkflowEdge(
            id="edge-feedback",
            source="node-moderator",
            target="node-strategist",
            type="feedback",
        )
    )

    now = datetime.now(UTC)

    wf = WorkflowDefinition(
        id=f"wf-mvp-{uuid.uuid4().hex[:8]}",
        name=name,
        description=description,
        nodes=nodes,
        edges=edges,
        entry_point="node-strategist",
        termination_conditions=[
            TerminationCondition(
                type="max_rounds",
                value=max_rounds,
                description=f"Stop after {max_rounds} rounds",
            ),
            TerminationCondition(
                type="consensus_reached",
                value=consensus_threshold,
                description=f"Stop when consensus ≥ {consensus_threshold}",
            ),
        ],
        tags=["mvp", "per-agent-llm"],
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    logger.info(
        "Built MVP debate workflow '%s' (%s): %d nodes, %d edges, LLM assignments=%s",
        wf.name,
        wf.id,
        len(wf.nodes),
        len(wf.edges),
        {role: bp.llm_profile_id for role, bp in blueprints.items()},
    )

    return wf
