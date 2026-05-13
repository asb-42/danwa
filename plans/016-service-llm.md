# Sprint X — Service LLM & Titelgenerierung 2.0

> **Branch:** `feature/module-architecture` (oder neuer Branch `feature/service-llm`)
> **Dauer:** 1 Woche
> **Liefergegenstand:** Service-LLM-Konzept, Titelgenerierung Fix, UI-Feedback-System

---

## 1. Kontext & Problemstellung

### 1.1 Titelgenerierung — aktueller Fehler

Die Titelgenerierung in `backend/services/debate_workflow.py` → `generate_debate_title()` funktioniert zwar prinzipiell,
hat aber ein bekanntes Problem: **Viele LLMs ignorieren die System-Prompt-Anweisung** und geben statt eines Titels
eine Beschreibung zurück (z.B. "The user wants a debate about…"). Die Regex-Filter helfen, sind aber nicht robust genug.

**Ursachenanalyse:**
- Das verwendete LLM (Default: `openrouter-claude-3.6-sonnet` / aktuell `moonshotai/kimi-k2.6`) folgt den
  Instruktionen nicht zuverlässig bei diesem Profil
- Der System-Prompt ist korrekt, aber bestimmte Modelle sind bei kurzen Inputs "zu kreativ"
- Temperatur 0.3 ist noch relativ hoch für deterministische Textgenerierung

### 1.2 Service LLM — fehlendes Konzept

Aktuell wird für **jede LLM-Aufgabe** (Debattenteilnehmer, Titelgenerierung, Übersetzung) das in der
Debatte konfigurierte LLM-Profil verwendet. Es gibt **kein dediziertes "Service LLM"** für Systemfunktionen.

Probleme:
- Kostenintensive Modelle werden für triviale Aufgaben verbraucht (Titelgenerierung)
- Es gibt kein Fallback, wenn das primäre LLM für Systemaufgaben nicht geeignet ist
- Übersetzung großer Prompts mit kleinen Modellen → Qualitätsverlust

---

## 2. Architektur: Service LLM

### 2.1 Konzept

Ein **Service LLM** ist ein dediziertes LLM-Profil, das für systemnahe Aufgaben verwendet wird:
- Titelgenerierung
- Übersetzung der Prompts (EN → DE, EN → ZH etc.)
- Zusammenfassungen
- Validierung von Benutzereingaben

Es ist **nicht** dasselbe wie das "Default LLM Profile" einer Debatte (das für die Agenten ist).

### 2.2 Konfiguration

**Neues Feld in `Settings`** (`backend/core/config.py`):

```python
# --- Service LLM ---
service_llm_profile_id: str | None = None  # Falls None → erstes verfügbares text-LLM
```

**Neues Feld in LLM-Profilen** (`profiles/llm/*.yaml` und `backend/core/profiles.py`):

```yaml
# Neue Felder im YAML:
profile_type: text          # text, tts, stt — bestimmt Eignung
min_recommended_tokens: 4096  # Mindestkontext für Service-Nutzung
service_eligible: true       # Kann für Systemaufgaben verwendet werden?
```

```python
# In LLMProfile:
profile_type: Literal["text", "tts", "stt"] = "text"
# Bereits vorhanden! → Nutzen wir als Filterkriterium

# NEU:
service_eligible: bool = True
min_recommended_context: int = 4096  # Mindestkontextfenster für Service-Tasks
```

### 2.3 Eligibility-Validierung

Welche LLMs sind **nicht** als Service LLM geeignet?

| Kriterium | Bedingung | Grund |
|-----------|-----------|-------|
| `profile_type` | `!= "text"` | TTS/STT-Modelle sind keine Text-LLMs |
| `context_window` | `< 4096` | Zu kleiner Kontext für Systemprompts |
| `model` | In Blacklist | Bekannt inkompatible Modelle |
| `cost_per_1k_output` | Sehr hoch | Zu teuer für häufige Systemaufgaben |
| `provider` | Nicht erreichbar | Keine Verbindung möglich |

**Blacklist (konfigurierbar):**

