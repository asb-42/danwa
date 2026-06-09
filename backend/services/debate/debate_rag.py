"""RAG context resolution for debates."""

from __future__ import annotations

import logging
from typing import Any

from backend.persistence.debate_store import DebateStore

logger = logging.getLogger(__name__)


def _format_analysis_for_rag(analysis: dict) -> str:
    """Format a document analysis dict as RAG context text.

    Shared helper used by ``resolve_rag_context`` and
    ``resolve_rag_context_with_debate_results``.
    """
    parts = [
        "=== DOCUMENT ANALYSIS ===",
        "The following is a structured case analysis of the uploaded documents. "
        "Use it as your PRIMARY source of case context — it summarizes the key facts, "
        "parties, timeline, and issues. The raw document excerpts below are for "
        "fact-checking and finding exact quotes.",
        "",
        f"Case Summary: {analysis.get('case_summary', '')}",
    ]
    if analysis.get("key_facts"):
        parts.append("Key Facts:\n- " + "\n- ".join(analysis["key_facts"]))
    if analysis.get("parties"):
        lines = [f"  {p['name']} ({p['role']}): {p['positions']}" for p in analysis["parties"]]
        parts.append("Parties:\n" + "\n".join(lines))
    if analysis.get("timeline"):
        lines = [f"  {t['date']} — {t['event']}" for t in analysis["timeline"]]
        parts.append("Timeline:\n" + "\n".join(lines))
    if analysis.get("key_issues"):
        parts.append("Key Issues:\n- " + "\n- ".join(analysis["key_issues"]))
    return "\n\n".join(parts)


def _load_analysis_text(project_id: str, project_store=None) -> str:
    """Load and format document analysis for a project, or return empty string."""
    from backend.api.deps import get_case_dir
    from backend.services.dms.document_analyzer import load_analysis

    try:
        project_dir = get_case_dir(project_id)
        analysis = load_analysis(project_dir)
        if analysis and "error" not in analysis:
            logger.info("Loaded document analysis for project %s", project_id)
            return _format_analysis_for_rag(analysis)
    except Exception as exc:
        logger.debug("Could not load document analysis for project %s: %s", project_id, exc)
    return ""


def resolve_rag_context(
    project_id: str,
    case_text: str,
    document_ids: list[str] | None = None,
    rag_auto_retrieve: bool = False,
    include_debate_results: bool = False,
    debate_result_ids: list[str] | None = None,
    project_store: Any | None = None,
    store: DebateStore | None = None,
    include_document_analysis: bool = False,
) -> tuple[str, int]:
    """Resolve RAG context for a debate.

    Returns (rag_context_string, document_count).

    The ``project_store`` parameter is kept for backward compatibility but
    is no longer required.
    """
    from backend.api.deps import get_case_dir

    # Lazy imports to avoid circular dependency with debate_workflow
    from backend.services.debate_workflow import _build_transcript_for_followup, _generate_rag_friendly_summary
    from backend.services.dms.service import get_dms_for_project

    analysis_text = _load_analysis_text(project_id, project_store) if include_document_analysis else ""

    try:
        dms = get_dms_for_project(project_id)
    except Exception as exc:
        logger.warning("Could not initialize DMS for project %s: %s", project_id, exc)
        if analysis_text:
            return analysis_text, 0
        return "", 0

    all_chunks: list[dict] = []

    if document_ids:
        for doc_id in document_ids:
            try:
                chunks = dms.metadata_index.get_chunks_by_document(doc_id)
                logger.info("get_chunks_by_document(%s) returned %d chunks", doc_id, len(chunks))
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning("Failed to get chunks for document %s: %s", doc_id, exc)

        if not all_chunks:
            logger.warning(
                "Explicit document_ids %s returned zero chunks — documents may not be indexed in ChromaDB yet",
                document_ids,
            )

    elif rag_auto_retrieve and case_text:
        # Auto-retrieval only when no explicit documents are selected.
        # Never blends with explicit document selection to prevent spillover
        # from unrelated project documents.
        try:
            auto_chunks = dms.auto_retrieve_for_topic(case_text, project_id=project_id, k=10)
            logger.info(
                "Auto-retrieve returned %d chunks for project %s",
                len(auto_chunks),
                project_id,
            )
            all_chunks.extend(auto_chunks)
        except Exception as exc:
            logger.warning("Auto-retrieve failed for project %s: %s", project_id, exc)

    if include_debate_results:
        try:
            project_dir = get_case_dir(project_id)
            proj_store = DebateStore(data_dir=project_dir / "debates")

            debates = proj_store.list_all(limit=50)

            if debate_result_ids:
                debate_ids_set = set(debate_result_ids)
                debates = [d for d in debates if d.get("debate_id") in debate_ids_set]
                logger.info(
                    "Including %d specific debate result(s) for project %s",
                    len(debates),
                    project_id,
                )
            else:
                logger.info(
                    "Auto-selecting up to 5 recent completed debates for project %s",
                    project_id,
                )

            debate_count = 0
            from backend.services.dms.chunker import TextChunker

            chunker = TextChunker()

            for d in debates:
                if d.get("status") in ("completed",) and d.get("debate_id"):
                    if debate_result_ids and d.get("debate_id") not in debate_ids_set:
                        continue
                    transcript = _build_transcript_for_followup(d)
                    summary = _generate_rag_friendly_summary(transcript)
                    raw_chunks = chunker.chunk(summary)
                    chunks = [{"text": t, "document_id": f"debate_result_{d.get('debate_id', '')[:8]}"} for t in raw_chunks]
                    all_chunks.extend(chunks[:3])

                    debate_count += 1
                    if not debate_result_ids and debate_count >= 5:
                        break
        except Exception as exc:
            logger.warning("Failed to include debate results in RAG context: %s", exc)

    if not all_chunks:
        if analysis_text:
            logger.info("Document analysis available but no chunks — returning analysis-only RAG context")
            return analysis_text, 0
        return "", 0

    seen_texts: set[str] = set()
    unique_chunks: list[dict] = []
    for chunk in all_chunks:
        text = chunk.get("text", "")
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_chunks.append(chunk)

    if document_ids:
        rag_context = dms.format_rag_context(unique_chunks, max_chars=80_000)
    else:
        rag_context = dms.format_rag_context(unique_chunks)
    doc_count = len(document_ids) if document_ids else 0

    if analysis_text:
        rag_context = f"{analysis_text}\n\n=== DOCUMENT EXCERPTS ===\n\n{rag_context}" if rag_context else analysis_text
        logger.info("Prepended document analysis to RAG context for project %s", project_id)

    logger.info(
        "RAG context resolved for project %s: %d unique chunks from %d documents",
        project_id,
        len(unique_chunks),
        doc_count,
    )
    return rag_context, doc_count


