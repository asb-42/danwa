#!/usr/bin/env python3
"""LLM-basierte Dokumentation aktualisieren.

Ermittelt geänderte Dateien seit dem letzten Doc-Update und lässt ein LLM
die technische Dokumentation und/oder das User Manual aktualisieren.
Änderungen werden chirurgisch (per Section) eingespielt — nie wird die
gesamte Datei ersetzt.

Usage:
    python scripts/doc_update.py --tech            # Nur technische Doku
    python scripts/doc_update.py --user            # Nur User Manual
    python scripts/doc_update.py --all             # Beide (default)
    python scripts/doc_update.py --dry-run         # Vorschau ohne Änderungen
    python scripts/doc_update.py --profile <id>    # Spezifisches LLM-Profil
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DOCS_DIR = PROJECT_ROOT / "docs"
TECH_DOC = DOCS_DIR / "technical_documentation.md"
USER_MANUAL = DOCS_DIR / "user_manual.md"
LAST_UPDATE_MARKER = DOCS_DIR / ".last-doc-update"


def get_changed_files(since: str = "HEAD~10") -> list[str]:
    """Get list of changed files since a git reference."""
    try:
        result = subprocess.run(
            ["git", "diff", since, "--name-only", "--", "*.py", "*.svelte", "*.js", "*.ts"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []
    except Exception:
        return []


def read_file_safe(path: Path) -> str:
    """Read file content, return empty string if not found."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def parse_sections(text: str) -> list[dict]:
    """Parse a markdown doc into sections by ## headings.
    Returns list of {heading, content, heading_line, end_line}."""
    sections = []
    lines = text.split("\n")
    current_heading = None
    current_start = None
    heading_line = 0

    for i, line in enumerate(lines):
        m = re.match(r"^(##\s+.+)$", line)
        if m:
            if current_heading is not None:
                sections.append(
                    {
                        "heading": current_heading,
                        "heading_line": heading_line,
                        "content": "\n".join(lines[current_start:i]),
                        "start": current_start,
                        "end": i,
                    }
                )
            current_heading = m.group(1)
            current_start = i
            heading_line = i
        elif i == len(lines) - 1 and current_heading is not None:
            # Last section until EOF
            sections.append(
                {
                    "heading": current_heading,
                    "heading_line": heading_line,
                    "content": "\n".join(lines[current_start : i + 1]),
                    "start": current_start,
                    "end": i + 1,
                }
            )

    return sections


