# Redesign: Module System — 1 Modul = 1 Profil

## Problem
Aktuell sind Module "Bundles" die Dutzende Profile enthalten (z.B. `llm-profiles` = 21 YAML-Dateien). Das macht einzelne Profile nicht installierbar, editierbar oder duplizierbar.

## Ziel
- **1 Modul = genau 1 Profil** (1 LLM-Config, 1 Agent-Persona, 1 Role-Type, etc.)
- Module gruppiert nach Kategorie in der UI
- Jedes Profil einzeln ansehbar, editierbar (strukturiertes Formular), duplizierbar
- Install/Uninstall bezieht sich immer auf ein einzelnes Profil

---

## 1. Neue Modul-Struktur

### Verzeichnis-Layout
```
modules/
  llm-openrouter-claude/
    manifest.json          # module_id: "llm-openrouter-claude"
    profile.yaml           # Das LLM-Profil YAML
  llm-local-qwen36/
    manifest.json
    profile.yaml
  role-strategist/
    manifest.json          # module_id: "role-strategist"
    profile.json           # Role-Type JSON
  tone-heated/
    manifest.json
    profile.json
  agent-strategist-default/
    manifest.json
    profile.yaml           # Agent-Persona YAML
  workflow-standard-debate/
    manifest.json
    workflow.json          # Workflow-Template
```

### Manifest-Schema (angepasst)
```json
{
  "schema_version": "2.0.0",
  "module_id": "llm-openrouter-claude",
  "name": {"en": "Claude 3.6 Sonnet (OpenRouter)"},
  "version": "1.0.0",
  "type": "llm-profile",
  "category": "llm-profiles",
  "author": {"name": "Danwa Community"},
  "license": "CC-BY-4.0",
  "profile_file": "profile.yaml",
  "profile_format": "yaml",
  "tags": ["cloud", "openrouter", "anthropic"],
  "language": "en"
}
```

**Änderungen am Manifest:**
- `files` → `profile_file` (einzelne Datei statt Liste)
- `profile_format`: `"yaml"` | `"json"`
- `schema_version`: `"2.0.0"`

---

## 2. Backend-Änderungen

### 2.1 Module Service (`backend/modules/service.py`)
- `discover_local()`: Liest `profile_file` statt `files[]`
- `_dir_to_info()`: Lädt Profil-Datei, parst sie, extrahiert Metadaten
- Installation/Deinstallation: Kopiert/löscht einzelne Profil-Datei + Manifest

### 2.1 Module Models (`backend/modules/models.py`)
- `ModuleManifest`: Neues Feld `profile_file: str`, `profile_format: str`
- `ModuleFile` wird optional (nur für `profile_file`)

### 2.2 Neue Endpoints für Profil-Bearbeitung
```
GET    /api/v1/modules/                          → Alle Module (gruppiert nach category)
GET    /api/v1/modules/{module_id}/profile       → Profil-Inhalt (YAML/JSON geparst)
PUT    /api/v1/modules/{module_id}/profile       → Profil aktualisieren (validiert + speichert)
POST   /api/v1/modules/{module_id}/duplicate     → Profil duplizieren (neues Modul erstellen)
POST   /api/v1/modules/install                   → Modul installieren (wie bisher)
POST   /api/v1/modules/{module_id}/uninstall     → Modul deinstallieren (wie bisher)
```

### 2.3 Profil-Validierung
- LLM-Profile: Validiere gegen `LLMProfile` Pydantic-Modell
- Agent-Personas: Validiere gegen `AgentPersona` Pydantic-Modell
- Role-Types: Validiere gegen neues `RoleType` Modell
- Tone-Profile: Validiere gegen neues `ToneProfile` Modell

---

## 3. Frontend-Redesign (`ModuleManager.svelte`)

