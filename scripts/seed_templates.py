"""Seed system workflow templates into the database.

Reads JSON template definitions from the ``templates/`` directory and
upserts them into the ``workflow_templates`` table with ``is_system=True``.

Idempotent — safe to call multiple times. Existing system templates are
updated only if their content has changed.

Usage:
    uv run python -m scripts.seed_templates
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import WorkflowTemplate

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def seed_system_templates(
    repo: BlueprintRepository | None = None,
    templates_dir: Path | None = None,
) -> dict[str, int]:
    """Seed system workflow templates from JSON files.

    Parameters
    ----------
    repo:
        Repository instance. If ``None``, a default instance is created.
    templates_dir:
        Directory containing template JSON files. Defaults to ``templates/``
        in the project root.

    Returns
    -------
    dict:
        ``{"created": N, "updated": N, "skipped": N}``
    """
    if repo is None:
        repo = BlueprintRepository()
    if templates_dir is None:
        templates_dir = _TEMPLATES_DIR

    result = {"created": 0, "updated": 0, "skipped": 0}

    if not templates_dir.is_dir():
        logger.warning("Templates directory not found: %s", templates_dir)
        return result

    json_files = sorted(templates_dir.glob("*.json"))
    if not json_files:
        logger.info("No template JSON files found in %s", templates_dir)
        return result

    for json_file in json_files:
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            # Force system flag
            data["is_system"] = True
            data["category"] = "system"
            template = WorkflowTemplate.model_validate(data)
            _upsert_template(repo, template, result)
        except Exception as exc:
            logger.warning("Failed to seed template from %s: %s", json_file, exc)

    logger.info(
        "Seed complete: created=%d, updated=%d, skipped=%d",
        result["created"],
        result["updated"],
        result["skipped"],
    )
    return result


def _upsert_template(
    repo: BlueprintRepository,
    template: WorkflowTemplate,
    result: dict[str, int],
) -> None:
    """Idempotent upsert for a single template."""
    existing = repo.get_workflow_template(template.id)
    if existing:
        # Compare serialized content to detect changes
        old_hash = json.dumps(existing.template_data, sort_keys=True)
        new_hash = json.dumps(template.template_data, sort_keys=True)
        old_ph = json.dumps([p.model_dump() for p in existing.placeholders], sort_keys=True)
        new_ph = json.dumps([p.model_dump() for p in template.placeholders], sort_keys=True)
        if old_hash == new_hash and existing.name == template.name and old_ph == new_ph:
            result["skipped"] += 1
            return
        template.updated_at = datetime.now(UTC)
        repo.save_workflow_template(template)
        result["updated"] += 1
        logger.info("Updated system template: %s", template.id)
    else:
        repo.save_workflow_template(template)
        result["created"] += 1
        logger.info("Created system template: %s", template.id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_system_templates()
