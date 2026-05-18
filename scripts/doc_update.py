#!/usr/bin/env python3
"""LLM-basierte Dokumentation aktualisieren.

Ermittelt geänderte Dateien seit dem letzten Doc-Update und lässt ein LLM
die technische Dokumentation und/oder das User Manual aktualisieren.

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


def build_prompt(
    changed_files: list[str],
    tech_doc: str,
    user_manual: str,
    mode: str = "all",
) -> str:
    """Build prompt for LLM to update documentation."""
    lines = [
        "Du bist ein technischer Redakteur für das Danwa-Projekt.",
        "",
        "Folgende Dateien haben sich geändert:",
    ]

    for f in changed_files:
        lines.append(f"- {f}")

    lines.append("")

    if mode in ("tech", "all"):
        lines.append("Aktualisiere die folgende technische Dokumentation basierend auf diesen Änderungen:")
        lines.append("")
        lines.append("<technical_documentation>")
        lines.append(tech_doc[:8000])  # Limit to avoid token limits
        lines.append("</technical_documentation>")
        lines.append("")

    if mode in ("user", "all"):
        lines.append("Aktualisiere das folgende User Manual basierend auf diesen Änderungen:")
        lines.append("")
        lines.append("<user_manual>")
        lines.append(user_manual[:8000])  # Limit to avoid token limits
        lines.append("</user_manual>")
        lines.append("")

    lines.extend([
        "Regeln:",
        "- Behalte die bestehende Struktur bei",
        "- Füge neue Sections hinzu wo nötig",
        "- Markiere geänderte Stellen mit <!-- UPDATED -->",
        "- Entferne veraltete Informationen",
        "- Output: Nur die aktualisierte Markdown-Datei",
        "",
        "Output-Format (JSON):",
        "{",
        '  "tech_doc": "<aktualisierte technische Dokumentation oder leer wenn nicht geändert>",',
        '  "user_manual": "<aktualisiertes User Manual oder leer wenn nicht geändert>"',
        "}",
    ])

    return "\n".join(lines)


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


def parse_llm_response(response: str) -> dict:
    """Parse LLM response JSON."""
    # Try to extract JSON from response
    start = response.find("{")
    end = response.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = response[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Fallback: return empty dict
    return {"tech_doc": "", "user_manual": ""}


def main():
    parser = argparse.ArgumentParser(description="LLM-basierte Dokumentation aktualisieren")
    parser.add_argument("--tech", action="store_true", help="Nur technische Doku")
    parser.add_argument("--user", action="store_true", help="Nur User Manual")
    parser.add_argument("--all", action="store_true", help="Beide (default)")
    parser.add_argument("--dry-run", action="store_true", help="Vorschau ohne Änderungen")
    parser.add_argument("--profile", type=str, help="LLM-Profil ID")
    parser.add_argument("--since", type=str, default="HEAD~10", help="Git reference für Änderungen")
    args = parser.parse_args()

    # Determine mode
    if args.tech:
        mode = "tech"
    elif args.user:
        mode = "user"
    else:
        mode = "all"

    # Get changed files
    changed_files = get_changed_files(args.since)
    if not changed_files:
        print("[OK] Keine relevanten Änderungen seit letztem Doc-Update")
        return

    print(f"[INFO] {len(changed_files)} geänderte Dateien gefunden:")
    for f in changed_files:
        print(f"  - {f}")

    # Read current docs
    tech_doc = read_file_safe(TECH_DOC)
    user_manual = read_file_safe(USER_MANUAL)

    # Build prompt
    prompt = build_prompt(changed_files, tech_doc, user_manual, mode)

    if args.dry_run:
        print("\n[DRY-RUN] Prompt:")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("\n[DRY-RUN] Keine Änderungen geschrieben")
        return

    # Call LLM
    print("\n[INFO] LLM-Call gestartet...")
    response = call_llm(prompt, args.profile)

    # Parse response
    updates = parse_llm_response(response)

    # Apply updates
    if mode in ("tech", "all") and updates.get("tech_doc"):
        if args.dry_run:
            print(f"\n[DRY-RUN] Technische Doku würde aktualisiert ({len(updates['tech_doc'])} Zeichen)")
        else:
            TECH_DOC.write_text(updates["tech_doc"], encoding="utf-8")
            print(f"[OK] Technische Doku aktualisiert: {TECH_DOC}")

    if mode in ("user", "all") and updates.get("user_manual"):
        if args.dry_run:
            print(f"\n[DRY-RUN] User Manual würde aktualisiert ({len(updates['user_manual'])} Zeichen)")
        else:
            USER_MANUAL.write_text(updates["user_manual"], encoding="utf-8")
            print(f"[OK] User Manual aktualisiert: {USER_MANUAL}")

    # Update marker
    if not args.dry_run:
        LAST_UPDATE_MARKER.write_text("HEAD", encoding="utf-8")
        print(f"[OK] Update-Marker gesetzt: {LAST_UPDATE_MARKER}")


if __name__ == "__main__":
    main()