def build_prompt_surgical(
    changed_files: list[str],
    tech_sections: list[dict],
    user_sections: list[dict],
    mode: str = "all",
    max_section_chars: int = 400,
) -> str:
    """Build prompt for surgical section updates (no full-file replacement)."""
    lines = [
        "Du bist ein technischer Redakteur für das Danwa-Projekt.",
        "",
        "Es haben sich folgende Dateien geändert (seit letztem Doc-Update):",
    ]
    for f in changed_files:
        lines.append(f"- {f}")
    lines.append("")

    if mode in ("tech", "all"):
        lines.append("--- TECHNISCHE DOKUMENTATION ---")
        lines.append("Vorhandene Sections (Überschrift + Kurzfassung):")
        lines.append("")
        for i, sec in enumerate(tech_sections):
            snippet = sec["content"][:max_section_chars].replace("\n", "\\n")
            lines.append(f"[{i}] {sec['heading']}: {snippet}")
        lines.append("")

    if mode in ("user", "all"):
        lines.append("--- USER MANUAL ---")
        lines.append("Vorhandene Sections (Überschrift + Kurzfassung):")
        lines.append("")
        for i, sec in enumerate(user_sections):
            snippet = sec["content"][:max_section_chars].replace("\n", "\\n")
            lines.append(f"[{i}] {sec['heading']}: {snippet}")
        lines.append("")

    lines.extend(
        [
            "--- AUFGABE ---",
            "Analysiere ob eine der vorhandenen Sections aktualisiert werden muss,",
            "oder ob neue Sections hinzugefügt werden sollten (basierend auf den",
            "geänderten Dateien oben).",
            "",
            "Output-Format (JSON, NUR dieses JSON, keine Einleitung/Erklärung):",
            "{",
            '  "tech_doc_updates": [',
            "    {",
            '      "section_index": 3,',
            '      "new_content": "<VOLLSTÄNDIGER neuer Inhalt dieser Section (inkl. Heading)>"',
            "    }",
            "  ],",
            '  "tech_doc_insertions": [',
            "    {",
            '      "insert_after_heading": "## 5. Backend Architecture",',
            '      "new_content": "<VOLLSTÄNDIGER Inhalt der neuen Section (inkl. ## Heading)>"',
            "    }",
            "  ],",
            '  "user_manual_updates": [...],',
            '  "user_manual_insertions": [...]',
            "}",
            "",
            "Regeln:",
            "- WENN eine Section unverändert bleiben kann: NICHT zurückgeben.",
            "- 'new_content' ist der VOLLSTÄNDIGE Inhalt der aktualisierten/neuen Section (inkl. ## Heading).",
            "- Füge <!-- UPDATED --> direkt nach dem Section-Heading ein bei geänderten Sections.",
            "- 'section_index' bezieht sich auf die Nummer in [Klammern] oben.",
            '- Wenn Insertion: "insert_after_heading" ist die EXAKTE Überschrift (inkl. "## ") nach der eingefügt werden soll.',
            '- Bei neuem Section am Ende: insert_after_heading == "<EOF>"',
            "- Felder für nicht angeforderte Dokumente weglassen oder leeres Array.",
        ]
    )

    return "\n".join(lines)


def apply_surgical_update(original: str, updates: list[dict], insertions: list[dict]) -> str:
    """Apply surgical section updates to original markdown text.

    updates: list of {section_index, new_content}
    insertions: list of {insert_after_heading, new_content}
    """
    sections = parse_sections(original)
    lines = original.split("\n")

    # Apply updates from bottom to top so line numbers stay valid
    updates_sorted = sorted(updates, key=lambda u: u["section_index"], reverse=True)

    for up in updates_sorted:
        idx = up["section_index"]
        if idx < 0 or idx >= len(sections):
            print(f"  [WARN] Section index {idx} out of range (max {len(sections) - 1}), skipping")
            continue
        sec = sections[idx]
        new_lines = up["new_content"].split("\n")
        lines[sec["start"] : sec["end"]] = new_lines
        # Re-parse because lines changed
        sections = parse_sections("\n".join(lines))

    # Apply insertions (rebuild line list after updates)
    result = "\n".join(lines)
    lines = result.split("\n")

    for ins in insertions:
        after_h = ins["insert_after_heading"]
        new_lines = ins["new_content"].split("\n")
        if after_h == "<EOF>":
            lines.extend([""] + new_lines)
        else:
            # Find heading line
            found = -1
            for i, line in enumerate(lines):
                if line.strip() == after_h.strip():
                    found = i
                    break
            if found < 0:
                print(f"  [WARN] Heading '{after_h}' not found for insertion, skipping")
                continue
            # Find end of that section (next heading or EOF)
            insert_at = found + 1
            for i in range(found + 1, len(lines)):
                if re.match(r"^##\s+", lines[i]):
                    insert_at = i
                    break
                insert_at = i + 1
            # Insert after the section content
            lines[insert_at:insert_at] = [""] + new_lines

    return "\n".join(lines)


def parse_llm_surgical_response(response: str) -> dict:
    """Parse LLM response into surgical update directives."""
    start = response.find("{")
    end = response.rfind("}") + 1
    result = {}
    if start >= 0 and end > start:
        json_str = response[start:end]
        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError:
            print(f"  [WARN] JSON parse error, raw snippet: {json_str[:200]}")
            return result
    print(f"  [WARN] No JSON found in response, raw snippet: {response[:200]}")
    return result