```python
SERVICE_LLM_BLACKLIST = {
    "whisper-1",           # STT
    "tts-1",               # TTS
    "eleven/.*",           # Voice-Modelle
    "openai/gpt-4o-mini",  # Zu klein für Systemprompts (8K Kontext, billig aber limitiert)
}
```

**Validierungsfunktion:**

```python
def is_service_llm_eligible(profile: LLMProfile) -> tuple[bool, str]:
    """Prüft, ob ein LLM-Profil als Service-LLM geeignet ist.
    
    Returns:
        (eligible: bool, reason: str) — reason bei False erklärt die Nichteignung
    """
    if profile.profile_type != "text":
        return False, f"Nur Text-LLMs geeignet (dieses: {profile.profile_type})"
    
    if (profile.context_window or 0) < settings.service_llm_min_context:
        return False, f"Kontextfenster zu klein ({profile.context_window})"
    
    for pattern in settings.service_llm_blacklist_patterns:
        if re.match(pattern, profile.model):
            return False, f"Modell auf Blacklist ({profile.model})"
    
    return True, "Eignung bestätigt"
```

### 2.4 Fallback-Strategie

```
Service LLM Auswahl:
1. Konfiguriertes service_llm_profile_id prüfen → geeignet? → Nutzen
2. Falls nicht konfiguriert oder nicht geeignet:
   → Erstes verfügbares text-LLM mit ausreichendem Kontext
3. Falls keines gefunden:
   → Fehler mit klarem Hinweis an den Benutzer
4. Bei Titelgenerierung: Erstes LLM mit >70% Qualitätsscore
```

---

## 3. Titelgenerierung 2.0

### 3.1 Verbesserter Prompt

Der aktuelle Prompt hat Schwächen bei der Einhaltung des Formats. Verbesserung:

```python
SYSTEM_PROMPT_TITLES = {
    "en": """You are a precise debate title generator.
Rules — follow ALL of them:
1. Output ONLY the title. Nothing else. No intro, no explanation.
2. The title must be 40-120 characters.
3. Do NOT start with "Here is", "The title is", "I suggest", etc.
4. Do NOT describe the task or the user's request.
5. Do NOT use quotation marks around the title.
6. Do NOT end with punctuation.
7. Format: concise noun phrase or simple sentence.

BAD: "The user wants a title about climate change"
BAD: "Here is my suggested title: ..."
GOOD: "Climate Change and Economic Growth: Compatible or Contradictory?" """,
    "de": """Du bist ein präziser Titel-Generator für Debatten.
Regeln — befolge ALLE:
1. Gib AUSSCHLIESSLICH den Titel aus. Nichts anderes. Keine Einleitung.
2. Der Titel muss 40-120 Zeichen lang sein.
3. Beginne NICHT mit "Hier ist", "Der Titel lautet", etc.
4. Beschreibe NICHT die Aufgabe oder den Wunsch des Benutzers.
5. Keine Anführungszeichen um den Titel.
6. Kein Satzzeichen am Ende.
7. Format: kompakte Nominalphrase oder einfacher Satz.

BAD: "Der Benutzer möchte einen Titel über Klimawandel"
BAD: "Hier ist mein vorgeschlagener Titel: ..."
GOOD: "Klimawandel und Wirtschaftswachstum: Vereinbar oder Widersprüchlich?" """
}
```

**Zusätzliche Maßnahmen:**
- Temperature auf **0.1** senken (maximal deterministisch)
- `stop_sequences` definieren: `["\n\n", "---", "Titel:"]`
- Post-Processing: Mehrstufige Bereinigung (bereits vorhanden, verbessern)
- **Falls alle Versuche scheitern**: Fallback auf statisches Muster
  `"{first_sentence[:80]}…"` mit klarer Markierung im UI

### 3.2 Ergebnisvalidierung

