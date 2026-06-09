"""Kitsune Agent — read-only tool definitions for the Danwa assistant.

Each tool is a registered async function with a JSON Schema for its parameters.
Tools are stateless and idempotent. They receive a context dict containing
service instances at execution time.

Phase 1: Read-only tools only. No destructive actions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Registry ─────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
) -> callable:
    """Decorator to register a tool function in the global registry.

    Args:
        name: Unique tool name (snake_case).
        description: Human-readable description of what the tool does.
        parameters: OpenAI-compatible JSON Schema describing the parameters.

    Returns:
        Decorator that registers the function and returns it unchanged.
    """

    def decorator(func):
        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "fn": func,
        }
        return func

    return decorator


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return all registered tool definitions in OpenAI function-calling format.

    Returns:
        List of tool definition dicts suitable for the ``tools`` parameter
        of the chat completions API.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_REGISTRY.values()
    ]


async def execute_tool(name: str, arguments: str, **ctx: Any) -> str:
    """Execute a registered tool by name.

    Args:
        name: The tool name to execute.
        arguments: JSON-encoded string of arguments.
        ctx: Keyword arguments passed through to the tool function
            (typically service instances).

    Returns:
        JSON-encoded result string. On error, returns ``{"error": "..."}``.
    """
    if name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)

    try:
        args = json.loads(arguments) if arguments else {}
        result = await TOOL_REGISTRY[name]["fn"](**args, **ctx)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e, exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ─── Tools ────────────────────────────────────────────────────────────────────


@tool(
    name="get_system_status",
    description="Get a compact summary of current system status: active assistant sessions, LLM profiles, installed modules, and active debates.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def get_system_status(**ctx: Any) -> dict[str, Any]:
    """Return a summary of current system status."""
    assistant = ctx.get("assistant_service")
    blueprint_repo = ctx.get("blueprint_repository")
    debate_store = ctx.get("debate_store")

    sessions_count = len(assistant.list_sessions()) if assistant else 0

    profiles_count = 0
    if blueprint_repo:
        try:
            profiles = blueprint_repo.list_llm_profiles()
            profiles_count = len(profiles)
        except Exception:
            pass

    debates_count = 0
    if debate_store:
        try:
            debates = debate_store.list_all(limit=100)
            debates_count = len(debates)
        except Exception:
            pass

        # If the provided store is empty (legacy dir), scan case directories
        if debates_count == 0:
            debates_count = len(_aggregate_debates_from_cases())

    return {
        "active_sessions": sessions_count,
        "llm_profiles_count": profiles_count,
        "active_debates_count": debates_count,
    }


def _aggregate_debates_from_cases() -> list[dict]:
    """Scan all tenant/case debate directories and aggregate debates."""
    from backend.persistence.case_store import _DEFAULT_BASE_DIR as CASE_BASE

    debates: list[dict] = []
    if not CASE_BASE.is_dir():
        return debates

    for tenant_dir in sorted(CASE_BASE.iterdir()):
        if not tenant_dir.is_dir():
            continue
        cases_dir = tenant_dir / "cases"
        if not cases_dir.is_dir():
            continue
        for case_dir in sorted(cases_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            debates_dir = case_dir / "debates"
            if not debates_dir.is_dir():
                continue
            for path in debates_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if data.get("debate_id"):
                        debates.append(data)
                except Exception:
                    pass

    # Also scan legacy data/debates/ directory
    legacy_dir = Path("data/debates")
    if legacy_dir.is_dir():
        for path in legacy_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("debate_id") and data["debate_id"] not in {d["debate_id"] for d in debates}:
                    debates.append(data)
            except Exception:
                pass

    # Sort newest first
    debates.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return debates


@tool(
    name="list_debates",
    description="List all debates. Returns topic, status, round count, and creation date for each debate.",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["running", "completed", "all"],
                "description": "Filter by debate status. Default: all",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of debates to return (default 20, max 50).",
            },
        },
        "required": [],
    },
)
async def list_debates(
    status: str = "all",
    limit: int = 20,
    **ctx: Any,
) -> list[dict[str, Any]]:
    """Return a list of debates with key metadata."""
    debate_store = ctx.get("debate_store")

    # If the provided store has no debates, scan all case directories
    debates = []
    if debate_store:
        debates = debate_store.list_all(limit=999)
        if not debates:
            debates = _aggregate_debates_from_cases()
    else:
        return [{"error": "Debate store not available"}]

    result = []
    for d in debates[: min(limit, 50)]:
        d_status = d.get("status", "unknown")
        if status != "all" and d_status != status:
            continue
        result.append(
            {
                "debate_id": d.get("debate_id", ""),
                "title": d.get("title", "")[:100],
                "status": d_status,
                "current_round": d.get("current_round", 0),
                "max_rounds": d.get("max_rounds", 0),
                "created_at": str(d.get("created_at", "")),
            }
        )
    return result


@tool(
    name="get_debate_details",
    description="Get detailed information about a specific debate, including current round, consensus status, and recent messages.",
    parameters={
        "type": "object",
        "properties": {
            "debate_id": {
                "type": "string",
                "description": "The debate ID to fetch details for.",
            },
        },
        "required": ["debate_id"],
    },
)
async def get_debate_details(debate_id: str, **ctx: Any) -> dict[str, Any]:
    """Return full details of a single debate."""
    debate_store = ctx.get("debate_store")

    debate = None
    if debate_store:
        debate = debate_store.get(debate_id)

        # If not found in the provided store, scan case directories
        if not debate:
            for d in _aggregate_debates_from_cases():
                if d.get("debate_id") == debate_id:
                    debate = d
                    break
    else:
        return {"error": "Debate store not available"}

    if not debate:
        return {"error": f"Debate not found: {debate_id}"}

    return {
        "debate_id": debate.get("debate_id", ""),
        "title": debate.get("title", ""),
        "status": debate.get("status", "unknown"),
        "current_round": debate.get("current_round", 0),
        "max_rounds": debate.get("max_rounds", 0),
        "consensus": debate.get("final_consensus", None),
        "created_at": str(debate.get("created_at", "")),
        "updated_at": str(debate.get("updated_at", "")),
        "round_count": len(debate.get("rounds", [])),
        "llm_assignments": debate.get("llm_assignments", {}),
    }


@tool(
    name="get_llm_profiles",
    description="List all configured LLM profiles with provider, model, and service eligibility.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def get_llm_profiles(**ctx: Any) -> list[dict[str, Any]]:
    """Return all LLM profiles with key attributes."""
    blueprint_repo = ctx.get("blueprint_repository")
    if not blueprint_repo:
        return [{"error": "Blueprint repository not available"}]

    try:
        profiles = blueprint_repo.list_llm_profiles()
        return [
            {
                "id": p.id,
                "name": p.name,
                "provider": p.provider,
                "model": p.model,
                "service_eligible": getattr(p, "service_eligible", True),
                "max_tokens": getattr(p, "max_tokens", 0),
                "temperature": getattr(p, "temperature", 0.7),
            }
            for p in profiles
        ]
    except Exception as e:
        logger.error("Failed to list LLM profiles: %s", e, exc_info=True)
        return [{"error": str(e)}]


@tool(
    name="get_modules",
    description="List installed modules, optionally filtered by category.",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["llm-profiles", "agents", "prompts", "prompt-modifiers", "tone-profiles", "workflows", "translations", "bundles"],
                "description": "Optional category to filter by. Omit to list all.",
            },
        },
        "required": [],
    },
)
async def get_modules(category: str | None = None, **ctx: Any) -> list[dict[str, Any]]:
    """Return list of installed modules."""
    module_service = ctx.get("module_service")
    if not module_service:
        return [{"error": "Module service not available"}]

    try:
        modules = module_service.discover_local_with_status()
        if category:
            modules = [m for m in modules if m.get("category") == category]
        return [
            {
                "module_id": m.get("module_id", ""),
                "name": m.get("name", ""),
                "version": m.get("version", ""),
                "type": m.get("type", ""),
                "category": m.get("category", ""),
                "enabled": m.get("enabled", False),
            }
            for m in modules
        ]
    except Exception as e:
        logger.error("Failed to list modules: %s", e, exc_info=True)
        return [{"error": str(e)}]


@tool(
    name="search_knowledge_base",
    description="Search the Danwa codebase knowledge base for technical information about "
    "API endpoints, configuration options, database tables, and workflow nodes.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search term or question.",
            },
        },
        "required": ["query"],
    },
)
async def search_knowledge_base(query: str, **ctx: Any) -> dict[str, Any]:
    """Search in the auto-generated knowledge base."""
    knowledge_file = ctx.get("knowledge_base_path")
    if not knowledge_file:
        return {"error": "Knowledge base not available"}

    try:
        content = knowledge_file.read_text(encoding="utf-8")
    except Exception as e:
        return {"error": f"Failed to read knowledge base: {e}"}

    query_lower = query.lower()
    lines = content.split("\n")

    # Simple case-insensitive search
    matches = []
    for i, line in enumerate(lines):
        if query_lower in line.lower():
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            snippet = "\n".join(lines[start:end])
            matches.append(
                {
                    "line": i + 1,
                    "snippet": snippet.strip(),
                }
            )

    return {
        "query": query,
        "match_count": len(matches),
        "matches": matches[:10],  # Limit to 10 results
    }
