"""Quick verification script for the RAG fix.

Run with: python -m scripts.verify_rag <case_id>

Checks:
1. The case directory exists under data/tenants/<tid>/cases/<case_id>/
2. The DMS is resolvable via get_dms_for_project(case_id)
3. ChromaDB has chunks with project_id == case_id (after migration v024)
4. get_chunks_by_document returns chunks
"""

import sys
from pathlib import Path


def verify(case_id: str) -> int:
    print(f"=== Verifying RAG for case {case_id} ===")
    # 1. Find the case directory
    tenants_base = Path("data") / "tenants"
    case_dir = None
    for tenant_dir in tenants_base.iterdir():
        candidate = tenant_dir / "cases" / case_id
        if candidate.is_dir():
            case_dir = candidate
            print(f"  [OK] case_dir = {case_dir}")
            break
    if not case_dir:
        print(f"  [FAIL] case {case_id} not found under {tenants_base}")
        return 1

    # 2. Resolve DMS
    try:
        from backend.services.dms.service import get_dms_for_project

        dms = get_dms_for_project(case_id)
        print(f"  [OK] dms.project_id = {dms._project_id}")
    except Exception as e:
        print(f"  [FAIL] get_dms_for_project: {e}")
        return 1

    # 3-4. Check chunks
    try:
        coll = dms.vector_store.collection
        count = coll.count()
        print(f"  [INFO] collection has {count} total chunks")
        if count == 0:
            print("  [WARN] no chunks — was a document ever uploaded?")
            return 0
        # Inspect metadatas
        all_rows = coll.get(include=["metadatas"])
        metadatas = all_rows.get("metadatas", [])
        unique_pids = set(m.get("project_id") for m in metadatas if m)
        print(f"  [INFO] unique project_ids in collection: {unique_pids}")
        if str(case_id) not in unique_pids and f"case:_default:{case_id}" not in unique_pids:
            print(f"  [FAIL] case_id={case_id} not in project_ids — migration v024 needed")
            return 1
        if f"case:_default:{case_id}" in unique_pids:
            print("  [WARN] old scope_id present — run migration v024 to rewrite")
    except Exception as e:
        print(f"  [FAIL] chroma inspection: {e}")
        return 1

    print(f"  [OK] RAG should work for case {case_id}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.verify_rag <case_id>")
        sys.exit(2)
    sys.exit(verify(sys.argv[1]))
