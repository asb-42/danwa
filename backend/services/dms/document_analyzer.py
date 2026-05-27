"""Document analysis — uses LLM to summarize and structure project documents."""

from __future__ import annotations

import json
import logging
import re
import time
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


def _sanitize_for_prompt(text: str) -> str:
    """Neutralize common prompt-injection patterns in user-provided document text.

    This is a defense-in-depth measure — not a complete solution. Structured
    prompt delimiters (XML tags) in the system prompt provide the primary boundary.
    """
    text = re.sub(
        r"(?i)(ignore|disregard|forget)\s+(all|previous|above|prior)\s+(instructions?|prompts?|rules?)",
        "[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)you\s+are\s+now\s+(a|an|the)",
        "[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)(system|assistant)\s*:\s*",
        "[REDACTED] ",
        text,
    )
    return text


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
    # 3. Find outermost balanced JSON object
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        c = text[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\" and in_string:
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _clean_json(text: str) -> str:
    """Strip trailing commas before ] or } so json.loads can handle them."""
    # Remove trailing commas: ,] -> ], ,} -> }
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    return cleaned


def _parse_json(text: str) -> dict | None:
    """Attempt to parse JSON with progressively more aggressive cleaning."""
    # Strategy 1: raw text
    for candidate in [text, _clean_json(text)]:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    # Strategy 2: strip control characters
    try:
        return json.loads(_clean_json(re.sub(r"[\x00-\x1f]", "", text)))
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _call_llm(
    user_prompt: str,
    system_prompt: str,
    profile_service: ProfileService,
    profile_id: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """Call the LLM and parse the JSON response. Returns parsed analysis or error dict.
    Retries once if JSON parsing fails, asking the LLM to fix the formatting.
    """
    llm_profile_id = profile_id or select_service_llm(profile_service)
    llm = LLMService(profile_id=llm_profile_id, profile_service=profile_service)

    result = _generate_with_retry(llm, user_prompt, system_prompt)
    if "error" in result:
        return result

    content = result["content"]
    extracted = _extract_json(content)
    if not extracted:
        logger.error("No JSON found in LLM response")
        return {"error": "Analysis produced unexpected output", "raw": content[:500]}

    analysis = _parse_json(extracted)
    if not analysis:
        logger.warning("Initial JSON parse failed, requesting LLM to fix formatting")
        fixed = _request_json_fix(llm, content)
        if fixed and "error" not in fixed:
            analysis = fixed
        else:
            logger.error("Failed to parse analysis JSON after retry")
            return {"error": "Analysis produced unparseable JSON", "raw": content[:500]}

    analysis["_model"] = result["model"]
    analysis["_tokens_in"] = result["tokens_in"]
    analysis["_tokens_out"] = result["tokens_out"]
    analysis["_duration_ms"] = result["duration_ms"]

    return analysis


def _generate_with_retry(
    llm: LLMService,
    user_prompt: str,
    system_prompt: str,
    timeout: int = 180,
    max_retries: int = 2,
    base_delay: float = 2.0,
) -> dict[str, Any]:
    """Call generate_sync with retry on transient failures. Returns dict with content/metadata or error."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = llm.generate_sync(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=8192,
                context="Document Analysis",
            )
            return {
                "content": result.content.strip(),
                "model": result.model,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "duration_ms": result.duration_ms,
            }
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning("LLM call attempt %d failed, retrying in %.1fs: %s", attempt + 1, delay, e)
                time.sleep(delay)
    logger.error("LLM analysis failed after %d attempts: %s", max_retries + 1, last_error)
    return {"error": f"Analysis failed after {max_retries + 1} attempts: {last_error}"}


def _request_json_fix(llm: LLMService, malformed: str) -> dict | None:
    """Ask the LLM to fix malformed JSON and return valid JSON only."""
    fix_prompt = (
        "The following text is supposed to be valid JSON but has a syntax error. "
        "Fix the JSON and return ONLY the corrected JSON object — no markdown, no explanations.\n\n" + malformed[:30000]
    )
    fix_system = "You fix JSON syntax errors. Return ONLY valid JSON, no markdown, no explanations."
    try:
        result = llm.generate_sync(
            prompt=fix_prompt,
            system_prompt=fix_system,
            temperature=0.0,
            max_tokens=8192,
            context="Document Analysis (JSON fix)",
        )
    except Exception as e:
        logger.warning("JSON fix LLM call failed: %s", e)
        return None

    fixed_content = result.content.strip()
    extracted = _extract_json(fixed_content)
    if not extracted:
        return None
    return _parse_json(extracted)


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
        text = _sanitize_for_prompt(doc.get("text", "")[:20000])
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
        text = _sanitize_for_prompt(doc.get("text", "")[:20000])
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
    """Save analysis JSON to the project directory.

    Raises:
        OSError: If the file cannot be written.
    """
    path = Path(project_dir) / "analysis.json"
    path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved analysis to %s", path)
