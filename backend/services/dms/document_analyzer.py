"""Document analysis — uses LLM to summarize and structure project documents."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from backend.services.llm_service import LLMService
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a legal document analyst. Your task is to analyze the
provided documents and produce a structured case analysis in JSON format.

Analyze the documents and return ONLY valid JSON with this exact structure:
{
  "case_summary": "A comprehensive 2-3 paragraph summary of the entire case",
  "key_facts": ["List of the most important factual points"],
  "parties": [
    {"name": "Name of person or entity", "role": "Their role in the case", "positions": "Their stated positions or interests"}
  ],
  "timeline": [
    {"date": "Date or time period", "event": "Description of what happened"}
  ],
  "key_issues": ["The main legal or factual issues to be debated"],
  "documents": [
    {"filename": "Document name", "summary": "Brief summary", "key_excerpts": ["Important quotes or passages"]}
  ]
}

Rules:
- Be thorough but concise
- Extract specific dates, names, amounts, and concrete facts
- Note any contradictions or inconsistencies between documents
- Identify missing information that would be relevant
- Output ONLY the JSON object, no markdown, no explanations"""


def select_service_llm(profile_service: ProfileService) -> str:
    """Select a suitable LLM profile for document analysis."""
    for p in profile_service.list_llm_profiles():
        if p.is_service_llm_eligible and p.provider and ("openrouter" in p.provider.lower() or "openai" in p.provider.lower()):
            if p.context_length and p.context_length >= 128000:
                return p.id
    for p in profile_service.list_llm_profiles():
        if p.is_service_llm_eligible:
            return p.id
    profiles = profile_service.list_llm_profiles()
    if profiles:
        return profiles[0].id
    raise ValueError("No LLM profiles available")


def analyze_documents(
    document_texts: list[dict[str, str]],
    profile_service: ProfileService,
    profile_id: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """Analyze a set of documents and return a structured case analysis.

    Args:
        document_texts: List of {"filename": str, "text": str} dicts.
        profile_service: ProfileService for LLM profile lookup.
        profile_id: Optional explicit LLM profile ID.
        timeout: Max seconds to wait for LLM response.

    Returns:
        Dict with analysis fields, or error dict.
    """
    if not document_texts:
        return {"error": "No documents to analyze"}

    llm_profile_id = profile_id or select_service_llm(profile_service)
    logger.info("Using LLM profile %s for document analysis of %d documents", llm_profile_id, len(document_texts))

    llm = LLMService(profile_id=llm_profile_id, profile_service=profile_service)

    doc_texts_str = ""
    for i, doc in enumerate(document_texts):
        text = doc.get("text", "")[:20000]
        doc_texts_str += f"\n--- Document {i + 1}: {doc.get('filename', 'unknown')} ---\n{text}\n"

    user_prompt = f"""Analyze the following {len(document_texts)} document(s) and produce a structured case analysis:

{doc_texts_str}

Return ONLY valid JSON following the required structure."""

    try:
        result = llm.generate_sync(
            prompt=user_prompt,
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=8192,
            context="Document Analysis",
        )
    except Exception as e:
        logger.error("LLM analysis failed: %s", e)
        return {"error": f"Analysis failed: {e}"}

    content = result.content.strip()
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        logger.error("No JSON found in LLM response")
        return {"error": "Analysis produced unexpected output", "raw": content[:500]}

    try:
        analysis = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        logger.error("Failed to parse analysis JSON: %s", e)
        return {"error": f"Failed to parse analysis: {e}", "raw": content[:500]}

    analysis["_model"] = result.model
    analysis["_tokens_in"] = result.tokens_in
    analysis["_tokens_out"] = result.tokens_out
    analysis["_duration_ms"] = result.duration_ms

    return analysis


def load_analysis(project_dir: str | Path) -> dict[str, Any] | None:
    """Load a stored analysis JSON from the project directory."""
    path = Path(project_dir) / "analysis.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load analysis from %s: %s", path, e)
        return None


def save_analysis(project_dir: str | Path, analysis: dict[str, Any]) -> None:
    """Save analysis JSON to the project directory."""
    path = Path(project_dir) / "analysis.json"
    try:
        path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved analysis to %s", path)
    except OSError as e:
        logger.error("Failed to save analysis to %s: %s", path, e)
