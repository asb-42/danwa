# DOX: docs/

## Purpose

Project documentation: architecture decision records (ADRs), architecture guides, reviews, and standalone documentation.

## Ownership

- **ADRs**: `docs/adr/` — architecture decision records
- **Architecture**: `docs/architecture/` — 20 architecture documentation files
- **API Reference**: lives in danwa-core (`docs/api-reference.md`, `docs/api/`) — generated there from the OpenAPI spec; this repo's `docs/api/` was removed with the legacy backend (review §3.1, 2026-08-31)
- **Guides**: `docs/` root — user manual, technical docs, development guides
- **Reviews**: `docs/reviews/` — dated deep-dive code and architecture reviews

## Local Contracts

- ADRs follow the template in `docs/adr/TEMPLATE.md`
- Architecture docs cover frontend and cross-repo integration layers
- API reference generation is delegated: `./manage.sh doc-api` / `doc-pdoc` run in danwa-core

## Work Guidance

- Add ADRs for significant architectural decisions
- Keep architecture docs current with code changes
- Use consistent formatting and cross-references

## Verification

- Verify links between documents work
- Check ADR template compliance

## Child DOX Index

| Child | Purpose |
|-------|---------|
| `docs/adr/` | Architecture Decision Records |
| `docs/architecture/` | Architecture documentation (20 files) |
| `docs/reviews/` | Dated deep-dive reviews (e.g., `YYYY-MM-DD_<topic>-code-review.md`) |