```python
def validate_title(title: str, case_text: str) -> tuple[bool, str]:
    """Prüft, ob der generierte Titel akzeptabel ist."""
    if len(title) < 10:
        return False, "Zu kurz"
    if len(title) > 150:
        return False, "Zu lang"
    if title.lower()[:15] in case_text.lower()[:50]:
        return False, "Identisch mit Fallbeschreibung"  # Kein Titel generiert
    # Prüfe auf Meta-Text
    meta_patterns = ["the user", "the case", "this debate", "würde gerne"]
    if any(p in title.lower() for p in meta_patterns):
        return False, "Enthält Meta-Text"
    return True, "OK"
```

---

## 4. UI-Feedback für Hintergrundoperationen

### 4.1 Anforderungen

Der Benutzer muss **jederzeit** wissen:
- Wenn das System im Hintergrund arbeitet (Titel generieren, Übersetzen)
- Wenn eine Operation erfolgreich war
- Wenn eine Operation fehlgeschlagen ist
- Wie der aktuelle Fortschritt aussieht

### 4.2 Tailwind-CSS-Klassen für Status-Feedback

Tailwind bietet **Toast-Notifications** (via eigene Komponente) und **Progress Indicators**:

**Toast/Snackbar (für Erfolg/Fehler):**
```html
<!-- Erfolgs-Toast -->
<div class="fixed bottom-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg transition-opacity duration-300">
  ✅ Titel wurde generiert
</div>

<!-- Fehler-Toast -->
<div class="fixed bottom-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg transition-opacity duration-300">
  ❌ Titelgenerierung fehlgeschlagen
</div>

<!-- Ladeindikator -->
<div class="fixed bottom-4 right-4 bg-blue-500 text-white px-6 py-3 rounded-lg shadow-lg">
  <div class="flex items-center gap-2">
    <svg class="animate-spin h-4 w-4">...</svg>
    Übersetze Prompt...
  </div>
</div>
```

**Inline-Statusanzeige (DebateView Header):**

```html
<!-- Im Header der Debatte -->
<div class="flex items-center gap-2 text-sm">
  {#if titleGenerating}
    <svg class="animate-spin h-4 w-4 text-blue-500" ... />
    <span class="text-blue-600">Titel wird generiert…</span>
  {:else if titleError}
    <svg class="h-4 w-4 text-red-500" ... />
    <span class="text-red-600">Titelgenerierung fehlgeschlagen</span>
  {:else}
    <span class="text-gray-500">Bereit</span>
  {/if}
</div>
```

**Farbschema (Tailwind):**

| Status | Hintergrund | Icon | Text |
|--------|------------|------|------|
| In Bearbeitung | `bg-blue-500` | Spinner (animate-spin) | "Wird verarbeitet…" |
| Erfolg | `bg-green-500` | ✅ | "Erledigt" (2s, dann fade) |
| Fehler | `bg-red-500` | ❌ | Fehlermeldung |
| Warnung | `bg-amber-500` | ⚠️ | Warnhinweis |

### 4.3 Implementierungsplan UI

1. **Toast-Store** erstellen (`stores/toast.js`):
   ```javascript
   import { writable } from 'svelte/store';
   
   export const toasts = writable([]);
   
   export function addToast({ type, message, duration = 3000 }) {
     const id = crypto.randomUUID();
     toasts.update(all => [...all, { id, type, message, duration }]);
     setTimeout(() => removeToast(id), duration);
   }
   
   export function removeToast(id) {
     toasts.update(all => all.filter(t => t.id !== id));
   }
   ```

2. **ToastContainer.svelte** Komponente:
   - Fixed position bottom-right
   - Animierter Eintritt/Austritt
   - Auto-dismiss nach konfigurierbarer Dauer

3. **In allen API-Calls integrieren**:
   - `createDebate` → Toast "Debatte erstellt" / Fehler
   - `startDebate` → Toast "Debatte gestartet"
   - `requestTranslation` → Toast "Übersetzung läuft…" / "Übersetzung fertig"
   - `generateTitle` → Toast "Titel wird generiert…" / "Titel generiert"

4. **Inline-Statusanzeige** in `DebateView.svelte`:
   - Zeigt aktuellen Status der Hintergrundoperationen
   - Sanftes Ein-/Ausblenden (transition)
   - Klickbar → Details / Retry bei Fehler

### 4.4 Abhängigkeitsmanagement für Service LLM

