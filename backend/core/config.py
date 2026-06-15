"""Application settings via pydantic-settings. Reads from environment / .env file."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_version() -> str:
    """Read version from the VERSION single source of truth file.

    Falls back to ``0.0.0-dev`` if the file is missing (e.g. during development).
    """
    version_file = Path(__file__).resolve().parent.parent.parent / "version"
    if not version_file.exists():
        return "0.0.0-dev"
    lines = [line.strip() for line in version_file.read_text().splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        return "0.0.0-dev"
    ver = lines[-1].strip()
    return ver if re.match(r"^\d+\.\d+\.\d+$", ver) else "0.0.0-dev"


class Settings(BaseSettings):
    """Central configuration for the debate engine."""

    model_config = SettingsConfigDict(
        env_prefix="DANWA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Debate-Agent"
    app_version: str = _get_version()
    debug: bool = False

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Database ---
    db_path: Path = Path("data/audit.db")

    # --- Debate defaults ---
    default_max_rounds: int = 3
    default_consensus_threshold: float = 0.8
    default_agent_profile: str = "default"

    # --- Web search (SearXNG) ---
    searxng_url: str = "http://localhost:8080"
    searxng_max_results: int = 5
    searxng_region: str = "de-de"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]

    # --- A2A Protocol (Phase 8) ---
    a2a_allow_private_ips: bool = False

    # --- Output Composer ---
    output_dir: Path = Path("data/outputs")

    # --- Input Composer / External Plugins ---
    allow_external_plugins: bool = False

    # --- Service LLM (Sprint 16) ---
    service_llm_profile_id: str | None = None
    service_llm_min_context: int = 4096
    service_llm_blacklist: list[str] = [
        "whisper-",
        "tts-",
        "eleven/",
        "gpt-3.5",
        "gpt-35",
        "text-ada",
        "text-babbage",
        "text-curie",
        "text-davinci-001",
        "text-davinci-002",
        "text-davinci-003",
    ]

    # --- Backup ---
    backup_enabled: bool = True
    backup_auto_on_shutdown: bool = True
    backup_retention_count: int = 10
    backup_encrypt: bool = False
    backup_dir: Path = Path("data/backups")

    # --- Authentication (JWT) ---
    jwt_secret_key: str = ""  # MUST be set in production via DANWA_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480  # 8 hours
    jwt_refresh_token_expire_days: int = 30
    auth_enabled: bool = True  # Set to False to disable auth (dev mode)

    # --- Redis / Celery (optional — falls back to in-memory if unavailable) ---
    redis_url: str = ""  # e.g. "redis://localhost:6379/0". Empty = no Redis
    celery_enabled: bool = False  # True = use Celery for debate tasks
    celery_worker_concurrency: int = 4
    max_concurrent_debates_global: int = 20

    # --- Rate Limiting ---
    rate_limit_enabled: bool = True
    rate_limit_default: str = "60/minute"  # Default API rate limit
    rate_limit_debate: str = "10/hour"  # Debate creation limit
    rate_limit_upload: str = "20/hour"  # Document upload limit
    rate_limit_analysis: str = "5/hour"  # LLM analysis limit

    # --- Observability ---
    prometheus_enabled: bool = True

    # --- Feature flags (progressive rollout) ---
    # Case-Space is the documented primary UI of the application
    # (plans/2026-06-14_case-space-workspace.md).  The legacy views
    # (CasesView, DocumentsView, TagManagerView, ...) remain available
    # for power-users and admins, but the new Workspace / Inbox / Graph
    # views are ON by default so a fresh installation is *usable* out
    # of the box, not behind a hidden env-var gate.
    #
    # To opt out (e.g. for migration windows, or to force a stable
    # legacy-only deployment), set the corresponding env-var to
    # 'false' / '0' / 'no':
    #
    #   DANWA_ENABLE_CASE_SPACE=false
    #   DANWA_ENABLE_CASE_SPACE_INBOX=false
    #   DANWA_ENABLE_CASE_SPACE_GRAPH=false
    #
    # The original P1+P2 default (False) made the feature invisible
    # during testing and is reverted here: the rollout plan's only
    # outstanding concern was the knowledge-graph (Phase 4+5) which
    # has its own independent flag (enable_case_space_graph).
    enable_case_space: bool = True
    enable_case_space_inbox: bool = True
    # Phase 4.9 (BrowseView list-graph) + Phase 5.4 (Inspector
    # graph tab) both consume the /api/v1/graph/* endpoints.
    # Both are now shippable behind this single flag because the
    # Inspector tab degrades to a list renderer when Cytoscape
    # is not desired, and the list renderer is the default for
    # the BrowseView too.
    enable_case_space_graph: bool = True


def is_service_llm_eligible(profile) -> tuple[bool, str]:
    """Check whether an LLM profile is suitable as a service LLM.

    Returns:
        (eligible: bool, reason: str) — reason explains why the profile
        is not eligible when the first element is False.
    """
    from backend.core.config import settings

    if getattr(profile, "profile_type", "text") != "text":
        return False, f"Nur Text-LLMs geeignet (dieses: {profile.profile_type})"
    if getattr(profile, "service_eligible", True) is not True:
        return False, "Profil ist nicht als Service-LLM markiert"
    ctx = getattr(profile, "context_window", None)
    if ctx is not None and ctx < settings.service_llm_min_context:
        return False, f"Kontextfenster zu klein ({ctx} < {settings.service_llm_min_context})"
    for pattern in settings.service_llm_blacklist:
        if pattern.lower() in profile.model.lower():
            return False, f"Modell auf Blacklist ({profile.model})"
    return True, "Eignung bestätigt"


# Module-level singleton — importable as `settings`
settings = Settings()
