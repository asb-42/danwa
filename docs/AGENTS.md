# DOX: docs/

## Purpose

Project documentation: architecture decision records (ADRs), API reference, architecture guides, and standalone documentation.

## Ownership

- **ADRs**: `docs/adr/` — architecture decision records
- **Architecture**: `docs/architecture/` — 20 architecture documentation files
- **API Reference**: `docs/api-reference.md`, `docs/api/` — OpenAPI-generated docs
- **Guides**: `docs/` root — user manual, technical docs, development guides

## Local Contracts

- ADRs follow the template in `docs/adr/TEMPLATE.md`
- Architecture docs cover backend, frontend, and integration layers
- API reference is generated from OpenAPI spec

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
| `docs/api/` | Generated API reference |
