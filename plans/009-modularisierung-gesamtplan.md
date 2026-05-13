# Gesamtplan: Danwa-Modularisierung & Einsprachiger SSOT

> **Branch:** `feature/module-architecture`  
> **Start:** 2026-05-13  
> **Geplante Dauer:** 6 Sprints (6 Wochen)  
> **Autor:** Kilo

---

## Ausgangslage & Motivation

### Problem 1: Zu viele Dateien, keine Struktur
- `profiles/` enthält 160+ Dateien in 6+ Unterverzeichnissen
- Keine einheitliche Metadatenstruktur
- Keine Versionskontrolle pro Modul
- Duplikate (DE + EN nebenläufig gepflegt)

### Problem 2: SSOT-Ambiguität
- Prompts leben nur in Dateien → kein Audit, kein Review
- LLM-Profile, Agent-Personas, Workflow-Templates mischen Dateien und DB
- Keine klare Quelle der Wahrheit

### Problem 3: Keine Erweiterbarkeit
- Neue Gesprächsformate erfordern Code-Änderungen
- Drittanbieter-Module unmöglich
- Keine klare Trennung zwischen System-Prompts und Benutzerinhalten

### Lösung: Modul-Architektur
- Jedes Modul = eigenständige Einheit mit Manifest
- Module können installiert, aktualisiert, deinstalliert werden
- EN als SSOT, Übersetzungen als DB-Cache
- Git-tracked für Entwicklung, DB für Runtime

---

## Architektur-Prinzipien

| Prinzip | Beschreibung |
|---------|-------------|
| **EN als SSOT** | Alle Quelldateien nur in Englisch |
| **DB als Runtime-SSOT** | Übersetzungen und Module in der Datenbank |
| **Dateien für Entwicklung** | Module liegen als Dateien vor (Git-diffbar) |
| **Checksummen** | Jedes Modul hat SHA-256-Prüfsummen aller Dateien |
| **Semantisches Versioning** | Module haben eigene Versionen |
| **Abwärtskompatibilität** | Alte Pfade funktionieren bis Sprint 5-Ende |
| **Sicherheit** | Keine ausführbaren Dateien in Modulen erlaubt |

---

## Sprint-Übersicht

| Sprint | Thema | Dauer | Ergebnis |
|--------|-------|-------|----------|
| 1 | EN-SSOT + Grundlagen | 1 Wo | Schema, DB-Modelle, erste Module |
| 2 | Modulformat + Import-Engine | 1 Wo | Installer, Validator, Migration |
| 3 | Übersetzungscache | 1 Wo | LLM-Übersetzung, Cache, UI |
| 4 | API + Frontend | 1 Wo | Module-Manager, Marketplace |
| 5 | Migration & Cleanup | 1 Wo | Alte Dateien entfernt |
| 6 | Modulecosystem | 1 Wo | GitHub-Repo, Export, Docs |

---

## Abhängigkeitsdiagramm

```
Sprint 1 (Grundlagen)
  ├── Manifest-Schema
  ├── DB-Modelle (module_registry, module_translation_cache)
  ├── Verzeichnisstruktur modules/
  ├── EN-Bereinigung
  └── Deploy-Import (Rohversion)
        │
        ▼
Sprint 2 (Import-Engine)
  ├── ModuleValidator
  ├── ModuleInstaller/Uninstaller
  ├── ModuleService
  ├── API-Endpoints
  └── Migration bestehender Dateien
        │
        ▼
Sprint 3 (Übersetzungscache)
  ├── TranslationService
  ├── Back-Translation-Qualitätssicherung
  ├── PromptService-Integration
  ├── Übersetzungs-API
  └── Frontend Übersetzungs-Dashboard
        │
        ▼
Sprint 4 (API + Frontend)
  ├── REST-API vervollständigen
  ├── ModuleManager.svelte
  ├── ModuleMarketplace.svelte
  └── Prompt-Editor-Integration
        │
        ▼
Sprint 5 (Migration & Cleanup)
  ├── Alle Prompts migriert
  ├── Alle Profile migriert
  ├── Abwärtskompatibilitätsschicht
  └── Legacy-Dateien entfernt
        │
        ▼
Sprint 6 (Modulecosystem)
  ├── GitHub-Repo danwa-modules
  ├── Export/Import-Mechanismus
  ├── CI/CD-Pipeline
  ├── Dokumentation
  └── Community-Module
```

---

## Risiken & Notfallpläne

| Risiko | Wahrscheinlichkeit | Auswirkung | Notfallplan |
|--------|-------------------|-----------|-------------|
| Übersetzungsqualität | Mittel | Hoch | Back-Translation-Check + manuelle Freigabe |
| Migration bricht ab | Niedrig | Hoch | Inkrementelle Migration, Rollback möglich |
| API-Keys exponiert | Niedrig | Kritisch | Keys nur in `.env`, niemals in Modul-Dateien |
| Performance-Regression | Niedrig | Mittel | Caching + Benchmarks pro Sprint |

---

## Abkürzungen

| Abkürzung | Bedeutung |
|-----------|-----------|
| SSOT | Single Source of Truth |
| DMS | Document Management System |
| HITL | Human-in-the-Loop |
| A2A | Agent-to-Agent |
| API | Application Programming Interface |
| DB | Datenbank |
| UI | User Interface |
| SDK | Software Development Kit |
| YAML | Yet Another Markup Language |
| JSON | JavaScript Object Notation |