### 3.1 Layout
```
┌─────────────────────────────────────────────────┐
│  Module Management                    [Refresh] │
├─────────────────────────────────────────────────┤
│ Tabs: All | Installed (15) | Available (7)      │
├─────────────────────────────────────────────────┤
│                                                 │
│  ▼ LLM Profiles (10)                            │
│  ┌───────────────────────────────────────────┐  │
│  │ Name                  │ Provider  │ Tags  │  │
│  ├───────────────────────────────────────────┤  │
│  │ Claude 3.6 Sonnet     │ openrouter│ cloud │  │
│  │ qwen3.6-35b (LM Studio)│ local    │ local │  │
│  │ ...                                       │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ▼ Agent Personas (8)                           │
│  ┌───────────────────────────────────────────┐  │
│  │ Name              │ Role       │ LLM      │  │
│  ├───────────────────────────────────────────┤  │
│  │ Default Strategist│ strategist │ claude   │  │
│  │ ...                                       │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ▼ Role Types (10)                              │
│  ▼ Tone Profiles (3)                            │
│  ▼ Workflow Templates (7)                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 3.2 Aktionen pro Profil (Zeile)
- **👁 View** → Accordion aufklappen, Profil-Inhalt anzeigen
- **✏️ Edit** → Strukturiertes Formular-Modal öffnen
- **📋 Duplicate** → Kopie erstellen (neuer module_id)
- **📦 Install/Uninstall** (im Available/Installed Tab)

### 3.3 Edit-Modal: LLM Profile
```
┌──────────────────────────────────────────┐
│  Edit LLM Profile              [Save] [X]│
├──────────────────────────────────────────┤
│  Name: [Claude 3.6 Sonnet (OpenRouter)]  │
│  Provider: [openrouter ▼]                │
│  Model: [anthropic/claude-3.6-sonnet]    │
│  API Base: [https://openrouter.ai/...]   │
│  API Key Env: [OPENROUTER_API_KEY]       │
│  Max Tokens: [4096]                      │
│  Context Window: [200000]                │
│  Temperature: [0.7]                      │
│  Timeout: [600]                          │
│  Cost/1k Input: [$0.003]                 │
│  Cost/1k Output: [$0.015]                │
│  Protocol: [litellm ▼]                   │
│  Service Eligible: [✓]                   │
└──────────────────────────────────────────┘
```

### 3.4 Edit-Modal: Role Type
```
┌──────────────────────────────────────────┐
│  Edit Role Type                [Save] [X]│
├──────────────────────────────────────────┤
│  ID: [strategist] (readonly)             │
│  Name: [Strategist]                      │
│  Description: [Develops logical arg...]  │
│  Icon: [♟️]                               │
│  Color: [#8b5cf6]                        │
│  Max Rounds: [5]                         │
│  Consensus Threshold: [0.9]              │
│  Category: [functional ▼]                │
│  Active: [✓]                             │
└──────────────────────────────────────────┘
```

### 3.5 Edit-Modal: Tone Profile
```
┌──────────────────────────────────────────┐
│  Edit Tone Profile             [Save] [X]│
├──────────────────────────────────────────┤
│  ID: [system-heated] (readonly)          │
│  Name: [Heated Debate]                   │
│  Description: [A confrontational...]     │
│  Style: [heated ▼]                       │
│  Formality: [0.3] ━━━━━━━━○              │
│  Verbosity: [verbose ▼]                  │
│  Emotional Valence: [0.9] ━━━━━━━━○      │
│  Rhetorical Mode: [assertive ▼]          │
│  Custom Instructions: [(textarea)]       │
└──────────────────────────────────────────┘
```

### 3.6 Edit-Modal: Agent Persona
```
┌──────────────────────────────────────────┐
│  Edit Agent Persona            [Save] [X]│
├──────────────────────────────────────────┤
│  ID: [strategist-default] (readonly)     │
│  Name: [Default Strategist]              │
│  Role Type: [strategist ▼]               │
│  LLM Profile: [openrouter-claude-3.6 ▼]  │
│  Max Rounds: [5]                         │
│  Consensus Threshold: [0.9]              │
│  Description: [Default strategist...]    │
│  Tags: [default, balanced]               │
│                                          │
│  System Prompt:                          │
│  ┌────────────────────────────────────┐  │
│  │ You are the Strategist agent...    │  │
│  │                                    │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

---

## 4. Migration

### 4.1 Bestehende Bundle-Module auflösen
Jedes Bundle-Modul wird in einzelne Profil-Module zerlegt:

**Vorher:**
```
modules/llm-profiles/
  manifest.json          # module_id: "llm-profiles", 21 files
  llm/cloud-openrouter.yaml
  llm/local-qwen.yaml
  ... (19 more)
```

**Nachher:**
```
modules/llm-openrouter-claude/
  manifest.json          # module_id: "llm-openrouter-claude"
  profile.yaml
modules/llm-local-qwen/
  manifest.json          # module_id: "llm-local-qwen"
  profile.yaml
... (21 separate modules)
```

### 4.2 Migration-Skript
- Liest bestehende Bundle-Module
- Erstellt für jede Datei ein neues Modul-Verzeichnis
- Generiert neues Manifest pro Datei
- Löscht alte Bundle-Verzeichnisse
- Aktualisiert DB-Einträge

### 4.3 Alte DB-Einträge bereinigen
- `danwa-*` Einträge entfernen
- `danma-*` Typos entfernen
- Nur neue einzelne Profil-Module behalten

---

## 5. Ausführungsreihenfolge

1. **Backend Models** anpassen (schema_version 2.0, profile_file Feld)
2. **Backend Service** anpassen (discover, install, profile CRUD)
3. **Backend Router** anpassen (neue Endpoints)
4. **Migration-Skript** schreiben + ausführen
5. **Frontend ModuleManager** komplett neu bauen
6. **Edit-Modals** für jeden Profil-Typ
7. **Cleanup**: Alte Bundle-Einträge aus DB entfernen
8. **Testing**: Install/Uninstall/Edit/Duplicate pro Typ