def resolve_rag_context_with_debate_results(
    project_id: str,
    case_text: str,
    document_ids: list[str] | None = None,
    rag_auto_retrieve: bool = False,
    include_debate_results: bool = True,
    store: DebateStore | None = None,
    project_store: Any | None = None,
    include_document_analysis: bool = False,
) -> tuple[str, int]:
    """Erweitert RAG-Kontext um vorherige Debattenergebnisse (P3).

    The ``project_store`` parameter is kept for backward compatibility but
    is no longer required.
    """
    from backend.api.deps import get_case_dir
    from backend.services.debate_workflow import _build_transcript_for_followup, _generate_rag_friendly_summary
    from backend.services.dms.service import get_dms_for_project

    analysis_text = _load_analysis_text(project_id, project_store) if include_document_analysis else ""

    try:
        dms = get_dms_for_project(project_id)
    except Exception:
        if analysis_text:
            return analysis_text, 0
        return "", 0

    all_chunks = []

    # Standard-DMS-RAG
    if document_ids:
        for doc_id in document_ids:
            try:
                chunks = dms.metadata_index.get_chunks_by_document(doc_id)
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning("Failed to get chunks for document %s: %s", doc_id, exc)

        if not all_chunks and document_ids:
            logger.warning(
                "Document IDs %s returned zero chunks — documents may not be indexed",
                document_ids,
            )

    elif rag_auto_retrieve and case_text:
        try:
            auto_chunks = dms.auto_retrieve_for_topic(case_text, project_id=project_id, k=10)
            all_chunks.extend(auto_chunks)
        except Exception as exc:
            logger.warning("Auto-retrieve failed for project %s: %s", project_id, exc)

    # Zusätzlich: Debattenergebnisse als Kontext einbeziehen
    if include_debate_results:
        try:
            project_dir = get_case_dir(project_id)
            debate_store = DebateStore(data_dir=project_dir / "debates")

            debates = debate_store.list_all(limit=50)
            debate_count = 0
            from backend.services.dms.chunker import TextChunker

            chunker = TextChunker()

            for d in debates:
                if d.get("status") in ("completed",) and d.get("debate_id") != "":
                    transcript = _build_transcript_for_followup(d)
                    summary = _generate_rag_friendly_summary(transcript)
                    raw_chunks = chunker.chunk(summary)
                    chunks = [{"text": t, "document_id": f"debate_result_{d.get('debate_id', '')[:8]}"} for t in raw_chunks]
                    all_chunks.extend(chunks[:3])

                    debate_count += 1
                    if debate_count >= 5:
                        break
        except Exception as exc:
            logger.warning("Failed to include debate results in RAG context: %s", exc)

    if not all_chunks:
        if analysis_text:
            logger.info("Document analysis available but no chunks — returning analysis-only RAG context")
            return analysis_text, 0
        return "", 0

    # Deduplizierung
    seen_texts: set[str] = set()
    unique_chunks: list[dict] = []
    for chunk in all_chunks:
        text = chunk.get("text", "")
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_chunks.append(chunk)

    rag_context = dms.format_rag_context(unique_chunks)

    if analysis_text:
        rag_context = f"{analysis_text}\n\n=== DOCUMENT EXCERPTS ===\n\n{rag_context}" if rag_context else analysis_text

    return rag_context, len(unique_chunks)
