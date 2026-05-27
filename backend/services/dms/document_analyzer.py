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
- Output ONLY the JSON object, no markdown, no explanations
- Write ALL text in the specified language — field names stay in English, but all
  content (summaries, facts, descriptions, excerpts) must be in that language"""

ANALYSIS_UPDATE_SYSTEM_PROMPT = """You are a legal document analyst updating an existing case analysis
with information from newly added documents.

You will receive:
1. The existing case analysis (JSON)
2. One or more new documents

Your task is to produce an UPDATED analysis that merges the new information
into the existing structure. Return ONLY valid JSON with the same structure.

Rules:
- PRESERVE all existing analysis content (don't rewrite it unless new docs change it)
- ADD new documents to the "documents" array with their summaries and key excerpts
- UPDATE case_summary, key_facts, parties, timeline, and key_issues where the new
  documents add relevant information
- Note any contradictions between new and existing documents
- Output ONLY the JSON object, no markdown, no explanations
- Write ALL text in the specified language — field names stay in English, but all content
  (summaries, facts, descriptions, excerpts) must be in that language"""


def select_service_llm(profile_service: ProfileService) -> str:
    """Select a suitable LLM profile for document analysis.

    Follows the same selection order as the rest of the codebase:
    1. Configured ``service_llm_profile_id`` (if eligible).
    2. First service-eligible profile.
    3. First available profile.
    """
    from backend.core.config import is_service_llm_eligible, settings

    if settings.service_llm_profile_id:
        preferred = profile_service.get_llm_profile(settings.service_llm_profile_id)
        if preferred and is_service_llm_eligible(preferred)[0]:
            return settings.service_llm_profile_id

    for p in profile_service.list_llm_profiles():
        if is_service_llm_eligible(p)[0]:
            return p.id
    profiles = profile_service.list_llm_profiles()
    if profiles:
        return profiles[0].id
    raise ValueError("No LLM profiles available")


def _build_system_prompt(language: str) -> str:
    """Build the system prompt with language instruction."""
    lang_instruction = f"\n- Write ALL text in {language} — field names stay in English, but all content must be in {language}"
    return ANALYSIS_SYSTEM_PROMPT.replace(
        "- Output ONLY the JSON object, no markdown, no explanations",
        f"- Output ONLY the JSON object, no markdown, no explanations{lang_instruction}",
    )


def _build_update_system_prompt(language: str) -> str:
    """Build the update system prompt with language instruction."""
    lang_instruction = f"\n- Write ALL text in {language} — field names stay in English, but all content must be in {language}"
    return ANALYSIS_UPDATE_SYSTEM_PROMPT.replace(
        "- Output ONLY the JSON object, no markdown, no explanations",
        f"- Output ONLY the JSON object, no markdown, no explanations{lang_instruction}",
    )


def _extract_json(text: str) -> str | None:
    """Extract a JSON object from LLM output, handling markdown fences and noise."""
    # 1. Try content between ```json ... ``` fences
    m = re.search(r"```(?:json)?\s*\n?(\{.*?\})\n?\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # 2. Try content between ``` ... ``` (any fence)
    m = re.search(r"```\s*\n?(\{.*?\})\n?\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # 3. Try first { ... } block (greedy — outermost object)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return m.group()
    return None


def _clean_json(text: str) -> str:
    """Strip trailing commas before ] or } so json.loads can handle them."""
    # Remove trailing commas: ,] -> ], ,} -> }
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    return cleaned


def _parse_json(text: str) -> dict | None:
    """Attempt to parse JSON with progressively more aggressive cleaning."""
    candidates = [text, _clean_json(text)]
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    # Last resort: try to find any valid JSON object via brute force
    # (some LLMs produce multiple braces, control chars, etc.)
    try:
        return json.loads(_clean_json(re.sub(r"[\x00-\x1f]", "", text)))
    except (json.JSONDecodeError, ValueError):
        return None


def _call_llm(
    user_prompt: str,
    system_prompt: str,
    profile_service: ProfileService,
    profile_id: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """Call the LLM and parse the JSON response. Returns parsed analysis or error dict."""
    llm_profile_id = profile_id or select_service_llm(profile_service)

    llm = LLMService(profile_id=llm_profile_id, profile_service=profile_service)

    try:
        result = llm.generate_sync(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=8192,
            context="Document Analysis",
        )
    except Exception as e:
        logger.error("LLM analysis failed: %s", e)
        return {"error": f"Analysis failed: {e}"}

    content = result.content.strip()
    extracted = _extract_json(content)
    if not extracted:
        logger.error("No JSON found in LLM response")
        return {"error": "Analysis produced unexpected output", "raw": content[:500]}

    analysis = _parse_json(extracted)
    if not analysis:
        logger.error("Failed to parse analysis JSON")
        return {"error": "Analysis produced unparseable JSON", "raw": content[:500]}

    analysis["_model"] = result.model
    analysis["_tokens_in"] = result.tokens_in
    analysis["_tokens_out"] = result.tokens_out
    analysis["_duration_ms"] = result.duration_ms

    return analysis


def analyze_documents(
    document_texts: list[dict[str, str]],
    profile_service: ProfileService,
    profile_id: str | None = None,
    language: str = "de",
    timeout: int = 180,
) -> dict[str, Any]:
    """Analyze a set of documents and return a structured case analysis.

    Args:
        document_texts: List of {"filename": str, "text": str} dicts.
        profile_service: ProfileService for LLM profile lookup.
        profile_id: Optional explicit LLM profile ID.
        language: Language for analysis content (e.g. "de", "en").
        timeout: Max seconds to wait for LLM response.

    Returns:
        Dict with analysis fields, or error dict.
    """
    if not document_texts:
        return {"error": "No documents to analyze"}

    logger.info(
        "Analyzing %d documents (language=%s) with LLM profile",
        len(document_texts),
        language,
    )

    doc_texts_str = ""
    for i, doc in enumerate(document_texts):
        text = doc.get("text", "")[:20000]
        doc_texts_str += f"\n--- Document {i + 1}: {doc.get('filename', 'unknown')} ---\n{text}\n"

    user_prompt = f"""Analyze the following {len(document_texts)} document(s) and produce a structured case analysis:

