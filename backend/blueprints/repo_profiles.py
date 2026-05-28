"""LLM profile and prompt template repository methods."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime

from backend.blueprints.models import BlueprintLLMProfile, PromptTemplate

logger = logging.getLogger(__name__)


class ProfileRepository:
    """Mixin providing LLM profile and prompt template CRUD."""

    def save_llm_profile(self, profile: BlueprintLLMProfile) -> None:
        """Insert or replace an LLM profile."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO blueprint_llm_profiles
                    (id, name, profile_type, provider, model, api_base, api_key_env,
                     max_tokens, context_window, temperature, timeout,
                     cost_per_1k_input, cost_per_1k_output,
                     description, tags_json, created_at, updated_at,
                     protocol, a2a_endpoint, a2a_timeout,
                     fallback_llm_profile_id, a2a_config_json,
                      service_eligible)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.name,
                    profile.profile_type,
                    profile.provider,
                    profile.model,
                    profile.api_base,
                    profile.api_key_env,
                    profile.max_tokens,
                    profile.context_window,
                    profile.temperature,
                    profile.timeout,
                    profile.cost_per_1k_input,
                    profile.cost_per_1k_output,
                    profile.description,
                    json.dumps(profile.tags),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                    profile.protocol,
                    profile.a2a_endpoint,
                    profile.a2a_timeout,
                    profile.fallback_llm_profile_id,
                    json.dumps(profile.a2a_config),
                    profile.service_eligible,
                ),
            )
        logger.debug("Saved LLM profile %s", profile.id)

    def get_llm_profile(self, profile_id: str) -> BlueprintLLMProfile | None:
        """Retrieve an LLM profile by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM blueprint_llm_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_llm_profile(row)

    def list_llm_profiles(self, limit: int = 50, offset: int = 0) -> list[BlueprintLLMProfile]:
        """List all LLM profiles with pagination."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM blueprint_llm_profiles ORDER BY name LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_llm_profile(r) for r in rows]

    def delete_llm_profile(self, profile_id: str) -> bool:
        """Delete an LLM profile. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM blueprint_llm_profiles WHERE id = ?",
                (profile_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_llm_profile(row: sqlite3.Row) -> BlueprintLLMProfile:
        return BlueprintLLMProfile(
            id=row["id"],
            name=row["name"],
            profile_type=row["profile_type"] if "profile_type" in row.keys() else "text",
            provider=row["provider"],
            model=row["model"],
            api_base=row["api_base"],
            api_key_env=row["api_key_env"],
            max_tokens=row["max_tokens"],
            context_window=row["context_window"],
            temperature=row["temperature"],
            timeout=row["timeout"],
            cost_per_1k_input=row["cost_per_1k_input"],
            cost_per_1k_output=row["cost_per_1k_output"],
            description=row["description"],
            tags=json.loads(row["tags_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            protocol=row["protocol"] if "protocol" in row.keys() else "litellm",
            a2a_endpoint=row["a2a_endpoint"] if "a2a_endpoint" in row.keys() else None,
            a2a_timeout=row["a2a_timeout"] if "a2a_timeout" in row.keys() else 120,
            fallback_llm_profile_id=row["fallback_llm_profile_id"] if "fallback_llm_profile_id" in row.keys() else None,
            a2a_config=json.loads(row["a2a_config_json"]) if "a2a_config_json" in row.keys() and row["a2a_config_json"] else {},
            service_eligible=row["service_eligible"] if "service_eligible" in row.keys() else True,
        )

    def save_prompt_template(self, template: PromptTemplate) -> None:
        """Insert or replace a prompt template."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_templates
                    (id, name, role, content, language, variant,
                     description, tags_json, source_path, content_hash,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.id,
                    template.name,
                    template.role,
                    template.content,
                    template.language,
                    template.variant,
                    template.description,
                    json.dumps(template.tags),
                    template.source_path,
                    template.content_hash,
                    template.created_at.isoformat(),
                    template.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved prompt template %s", template.id)

    def get_prompt_template(self, template_id: str) -> PromptTemplate | None:
        """Retrieve a prompt template by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_prompt_template(row)

    def list_prompt_templates(
        self,
        role: str | None = None,
        variant: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptTemplate]:
        """List prompt templates, optionally filtered by role and/or variant."""
        clauses: list[str] = []
        params: list[str] = []
        if role:
            clauses.append("role = ?")
            params.append(role)
        if variant:
            clauses.append("variant = ?")
            params.append(variant)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM prompt_templates{where} ORDER BY role, name LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [self._row_to_prompt_template(r) for r in rows]

    def delete_prompt_template(self, template_id: str) -> bool:
        """Delete a prompt template. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM prompt_templates WHERE id = ?",
                (template_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_prompt_template(row: sqlite3.Row) -> PromptTemplate:
        return PromptTemplate(
            id=row["id"],
            name=row["name"],
            role=row["role"],
            content=row["content"],
            language=row["language"],
            variant=row["variant"],
            description=row["description"],
            tags=json.loads(row["tags_json"]),
            source_path=row["source_path"],
            content_hash=row["content_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
