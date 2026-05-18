# ADR-043: Open Source Documentation Automation

**Status:** Accepted
**Date:** 2026-05-18
**Context:** Die manuelle Pflege von `docs/technical_documentation.md` und `docs/user_manual.md` ist zeitaufwendig und fehleranfällig. Docs veralten schnell, besonders bei häufigen Code-Änderungen.

**Decision:** Dokumentation wird automatisiert durch eine Kombination von Open-Source-Tools:

1. **OpenAPI Export** — FastAPI OpenAPI-Spec wird automatisch zu Markdown konvertiert (`docs/api-reference.md`)
2. **pdoc** — Python Docstrings werden zu HTML-Dokumentation generiert (`docs/api/`)
3. **GitNexus Wiki** — Bestehender Knowledge Graph wird für Architekturdoku genutzt (`docs/architecture/`)
4. **LLM-basierte Doc-Updates** — `manage.sh doc-update` erkennt Code-Änderungen und schlägt Doc-Updates vor
5. **ADR-Workflow** — Template + Check für Architecture Decision Records

Alle Tools sind Open Source, laufen lokal, und erzeugen keine SaaS-Abhängigkeiten.

**Consequences:**
- **Positiv:** Docs bleiben aktuell, weniger manueller Aufwand, keine SaaS-Kosten
- **Negativ:** LLM-Updates erfordern manuelle Bestätigung, pdoc benötigt Docstrings in allen Modulen
- **Neutral:** Docs werden im Repo versioniert, erhöhen Repo-Größe

**Affected Files:**
- `manage.sh` — Neue Commands: `doc`, `doc-api`, `doc-pdoc`, `doc-architecture`, `doc-update`, `doc-all`, `adr-new`, `adr-check`
- `scripts/export_openapi.py` — OpenAPI Export Script
- `docs/api-reference.md` — Generierte API-Referenz
- `docs/api/` — Generierte pdoc HTML-Dokumentation
- `docs/architecture/` — Generierte GitNexus Wiki-Dokumentation
- `docs/adr/` — Architecture Decision Records

**Alternatives Considered:**
- **Swimm.io** — Code-Coupled Documentation, aber Pivot zu Enterprise, $16/User/Monat, SaaS-Abhängigkeit
- **Mintlify** — Schöne Docs, aber SaaS-Abhängigkeit, sensible Daten an externe Server
- **Docusaurus** — Gut für statische Docs, aber keine automatische Code-Integration
- **Sphinx** — Python-fokussiert, aber weniger geeignet für Multi-Language-Projekte
