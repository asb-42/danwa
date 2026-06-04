"""Domain-specific prompt augmentations for transactional drafting.

The Critic's "decision matrix" used to be hardcoded for German rental law
(BGB §§ 551, 557b, 278 with Kaution / Mieter examples).  That biased the
Critic to apply rental-law severity levels even when the topic was, say,
tax law, employment law, or a software licensing agreement.

This module exposes a registry of domain matrices keyed by blueprint tags.
The Critic looks up the matrix by inspecting the agent blueprint's tags;
if no domain matches, a generic legal-quality matrix is used instead of
the rental-law one.

Adding a new domain
-------------------
1.  Create a new constant ``_MATRIX_<DOMAIN>`` containing the matrix text.
2.  Add the canonical tag (lowercased) to ``_DOMAIN_TAGS`` below.
3.  Document the new domain in the user-facing ``docs/blueprint_workflow_audit.md``.

Backwards compatibility
-----------------------
The default domain is ``"rental_law"`` (legacy) so existing runs that rely
on the rental-law matrix keep working.  Agents can opt out by removing the
``mietrecht`` / ``rental_law`` tag from their blueprint — they will then
fall back to ``_GENERIC_MATRIX`` which is domain-agnostic.
"""

from __future__ import annotations

_RENTAL_LAW_TAGS = frozenset({"mietrecht", "rental", "rental_law", "mietvertrag"})

_GENERIC_MATRIX = """\
Du MUSST jeden Mangel nach dieser Tabelle klassifizieren.
Es gibt keine Option dazwischen.

| Severity   | Bedingung (mindestens eine muss zutreffen) |
| ---------- | ------------------------------------------ |
| blocking   | Rechtliche Nichtigkeit, Prozessverlust oder Vertragsanfechtung. Oder: Verstoß gegen zwingende gesetzliche Vorschrift, der die Klausel unwirksam macht. |
| critical   | Schwerer rechtlicher Mangel, der die Wirksamkeit nicht aufhebt, aber ein wesentliches wirtschaftliches oder prozessuales Risiko erzeugt. Oder: Beweislast ungünstig verteilt. |
| warning    | Unschärfe, die im Streitfall unterschiedlich ausgelegt werden könnte, aber keine Rechtsverletzung. Oder: Praktische Probleme. |
| cosmetic   | Stil, Formatierung, Typos. Keine rechtliche oder wirtschaftliche Relevanz. |

REGELN:
- Wenn eine zwingende gesetzliche Vorschrift verletzt wird: IMMER blocking.
- warning und cosmetic sind nur für Fälle, die vor Gericht diskutabel, aber
  nicht zwingend nachteilig sind.
- Du darfst NICHT alles als warning klassifizieren, um Konflikte zu vermeiden.
  Das ist ein Fehler.
- Wähle die für die konkret kritisierte Domäne (Arbeitsrecht, Steuerrecht,
  Mietrecht, Vertragsrecht, IT-Recht, etc.) passenden Maßstäbe.  Die obigen
  Kriterien sind domänen-agnostisch formuliert.
"""

