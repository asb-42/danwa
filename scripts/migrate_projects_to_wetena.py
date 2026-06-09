"""Migrate legacy projects to the Wetena tenant.

Mapping:
  - 1 Project  →  1 Tag (identical label)
  - 1 Debate inside a Project  →  1 Case (title = project name, tagged with the project's tag)

Original data under ``data/tenants/_default/cases/`` is preserved
(read-only) so debates remain accessible from the old paths.

Idempotent: re-running skips already-migrated tags and cases.

Usage::

    .venv/bin/python scripts/migrate_projects_to_wetena.py
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WETENA_TENANT_ID = "8478b565-cb35-493e-b46f-c756311dc65b"
SOURCE_TENANT_ID = "_default"

BASE_DIR = Path("data")
SOURCE_CASES_DIR = BASE_DIR / "tenants" / SOURCE_TENANT_ID / "cases"
WETENA_TENANT_DIR = BASE_DIR / "tenants" / WETENA_TENANT_ID

# Colours assigned to tags by project name hash (cosmetic, no functional impact)
TAG_COLOURS = [
    "#6366f1",
    "#ec4899",
    "#f59e0b",
    "#10b981",
    "#3b82f6",
    "#8b5cf6",
    "#ef4444",
    "#14b8a6",
    "#f97316",
    "#06b6d4",
    "#84cc16",
    "#e11d48",
    "#a855f7",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("migrate")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_project(project_dir: Path) -> dict | None:
    """Load and return a project.json, or None on error."""
    json_path = project_dir / "project.json"
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Cannot read %s: %s", json_path, exc)
        return None


def _load_tags_for_tenant(tenant_id: str) -> dict[str, dict]:
    """Load tags.json for a tenant. Returns {name: tag_dict}."""
    tags_path = WETENA_TENANT_DIR / "tags.json"
    if not tags_path.exists():
        return {}
    try:
        data = json.loads(tags_path.read_text(encoding="utf-8"))
        return {t["name"]: t for t in data}
    except Exception as exc:
        logger.warning("Cannot read %s: %s", tags_path, exc)
        return {}


def _save_tags_for_tenant(tenant_id: str, tags: dict[str, dict]) -> None:
    """Persist tags.json for a tenant."""
    tags_path = WETENA_TENANT_DIR / "tags.json"
    tags_path.parent.mkdir(parents=True, exist_ok=True)
    tags_path.write_text(
        json.dumps(list(tags.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _case_exists(case_id: str) -> bool:
    """Check whether a case directory already exists under Wetena."""
    return (WETENA_TENANT_DIR / "cases" / case_id / "case.json").exists()


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------


def migrate(dry_run: bool = False) -> None:
    """Run the migration.

    Parameters
    ----------
    dry_run:
        If True, log what *would* happen without writing anything.
    """
    if not SOURCE_CASES_DIR.is_dir():
        logger.error("Source directory does not exist: %s", SOURCE_CASES_DIR)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Phase 1 — Collect projects
    # ------------------------------------------------------------------
    projects: list[tuple[str, str, Path]] = []  # (project_id, name, dir)
    for project_dir in sorted(SOURCE_CASES_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        data = _load_project(project_dir)
        if data is None:
            continue
        project_id = data["id"]
        name = data.get("name", project_id)
        projects.append((project_id, name, project_dir))

    logger.info("Found %d projects in _default tenant", len(projects))

    # ------------------------------------------------------------------
    # Phase 2 — Create / reuse tags
    # ------------------------------------------------------------------
    existing_tags = _load_tags_for_tenant(WETENA_TENANT_ID)
    tag_map: dict[str, str] = {}  # project_name -> tag_id

    for idx, (project_id, name, _dir) in enumerate(projects):
        if name in existing_tags:
            tag_map[name] = existing_tags[name]["id"]
            logger.debug("Tag already exists: %s -> %s", name, tag_map[name])
            continue

        tag_id = str(__import__("uuid").uuid4())
        tag_dict = {
            "id": tag_id,
            "tenant_id": WETENA_TENANT_ID,
            "name": name,
            "color": TAG_COLOURS[idx % len(TAG_COLOURS)],
            "parent_id": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        existing_tags[name] = tag_dict
        tag_map[name] = tag_id
        logger.info("Created tag: '%s' (id=%s)", name, tag_id)

    if not dry_run:
        _save_tags_for_tenant(WETENA_TENANT_ID, existing_tags)
        logger.info("Persisted %d tags", len(existing_tags))

    # ------------------------------------------------------------------
    # Phase 3 — Migrate debates → cases
    # ------------------------------------------------------------------
    total_debates = 0
    migrated = 0
    skipped = 0

    for project_id, project_name, project_dir in projects:
        debates_dir = project_dir / "debates"
        if not debates_dir.is_dir():
            continue

        debate_files = sorted(debates_dir.glob("*.json"))
        if not debate_files:
            continue

        tag_id = tag_map[project_name]
        logger.info(
            "Project '%s' — %d debates, tag_id=%s",
            project_name,
            len(debate_files),
            tag_id,
        )

        for debate_path in debate_files:
            total_debates += 1

            try:
                debate_data = json.loads(debate_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Cannot read debate %s: %s", debate_path, exc)
                continue

            debate_id = debate_data.get("debate_id", debate_path.stem)
            debate_title = debate_data.get("title", "")
            case_id = debate_id  # Use debate_id as case_id for traceability

            if _case_exists(case_id):
                skipped += 1
                logger.debug("  Skip (already migrated): %s", case_id)
                continue

            migrated += 1

            if dry_run:
                logger.info(
                    "  [DRY-RUN] Would create case: id=%s, title='%s', debate_title='%s', tags=[%s]",
                    case_id,
                    project_name,
                    debate_title,
                    tag_id,
                )
                continue

            # Create case directory and case.json
            case_dir = WETENA_TENANT_DIR / "cases" / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "debates").mkdir(parents=True, exist_ok=True)
            (case_dir / "dms").mkdir(parents=True, exist_ok=True)

            case_data = {
                "id": case_id,
                "tenant_id": WETENA_TENANT_ID,
                "title": project_name,
                "description": debate_title,
                "status": "active",
                "tags": [tag_id],
                "created_by": "migration",
                "created_at": debate_data.get("created_at", datetime.now(UTC).isoformat()),
                "updated_at": debate_data.get("updated_at", datetime.now(UTC).isoformat()),
                "metadata": {
                    "source_project_id": project_id,
                    "source_project_name": project_name,
                    "source_debate_id": debate_id,
                    "source_debate_title": debate_title,
                    "migrated_at": datetime.now(UTC).isoformat(),
                },
            }
            (case_dir / "case.json").write_text(
                json.dumps(case_data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

            # Copy debate JSON into the new case's debates/ directory
            shutil.copy2(debate_path, case_dir / "debates" / debate_path.name)

        # Copy analysis.json if present at the project level
        analysis_path = project_dir / "analysis.json"
        if analysis_path.exists():
            # Attach it to the first case of this project as reference
            first_debate = sorted(debates_dir.glob("*.json"))
            if first_debate:
                first_case_id = json.loads(first_debate[0].read_text()).get(
                    "debate_id",
                    first_debate[0].stem,
                )
                target_dir = WETENA_TENANT_DIR / "cases" / first_case_id
                if target_dir.is_dir():
                    target_analysis = target_dir / "analysis.json"
                    if not target_analysis.exists():
                        shutil.copy2(analysis_path, target_analysis)
                        logger.debug(
                            "  Copied analysis.json to case %s",
                            first_case_id,
                        )

    logger.info(
        "Migration complete: %d debates found, %d migrated, %d skipped (already exist)",
        total_debates,
        migrated,
        skipped,
    )

    # ------------------------------------------------------------------
    # Phase 4 — Summary
    # ------------------------------------------------------------------
    if dry_run:
        logger.info("[DRY-RUN] No changes were made.")
    else:
        logger.info("Tags in Wetena: %d", len(existing_tags))
        logger.info(
            "Cases in Wetena: %d",
            sum(1 for d in (WETENA_TENANT_DIR / "cases").iterdir() if d.is_dir() and (d / "case.json").exists())
            if (WETENA_TENANT_DIR / "cases").is_dir()
            else 0,
        )


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        logger.info("=== DRY RUN MODE ===")
    migrate(dry_run=dry)