def call_llm(prompt: str, profile_id: str | None = None) -> str:
    """Call LLM service to generate documentation updates."""
    try:
        from backend.services.llm_service import LLMService

        service = LLMService(profile_id=profile_id)
        if not service.profile:
            print("[ERROR] Kein LLM-Profil konfiguriert. Bitte erstelle ein LLM-Profil im Dashboard.", file=sys.stderr)
            sys.exit(1)

        import asyncio

        async def _generate():
            return await service.generate(
                prompt=prompt,
                system_prompt="Du bist ein technischer Redakteur. Antworte NUR mit validem JSON.",
                temperature=0.3,
                max_tokens=16000,
            )

        result = asyncio.run(_generate())
        return result.content
    except ImportError:
        print("[ERROR] Backend-Module nicht verfügbar.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] LLM-Call fehlgeschlagen: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="LLM-basierte Dokumentation aktualisieren")
    parser.add_argument("--tech", action="store_true", help="Nur technische Doku")
    parser.add_argument("--user", action="store_true", help="Nur User Manual")
    parser.add_argument("--all", action="store_true", help="Beide (default)")
    parser.add_argument("--dry-run", action="store_true", help="Vorschau ohne Änderungen")
    parser.add_argument("--profile", type=str, help="LLM-Profil ID")
    parser.add_argument("--since", type=str, default="HEAD~10", help="Git reference für Änderungen")
    args = parser.parse_args()

    if args.tech:
        mode = "tech"
    elif args.user:
        mode = "user"
    else:
        mode = "all"

    changed_files = get_changed_files(args.since)
    if not changed_files:
        print("[OK] Keine relevanten Änderungen seit letztem Doc-Update")
        return

    print(f"[INFO] {len(changed_files)} geänderte Dateien gefunden:")
    for f in changed_files:
        print(f"  - {f}")

    tech_doc = read_file_safe(TECH_DOC)
    user_manual = read_file_safe(USER_MANUAL)

    tech_sections = parse_sections(tech_doc)
    user_sections = parse_sections(user_manual)

    prompt = build_prompt_surgical(changed_files, tech_sections, user_sections, mode)

    if args.dry_run:
        print("\n[DRY-RUN] Prompt:")
        print(prompt[:1000] + "\n..." if len(prompt) > 1000 else prompt)
        print("\n[DRY-RUN] Keine Änderungen geschrieben")
        return

    print("\n[INFO] LLM-Call gestartet...")
    response = call_llm(prompt, args.profile)

    updates = parse_llm_surgical_response(response)

    # Apply surgical updates
    any_change = False

    if mode in ("tech", "all"):
        tech_updates = updates.get("tech_doc_updates", [])
        tech_insertions = updates.get("tech_doc_insertions", [])
        if tech_updates or tech_insertions:
            new_tech = apply_surgical_update(tech_doc, tech_updates, tech_insertions)
            TECH_DOC.write_text(new_tech, encoding="utf-8")
            print(f"[OK] Technische Doku aktualisiert ({len(tech_updates)} updates, {len(tech_insertions)} insertions)")
            any_change = True

    if mode in ("user", "all"):
        user_updates = updates.get("user_manual_updates", [])
        user_insertions = updates.get("user_manual_insertions", [])
        if user_updates or user_insertions:
            new_user = apply_surgical_update(user_manual, user_updates, user_insertions)
            USER_MANUAL.write_text(new_user, encoding="utf-8")
            print(f"[OK] User Manual aktualisiert ({len(user_updates)} updates, {len(user_insertions)} insertions)")
            any_change = True

    if not any_change:
        print("[OK] Keine Änderungen nötig — alle Sections sind aktuell")

    if not args.dry_run and any_change:
        LAST_UPDATE_MARKER.write_text("HEAD", encoding="utf-8")
        print(f"[OK] Update-Marker gesetzt: {LAST_UPDATE_MARKER}")


if __name__ == "__main__":
    main()
