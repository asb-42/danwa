"""Migration v024: rewrite DMS ChromaDB project_id from
``case:{tenant_id}:{case_id}`` to ``{case_id}``.

Background
----------
The case-scoped DMS used to bind documents under a synthetic scope id
``case:{tenant_id}:{case_id}`` (defence-in-depth against cross-tenant
collisions in the shared ChromaDB collection).  The legacy debate
workflow, however, passes only the bare ``case_id`` to the RAG
resolver, so the synthetic-scope documents were invisible to
``get_chunks_by_document`` (ChromaDB's ``where={"project_id": case_id}``
filter returned zero results).  This caused agents to see ``"Dokument
nicht im RAG abfuefbar"`` in the MVP and legacy debate views.

The case-scoped factory was simplified to bind the DMS to the bare
``case_id`` (see ``_get_dms_for_case``).  This migration rewrites the
existing chunks' ``project_id`` metadata so old data is visible again
without a re-index.

Safe to re-run: each chunk is updated only if its current ``project_id``
matches the synthetic scope pattern.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Match the legacy synthetic scope id: "case:{tenant}:{case_id}".
_SCOPE_RE = re.compile(r"^case:([^:]+):(.+)$")

# Per-tenant directory where case directories live.
_TENANTS_BASE = Path("data") / "tenants"


def migrate(case_id: str | None = None, dry_run: bool = False) -> int:
    """Rewrite chunks' project_id for the given case (or all cases).

    Args:
        case_id:  If given, only migrate this case.  Otherwise scan
            every case directory under ``data/tenants/*/cases/*/``.
        dry_run:  If True, log the intended changes but don't write.

    Returns:
        Number of chunks rewritten.
    """
    if not _TENANTS_BASE.is_dir():
        logger.info("v024: no tenants directory at %s, nothing to migrate", _TENANTS_BASE)
        return 0

    targets: list[Path] = []
    if case_id:
        for tenant_dir in _TENANTS_BASE.iterdir():
            candidate = tenant_dir / "cases" / case_id
            if candidate.is_dir():
                targets.append(candidate)
    else:
        for tenant_dir in sorted(_TENANTS_BASE.iterdir()):
            if not tenant_dir.is_dir():
                continue
            cases_dir = tenant_dir / "cases"
            if not cases_dir.is_dir():
                continue
            for case_dir in sorted(cases_dir.iterdir()):
                if case_dir.is_dir():
                    targets.append(case_dir)

    total = 0
    for case_dir in targets:
        chroma_dir = case_dir / "dms" / "chroma_db"
        if not chroma_dir.is_dir():
            continue
        # Locate the "document_chunks" collection directory.  ChromaDB
        # stores one sub-dir per collection under <chroma_dir>/<uuid>/.
        # We don't have the collection name baked in here, so we
        # look for the SQLite parquet/level files inside each
        # sub-dir.  Instead of doing low-level parsing we re-use
        # the runtime ChromaDB client to enumerate and update.
        try:
            import chromadb  # noqa: PLC0415

            client = chromadb.PersistentClient(path=str(chroma_dir))
        except Exception as exc:
            logger.warning("v024: could not open ChromaDB at %s: %s", chroma_dir, exc)
            continue

        for collection in client.list_collections():
            try:
                coll = client.get_collection(collection.name)
            except Exception as exc:
                logger.warning(
                    "v024: could not open collection %s in %s: %s",
                    collection.name,
                    chroma_dir,
                    exc,
                )
                continue

            # Fetch all rows so we can inspect their project_id.
            try:
                rows = coll.get(include=["metadatas"])
            except Exception as exc:
                logger.warning(
                    "v024: get() failed for collection %s: %s",
                    collection.name,
                    exc,
                )
                continue

            ids = rows.get("ids", []) or []
            metadatas = rows.get("metadatas", []) or []
            updates: list[tuple[str, dict]] = []
            for cid, meta in zip(ids, metadatas):
                meta = meta or {}
                current = str(meta.get("project_id", ""))
                m = _SCOPE_RE.match(current)
                if not m:
                    continue
                bare = m.group(2)
                new_meta = dict(meta)
                new_meta["project_id"] = bare
                # Track the original scope id so the migration is
                # observable in audit logs.
                new_meta.setdefault("_legacy_project_id", current)
                updates.append((cid, new_meta))

            if not updates:
                continue

            logger.info(
                "v024: %s — rewriting %d chunks (case_dir=%s, dry_run=%s)",
                collection.name,
                len(updates),
                case_dir,
                dry_run,
            )

            if not dry_run:
                try:
                    coll.update(ids=[u[0] for u in updates], metadatas=[u[1] for u in updates])
                    total += len(updates)
                except Exception as exc:
                    logger.error(
                        "v024: update() failed for collection %s: %s",
                        collection.name,
                        exc,
                    )

    logger.info("v024 migration complete: %d chunks rewritten (dry_run=%s)", total, dry_run)
    return total


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Rewrite DMS ChromaDB project_id from synthetic scope to bare case_id")
    parser.add_argument("--case-id", default=None, help="Migrate a single case_id only (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be changed without writing")
    args = parser.parse_args()
    n = migrate(case_id=args.case_id, dry_run=args.dry_run)
    print(f"Migrated {n} chunks" + (" (dry run)" if args.dry_run else ""))
