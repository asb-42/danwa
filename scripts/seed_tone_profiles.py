"""Seed system tone profiles into the database.

Creates three built-in ToneProfiles: heated, academic, neutral.
These are marked as ``is_system=True`` and cannot be edited or deleted.

Idempotent — safe to call multiple times.

Usage:
    uv run python -m scripts.seed_tone_profiles
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.blueprints.models import ToneProfile
from backend.blueprints.repository import BlueprintRepository

logger = logging.getLogger(__name__)

SYSTEM_PROFILES: list[dict] = [
    {
        "id": "system-heated",
        "name": "Heated Debate",
        "description": "A confrontational, emotionally charged debate style. Agents challenge each other aggressively and use rhetorical devices.",
        "style": "heated",
        "formality": 0.3,
        "verbosity": "verbose",
        "emotional_valence": 0.9,
        "rhetorical_mode": "assertive",
        "custom_instructions": None,
    },
    {
        "id": "system-academic",
        "name": "Academic Debate",
        "description": "A formal, evidence-based debate style. Agents cite sources, use precise language, and maintain scholarly decorum.",
        "style": "academic",
        "formality": 0.9,
        "verbosity": "normal",
        "emotional_valence": 0.2,
        "rhetorical_mode": "dialectic",
        "custom_instructions": None,
    },
    {
        "id": "system-neutral",
        "name": "Neutral / Sachlich",
        "description": "A balanced, objective debate style. Agents present facts and arguments without emotional coloring.",
        "style": "neutral",
        "formality": 0.5,
        "verbosity": "normal",
        "emotional_valence": 0.3,
        "rhetorical_mode": "none",
        "custom_instructions": None,
    },
]


def seed_system_tone_profiles(
    repo: BlueprintRepository | None = None,
) -> dict[str, int]:
    """Seed system tone profiles.

    Parameters
    ----------
    repo:
        Repository instance. If ``None``, a default instance is created.

    Returns
    -------
    dict:
        ``{"created": N, "updated": N, "skipped": N}``
    """
    if repo is None:
        repo = BlueprintRepository()

    result = {"created": 0, "updated": 0, "skipped": 0}

    for data in SYSTEM_PROFILES:
        data["is_system"] = True
        now = datetime.now(UTC)
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)

        profile = ToneProfile.model_validate(data)
        existing = repo.get_tone_profile(profile.id)

        if existing:
            # Compare to detect changes
            old_json = existing.model_dump_json()
            new_json = profile.model_dump_json()
            if old_json == new_json:
                result["skipped"] += 1
                continue
            profile.updated_at = now
            repo.save_tone_profile(profile)
            result["updated"] += 1
            logger.info("Updated system tone profile: %s", profile.id)
        else:
            repo.save_tone_profile(profile)
            result["created"] += 1
            logger.info("Created system tone profile: %s", profile.id)

    logger.info(
        "Tone profile seed complete: created=%d, updated=%d, skipped=%d",
        result["created"],
        result["updated"],
        result["skipped"],
    )
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_system_tone_profiles()
