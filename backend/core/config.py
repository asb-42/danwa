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
    service_llm_profile_id: str = "openrouter-claude"
    service_llm_min_context: int = 1024
    service_llm_blacklist: list[str] = [
        "gpt-3.5",
        "gpt-35",
        "text-ada",
        "text-babbage",
        "text-curie",
        "text-davinci-001",
        "text-davinci-002",
        "text-davinci-003",
    ]


def is_service_llm_eligible(profile) -> bool:
    from backend.core.config import settings

    if getattr(profile, "service_eligible", True) is not True:
        return False
    if profile.context_window is not None and profile.context_window < settings.service_llm_min_context:
        return False
    for pattern in settings.service_llm_blacklist:
        if pattern.lower() in profile.model.lower():
            return False
    return True


# Module-level singleton — importable as `settings`
settings = Settings()