**Mindestanforderung an Service LLM:**
- `profile_type` = `"text"`
- `context_window` >= 4096 (konfigurierbar)
- Keine bekannten Inkompatibilitäten
- Erreichbar (Verbindungscheck beim Setzen der Checkbox)

**Validierungsablauf beim Setzen der Checkbox:**

```
Benutzer setzt "Service LLM" Checkbox:
  1. Profil-Daten laden (API: GET /api/v1/blueprints/llm-profiles/{id})
  2. Eignung prüfen (clientseitig + serverseitig)
  3. Falls nicht geeignet: Fehlermeldung anzeigen, Checkbox zurücksetzen
  4. Falls geeignet: Speichern (API: PUT /api/v1/config/service-llm)
  5. Bestätigung: "Dieses LLM wird jetzt für Systemaufgaben verwendet"
```

---

## 5. Neue API-Endpunkte

| Methode | Endpoint | Beschreibung |
|---------|----------|-------------|
| GET | `/api/v1/config/service-llm` | Aktuelles Service-LLM-Profil |
| PUT | `/api/v1/config/service-llm` | Service-LLM setzen (body: `{profile_id}`) |
| POST | `/api/v1/config/validate-service-llm` | Validiert ein LLM-Profil (body: `{profile_id}`) |
| GET | `/api/v1/llm-profiles/service-eligible` | Liste geeigneter Service-LLMs |

---

## 6. Datenmodell-Änderungen

### backend/core/config.py
```python
# Neue Settings-Felder
service_llm_profile_id: str | None = None
service_llm_min_context: int = 4096
service_llm_blacklist_patterns: list[str] = [
    r"whisper-.*",
    r"tts-.*",
    r"eleven/.*",
]
```

### backend/core/profiles.py (LLMProfile)
```python
# Neue Felder (optional, defaults)
service_eligible: bool = True  # Wird bei Abfrage dynamisch berechnet, nicht in YAML gespeichert
```

> **Hinweis:** `service_eligible` wird **nicht** in der YAML-Datei gespeichert, sondern dynamisch
> aus den Eigenschaften des Profils berechnet. So kann ein Benutzer sein "gutes" LLM
> als Service-LLM setzen, ohne die Profil-Datei zu verändern.

---

## 7. Tests

### Backend-Tests
- [ ] `test_service_llm_eligibility()`: Eignungsprüfung für verschiedene Profil-Typen
- [ ] `test_service_llm_fallback()`: Fallback bei nicht-geeignetem konfiguriertem LLM
- [ ] `test_title_generation()`: Titelgenerierung mit verschiedenen LLMs und Qualitätsprüfung
- [ ] `test_title_validation()`: Validierung erkennt fehlerhafte Titel
- [ ] `test_service_llm_api()`: API-Endpunkte für Service-LLM-Konfiguration
- [ ] `test_config_validation()`: Validierung verhindert TTS/STT als Service LLM

### E2E-Tests
- [ ] Toast-Notifications erscheinen bei Hintergrundoperationen
- [ ] Fortschrittsanzeige in DebateView bei Titelgenerierung
- [ ] Fehleranzeige bei fehlgeschlagener Titelgenerierung
- [ ] Service-LLM Checkbox Validierung
- [ ] Übersetzungs-Feedback im UI

### Erfolgskriterien
- [ ] AC: Titelgenerierung produziert bei >90% der Fälle einen korrekten Titel (kein Meta-Text)
- [ ] AC: Service LLM Auswahl schließt TTS/STT automatisch aus
- [ ] AC: Benutzer sieht Feedback bei allen Hintergrundoperationen (≤1s Verzögerung)
- [ ] AC: Fallback funktioniert, wenn konfiguriertes Service LLM nicht geeignet ist
- [ ] AC: Toast-Notifications sind zugänglich (ARIA-Live-Region, Tastaturnavigation)

---

## 8. Abhängigkeiten

- Benötigt **keine** anderen Sprints als Voraussetzung
- Kann parallel zu Sprint 3–5 laufen
- Übersetzungsfeature (Sprint 3) nutzt das Service LLM automatisch

