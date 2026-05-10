"""Application settings via pydantic-settings. Reads from environment / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    app_version: str = "2.0.0"
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


# Module-level singleton — importable as `settings`
settings = Settings()
