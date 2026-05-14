# Sprint 3 — Übersetzungscache: LLM-gestützte Mehrsprachigkeit

> **Branch:** `feature/module-architecture`  
> **Dauer:** 1 Woche  
> **Liefergegenstand:** Automatische Übersetzung, Cache-Invalidierung, UI für Übersetzungen

---

## Kontext

- EN ist SSOT (Quelldateien)
- DE muss automatisch aus EN generiert und gecacht werden
- Architektur ist offen für weitere Sprachen (ZH, …), wird aber in Sprint 3 **nicht** implementiert
- Neue Funktion "Prompt übersetzen" im UI unter **Konfiguration → Übersetzungen**

---

## Todo-Liste

### 3.1 — Übersetzungs-Service implementieren

- [ ] Klasse `TranslationService` in `backend/modules/translation.py`
  - [ ] `translate_prompt(module_id, file_path, source_lang='en', target_lang='de', llm_profile_id=None)`:
    - [ ] EN-Content auslesen (DB oder Datei)
    - [ ] Prompt an LLM senden mit klarer Anweisung: "Übersetze diesen System-Prompt ins Deutsche, beibehaltend den technischen Kontext"
    - [ ] Ergebnis in `module_translation_cache` speichern
    - [ ] Quality-Score berechnen (initial: 0.5 für LLM-generiert)
    - [ ] `generated_at`, `generated_by`, `source_hash` setzen
  - [ ] `batch_translate(module_id, target_lang)`:
    - [ ] Alle Dateien eines Moduls übersetzen
    - [ ] Fortschritt tracken
  - [ ] `invalidate_cache(module_id, file_path=None, language=None)`:
    - [ ] Cache-Einträge für geänderte Dateien entfernen
    - [ ] Wird bei Update/Re-Import automatisch aufgerufen

### 3.2 — Back-Translation-Qualitätssicherung

- [ ] Methode `verify_translation(original_en, translated_de) → float`:
  - [ ] LLM bittet DE-Text zurück ins EN zu übersetzen
  - [ ] Cosinus-Ähnlichkeit oder Token-Overlap mit Original vergleichen
  - [ ] Score > 0.8 → automatisch `approved=true` setzen
  - [ ] Score ≤ 0.8 → `approved=false`, erscheint in UI als "Manuelle Überprüfung nötig"
- [ ] API-Endpoint `POST /api/v1/modules/{id}/verify-translation`

### 3.3 — PromptService: Übersetzungs-Pipeline integrieren

- [ ] `assemble_prompt()` Logik aktualisieren:
  ```python
  def assemble_prompt(role_type_id, argumentation_pattern, tone_profile, 
                      workflow_variant, language="de"):
      # 1. Base Role Prompt (mit Übersetzungslogik)
      base = self.get_prompt_translated("default", role_type_id, language)
      
      # 2. Argumentation Pattern (mit Übersetzungslogik)
      if argumentation_pattern:
          pattern = self.get_argumentation_pattern_translated(pattern, role_type_id, language)
      
      # 3. Mode Modifier (sprachabhängig, aber Inhalt gleich)
      # 4. Tone Injection (sprachabhängig)
      # 5. Workflow Variant (mit Übersetzungslogik)
  ```
- [ ] `get_prompt_translated()` intern:
  - [ ] Prüfe `module_translation_cache` für `language`
  - [ ] Cache-Hit → zurückgeben
  - [ ] Cache-Miss → `translate_prompt()` → zurückgeben

### 3.4 — Übersetzungs-API ergänzen

- [ ] `GET /api/v1/modules/{id}/translations` → Liste aller Übersetzungen mit Status
- [ ] `POST /api/v1/modules/{id}/translate` → Übersetzung auslösen (body: `{target_lang, file_path?}`)
- [ ] `PUT /api/v1/modules/{id}/translations/{translation_id}` → Manuelle Korrektur speichern
- [ ] `POST /api/v1/modules/{id}/verify-translation` → Back-Translation prüfen
- [ ] `GET /api/v1/modules/{id}/translation-status` → Übersicht: welche Module/Dateien in welcher Sprache übersetzt

### 3.5 — Frontend: Übersetzungs-Dashboard

- [ ] Neue Seite **Konfiguration → Übersetzungen**
- [ ] Modul-Baum nach Kategorien
  - [ ] Pro Modul: Sprachstatus (EN: ✅ Original | DE: ✅/⚠️/❌)
  - [ ] Qualitätsscore anzeigen
  - [ ] Button "Übersetzen" / "Erneut übersetzen"
  - [ ] Button "Manuell bearbeiten" für freigegebene Übersetzungen
- [ ] Übersetzungs-Vergleichsansicht: Original (EN) vs. Übersetzung (DE)
- [ ] Massen-Übersetzung: Alle nicht übersetzten Dateien eines Moduls

### 3.6 — "Prompt übersetzen" Funktion im Editor

- [ ] Im Prompt- und Modul-Editor: Button "Übersetzen"
- [ ] Öffnet Modal mit Sprachauswahl (aktuell: DE)
- [ ] Zeigt Vorschau der Übersetzung an
- [ ] Speichert in Übersetzungscache (nicht als Datei!)
- [ ] Admin kann Freigabe erteilen/entziehen

### 3.7 — Alte DE-Dateien importieren

- [ ] Skript `scripts/import_de_translations.py`:
  - [ ] Liest alle `-de.md` Dateien aus `profiles/`
  - [ ] Importiert sie als initiale Übersetzungscache-Einträge
  - [ ] Setzt `approved=true` (da manuell erstellt)
  - [ ] Berechnet Source-Hash aus EN-Original
  - [ ] Setzt `quality_score=1.0` für manuell erstellte Übersetzungen
- [ ] Danach können die DE-Dateien aus `profiles/` gelöscht werden (optional, empfohlen für Sprint 5)

### 3.8 — Tests

- [ ] `tests/backend/test_translation_service.py`:
  - [ ] Einzelprompt-Übersetzung
  - [ ] Batch-Übersetzung
  - [ ] Cache-Invalidierung bei Modul-Update
  - [ ] Back-Translation-Bewertung
  - [ ] Manuelle Korrektur speichern
- [ ] E2E-Test: "Benutzer übersetzt Prompt von EN nach DE"
- [ ] Regressionstest: Alte DE-Dateien werden korrekt importiert
- [ ] Performance-Test: Übersetzungscache vs. Dateisystem (Zeitmessung)

---

## Abhängigkeiten
- Benötigt Sprint 1 (DB-Tabellen) und Sprint 2 (Modulstruktur)
- Benötigt funktionierenden LLM-Zugang für Übersetzungen

## Akzeptanzkriterien
- [ ] AC-3.1: EN-Prompt wird automatisch ins DE übersetzt und gecacht
- [ ] AC-3.2: Cache wird invalidiert bei Modul-Update
- [ ] AC-3.3: Back-Translation-Bewertung funktioniert
- [ ] AC-3.4: UI zeigt Übersetzungsstatus pro Modul
- [ ] AC-3.5: "Prompt übersetzen"-Button funktioniert
- [ ] AC-3.6: Manuelle Korrektur + Freigabe funktioniert
- [ ] AC-3.7: Alte DE-Dateien als initiale Cache-Einträge importiert
