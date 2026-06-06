"""Tone profile, prompt modifier, and argumentation pattern repository methods."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.blueprints.models import PromptModifier, ToneProfile

logger = logging.getLogger(__name__)


class MiscRepository:
    """Mixin providing tone profile, prompt modifier, and argumentation pattern methods."""

    def save_tone_profile(self, profile: ToneProfile) -> None:
        """Insert or replace a tone profile."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tone_profiles
                    (id, name, description, profile_json, is_system,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.name,
                    profile.description,
                    profile.model_dump_json(),
                    int(profile.is_system),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved tone profile %s", profile.id)

    def get_tone_profile(self, profile_id: str) -> ToneProfile | None:
        """Retrieve a tone profile by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tone_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_tone_profile(row)

    def list_tone_profiles(
        self,
        include_system: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ToneProfile]:
        """List tone profiles, optionally filtering system profiles."""
        with self._connect() as conn:
            if include_system:
                rows = conn.execute(
                    "SELECT * FROM tone_profiles ORDER BY is_system DESC, name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tone_profiles WHERE is_system = 0 ORDER BY name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._row_to_tone_profile(r) for r in rows]

    def delete_tone_profile(self, profile_id: str) -> bool:
        """Delete a tone profile. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM tone_profiles WHERE id = ?",
                (profile_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_tone_profile(row: sqlite3.Row) -> ToneProfile:
        """Convert a SQLite row to a ToneProfile model."""
        return ToneProfile.model_validate_json(row["profile_json"])

    def list_argumentation_patterns(self) -> list[str]:
        """List available argumentation pattern directory names from filesystem."""
        patterns_dir = Path("profiles/argumentation-patterns")
        if not patterns_dir.is_dir():
            return []
        return sorted(d.name for d in patterns_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

    def get_argumentation_pattern(self, name: str) -> dict[str, str] | None:
        """Get all role prompts for a given argumentation pattern.

        Returns a dict mapping role_type_id -> prompt content,
        or None if the pattern directory does not exist.
        """
        pattern_dir = Path(f"profiles/argumentation-patterns/{name}")
        if not pattern_dir.is_dir():
            return None

        result: dict[str, str] = {}
        for md_file in sorted(pattern_dir.glob("*.md")):
            # e.g. "strategist.md" -> role_type_id = "strategist"
            role_type_id = md_file.stem
            # skip language variants like "strategist-en.md"
            if "-" in role_type_id:
                continue
            content = md_file.read_text(encoding="utf-8")
            if content.strip():
                result[role_type_id] = content

        return result if result else None

    def save_prompt_modifier(self, modifier: PromptModifier) -> None:
        """Insert or replace a prompt modifier."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_modifiers
                    (id, name, content, description, tags_json, is_system,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    modifier.id,
                    modifier.name,
                    modifier.content,
                    modifier.description,
                    json.dumps(modifier.tags),
                    int(modifier.is_system),
                    modifier.created_at.isoformat(),
                    modifier.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved prompt modifier %s", modifier.id)

    def get_prompt_modifier(self, modifier_id: str) -> PromptModifier | None:
        """Retrieve a prompt modifier by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_modifiers WHERE id = ?",
                (modifier_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_prompt_modifier(row)

    def list_prompt_modifiers(
        self,
        include_system: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptModifier]:
        """List prompt modifiers, optionally including system ones."""
        with self._connect() as conn:
            if include_system:
                rows = conn.execute(
                    "SELECT * FROM prompt_modifiers ORDER BY is_system DESC, name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM prompt_modifiers WHERE is_system = 0 ORDER BY name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._row_to_prompt_modifier(r) for r in rows]

    def delete_prompt_modifier(self, modifier_id: str) -> bool:
        """Delete a prompt modifier. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM prompt_modifiers WHERE id = ?",
                (modifier_id,),
            )
        return cursor.rowcount > 0

    def save_provenance_batch(
        self,
        session_id: str,
        workflow_id: str,
        build_responses: list[dict],
    ) -> int:
        """Persist a batch of BuildResponse provenance entries.

        Used by the Pragmatist node to record clause-level lineage
        (which Critic item a BuildResponse addresses, which draft
        version it belongs to, and the Pragmatist's verdict/score).
        The ``build_response_provenance`` table itself is created by
        migration v32 — we do not re-create it here so the schema
        stays in one place.

        One row is inserted per BuildResponse — including those with
        empty or missing ``provenance`` sub-dicts — matching the
        historical behaviour of the inline ``sqlite3`` implementation
        in ``pragmatist_nodes._save_provenance_batch``.  Missing
        fields fall back to column defaults (0, ``''``,
        ``'conservative'``, NULL).

        Args:
            session_id: Workflow session ID.
            workflow_id: Workflow definition ID.
            build_responses: List of BuildResponse dicts.  Each entry
                produces one row, regardless of whether it carries a
                ``provenance`` sub-dict.

        Returns:
            The number of rows actually inserted.
        """
        rows: list[tuple] = []
        for br in build_responses:
            prov = br.get("provenance") or {}
            rows.append(
                (
                    session_id,
                    workflow_id,
                    br.get("response_to", ""),
                    int(prov.get("draft_version", 0) or 0),
                    prov.get("critic_item_id", ""),
                    prov.get("original_text", ""),
                    prov.get("revision_type", "conservative"),
                    prov.get("pragmatist_verdict"),
                    prov.get("pragmatist_score"),
                )
            )

        if not rows:
            return 0

        with self._connect() as conn:
            conn.executemany(
                """INSERT INTO build_response_provenance
                   (session_id, workflow_id, response_to, draft_version,
                    critic_item_id, original_text, revision_type,
                    pragmatist_verdict, pragmatist_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        logger.debug("Saved %d provenance records for session %s", len(rows), session_id)
        return len(rows)

    @staticmethod
    def _row_to_prompt_modifier(row: sqlite3.Row) -> PromptModifier:
        """Convert a SQLite row to a PromptModifier model."""
        return PromptModifier(
            id=row["id"],
            name=row["name"],
            content=row["content"],
            description=row["description"],
            tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
            is_system=bool(row["is_system"]) if "is_system" in row.keys() else False,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.now(),
        )