_RENTAL_LAW_MATRIX = """\
Du MUSST jeden Mangel nach dieser Tabelle klassifizieren.
Es gibt keine Option dazwischen.

| Severity | Bedingung (mindestens eine muss zutreffen) | Beispiel |
| --- | --- | --- |
| **blocking** | Rechtswidrigkeit (Gesetz, Verordnung, höchstrichterliche Entscheidung). Oder: Prozessverlust ist wahrscheinlich. Oder: Vertrag ist nichtig oder anfechtbar. | Kaution >3 Monate (§ 551 BGB). Haftung für höhere Gewalt. Kündigungsfrist 1 Monat bei Gewerbemiete. |
| **critical** | Schwerer rechtlicher Mangel, aber Vertrag bleibt wirksam. Oder: Wesentliche wirtschaftliche Risiken für Mandanten. Oder: Beweislast ungünstig verteilt. | Schönheitsreparaturen ohne Zeitbegrenzung. Unbegrenzte Indexmiete. |
| **warning** | Unschärfe, die im Streitfall unterschiedlich ausgelegt werden könnte. Oder: Praktische Probleme, aber keine Rechtsverletzung. | 'Gebrauchsspuren' nicht definiert. Kaution in bar statt Überweisung. |
| **cosmetic** | Stil, Formatierung, Typos. Keine rechtliche Relevanz. | Doppeltes Leerzeichen. 'Mietvertrag' statt 'Mietverhältnis'. |

REGELN:
- Wenn ein Gesetzsparagraf verletzt wird: IMMER blocking.
- Wenn eine Klausel im Standard-Mietvertragsrecht (BGH-Rechtsprechung) als
  unzulässig gilt: IMMER critical oder blocking.
- warning und cosmetic sind für Fälle, die vor Gericht diskutiert werden
  könnten, aber nicht zwingend verlieren.
- Du darfst NICHT alles als warning klassifizieren, um Konflikte zu vermeiden.
  Das ist ein Fehler.

BEISPIELE:

Beispiel 1 (blocking — Gesetzesverstoss):
```json
{
  "critic_id": "c-001",
  "severity": "blocking",
  "target": "§3 Kaution",
  "flaw": "Kaution beträgt 5 Monatsmieten, § 551 Abs. 1 S. 1 BGB begrenzt auf 3 Monatsmieten. Verstoss führt zur Unwirksamkeit der Kautionsabrede.",
  "principle": "§ 551 Abs. 1 S. 1 BGB",
  "context_quote": "Die Kaution beträgt fünf Monatsmieten"
}
```

Beispiel 2 (blocking — Haftung bei höherer Gewalt):
```json
{
  "critic_id": "c-002",
  "severity": "blocking",
  "target": "§5 Haftung",
  "flaw": "Mieter haftet für Schäden bei höherer Gewalt. § 278 BGB schliesst höhere Gewalt von der Schuldnerhaftung aus. Klausel ist nichtig.",
  "principle": "§ 278 BGB, höhere Gewalt",
  "context_quote": "Mieter haftet für alle Schäden, auch bei höherer Gewalt"
}
```

Beispiel 3 (critical — wirtschaftliches Risiko):
```json
{
  "critic_id": "c-003",
  "severity": "critical",
  "target": "§4 Mieterhöhung",
  "flaw": "Indexmiete ohne Obergrenze. Zulässig nach § 557b BGB, aber wirtschaftliches Existenzrisiko für Mieter bei starker Inflation.",
  "principle": "§ 557b BGB, wirtschaftliche Zumutbarkeit",
  "context_quote": "Indexmiete nach VPI, aber keine Obergrenze"
}
```
"""

_DOMAIN_MATRICES: dict[str, str] = {
    "rental_law": _RENTAL_LAW_MATRIX,
}


def _normalize_tags(tags: list[str] | tuple[str, ...] | None) -> set[str]:
    """Lowercase + dedupe a tag list; return empty set if input is None/empty."""
    if not tags:
        return set()
    return {str(t).strip().lower() for t in tags if t}


def get_decision_matrix(agent_tags: list[str] | tuple[str, ...] | None) -> str:
    """Return the decision-matrix text for the given agent blueprint tags.

    Domain resolution order:
      1.  ``mietrecht`` / ``rental_law`` / ``rental`` / ``mietvertrag`` → rental-law matrix.
      2.  Any future domain tag registered in ``_DOMAIN_MATRICES`` (case-insensitive
          prefix match is not supported — exact match only).
      3.  Fallback: ``_GENERIC_MATRIX`` (domain-agnostic legal-quality rubric).

    The function is total: it always returns a non-empty string, so callers
    do not need to handle ``None``.
    """
    tags = _normalize_tags(agent_tags)

    if tags & _RENTAL_LAW_TAGS:
        return _DOMAIN_MATRICES["rental_law"]

    for tag in tags:
        if tag in _DOMAIN_MATRICES:
            return _DOMAIN_MATRICES[tag]

    return _GENERIC_MATRIX


def is_rental_law(agent_tags: list[str] | tuple[str, ...] | None) -> bool:
    """Test helper: True iff the agent tags select the rental-law matrix."""
    tags = _normalize_tags(agent_tags)
    return bool(tags & _RENTAL_LAW_TAGS)