{doc_texts_str}

Return ONLY valid JSON following the required structure."""

    system_prompt = _build_system_prompt(language)
    return _call_llm(user_prompt, system_prompt, profile_service, profile_id, timeout)


def update_analysis(
    existing_analysis: dict[str, Any],
    new_document_texts: list[dict[str, str]],
    profile_service: ProfileService,
    profile_id: str | None = None,
    language: str = "de",
    timeout: int = 180,
) -> dict[str, Any]:
    """Update an existing analysis with information from new documents.

    Args:
        existing_analysis: The current analysis dict.
        new_document_texts: List of {"filename": str, "text": str} dicts for new docs.
        profile_service: ProfileService for LLM profile lookup.
        profile_id: Optional explicit LLM profile ID.
        language: Language for analysis content (e.g. "de", "en").
        timeout: Max seconds to wait for LLM response.

    Returns:
        Updated analysis dict, or error dict.
    """
    if not new_document_texts:
        return {"error": "No new documents to analyze", "analysis": existing_analysis}

    logger.info(
        "Updating analysis with %d new document(s) (language=%s)",
        len(new_document_texts),
        language,
    )

    existing_json = json.dumps(existing_analysis, ensure_ascii=False, indent=2)

    doc_texts_str = ""
    for i, doc in enumerate(new_document_texts):
        text = doc.get("text", "")[:20000]
        doc_texts_str += f"\n--- Document {i + 1}: {doc.get('filename', 'unknown')} ---\n{text}\n"

    user_prompt = f"""Here is the existing case analysis:

{existing_json}

And here {"is" if len(new_document_texts) == 1 else "are"} the new document(s) to merge in:

{doc_texts_str}

Return the updated case analysis as valid JSON following the required structure."""

    system_prompt = _build_update_system_prompt(language)
    result = _call_llm(user_prompt, system_prompt, profile_service, profile_id, timeout)

    if "error" not in result:
        result["_updated_from"] = existing_analysis.get("_model", "unknown")
    return result


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
