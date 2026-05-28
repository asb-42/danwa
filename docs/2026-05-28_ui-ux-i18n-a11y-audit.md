# UI/UX, i18n & Accessibility Audit — 2026-05-28

**Scope:** Full frontend (`frontend/src/`)  
**Method:** Automated search + manual review of all `.svelte` and `.js` files

---

## 1. i18n-System

**Architektur:** 3-Stufen-Fallback (bundled → HTTP-Backend → Key selbst). 14 Locale-Loader. Standard-Locale: `de`.

### 1.1 Fehlende i18n-Keys (Critical)

| Datei | Abdeckung | Anzahl harcoded Strings |
|-------|-----------|------------------------|
| `LoginView.svelte` | **0%** → **100% (behoben)** | 16 Strings |
| `MvpDebateView.svelte` | **~10%** | **~80+ Strings** (nicht behoben — zu umfangreich) |
| `DocumentsView.svelte` | **~60%** | ~30 Strings (4 Deutsche behoben, Rest Englisch) |
| `Header.svelte` | **~95%** | 2 Strings (1 hardcoded Deutsch) |
| `auth.js` | N/A | 3 Fehlermeldungen |
| `api.js` | N/A | 1 Fehlermeldung (behoben) |

### 1.2 Unübersetzte Keys in de.js (High)

- **29 `modules.*`-Keys** — komplett Englisch in de.js
- `manage.title` — `'Manage'` statt `'Verwalten'`
- 3 Toast-Messages — Englisch in de.js
- `workflow.a2aInvoking/a2aCompleted` — Englisch
- `blueprint.canvas.saveAs` — Englisch

### 1.3 Durchgeführte Fixes

| Fix | Dateien |
|-----|---------|
| LoginView i18n (16 Keys) | `en.js`, `de.js`, `LoginView.svelte` |
| Upload-Status i18n (4 Keys) | `en.js`, `de.js`, `DocumentsView.svelte` |
| Session-Expired i18n | `api.js`, `en.js`, `de.js` |
| Auth-Guard + Login-Route | `App.svelte` |

---

## 2. Accessibility

### 2.1 Gefundene Probleme

| Problem | Datei:Zeile | Status |
|---------|-------------|--------|
| Fehlendes `role="alert"` auf Error-Banner | `LoginView.svelte:76` | **Behoben** |
| 13× `svelte-ignore a11y_*` | 8 Dateien | Dokumentiert |
| No-op `onkeydown` Handler | `ManageView.svelte:461`, `TranslationDashboard.svelte:325` | Dokumentiert |
| Fehlende Form-Labels | `DocumentsView.svelte:440-456`, `MvpDebateView.svelte:1324` | Dokumentiert |
| Fehlende Space-Key-Behandlung | `MvpDebateView.svelte:1244`, `DocumentsView.svelte:408` | Dokumentiert |

### 2.2 Positiv

- Keine `<img>` ohne `alt`-Attribut (Emojis statt Bilder)
- Health-Status-Indikator hat Text-Alternative
- Farb-Indikatoren haben immer Text-Pendants

---

## 3. UI-Konsistenz

### 3.1 Gemischte Styling-Ansätze (Critical)

| Ansatz | Verwendung |
|--------|-----------|
| Tailwind Utility Classes | DocumentsView, Header, Sidebar, ArchiveView, ManageView, ProjectsView |
| Component-scoped CSS | MvpDebateView (~1000 Zeilen `<style>`), LoginView |
| CSS Custom Properties | LoginView (`var(--color-primary)`) — kein anderer Komponent nutzt das |

### 3.2 Inkonsistente Dark-Mode-Patterns

| Pattern | Dateien |
|---------|---------|
| Tailwind `dark:` prefix | DocumentsView, Header, Sidebar, ArchiveView |
| `:global(.dark)` selector | MvpDebateView (umfangreich) |
| CSS Custom Properties mit Fallbacks | LoginView (einzigartig) |

### 3.3 Inkonsistente Farbwerte

| Token | LoginView | MvpDebateView | Tailwind-Dateien |
|-------|-----------|---------------|------------------|
| Primary | `var(--color-primary, #3b82f6)` | `#3b82f6` hardcoded | `bg-blue-600` |
| Error | `#c00` | `#ef4444` | `text-red-600` |

### 3.4 Doppelte Token-Refresh-Logik

`auth.js:refreshAccessToken()` und `api.js:attemptTokenRefresh()` implementieren identische Logik unabhängig voneinander. **Kommentar hinzugefügt**, der auf die Unterschiede hinweist.

---

## 4. Offene Punkte (nicht behoben — Follow-up nötig)

| # | Problem | Aufwand | Priorität |
|---|---------|---------|-----------|
| 1 | MvpDebateView: ~80+ hardcoded Strings i18n-migrieren | 4-6h | High |
| 2 | 29 `modules.*`-Keys in de.js übersetzen | 1h | High |
| 3 | Design-Token-System einführen (CSS Custom Properties für alle Komponenten) | 1-2 Tage | Medium |
| 4 | 13× `svelte-ignore a11y_*` auflösen (echte Keyboard-Handler statt No-ops) | 2-3h | Medium |
| 5 | Fehlende Form-Labels ergänzen (DocumentsView RAG-Search, MvpDebateView Interjection) | 1h | Medium |
| 6 | `ManageView.svelte:461` und `TranslationDashboard.svelte:325` — No-op Handler durch echte Keyboard-Navigation ersetzen | 1h | Medium |
| 7 | Header.svelte:156 — hardcoded deutscher `title`-Attribut i18n-migrieren | 15min | Low |
| 8 | `auth.js` Fehlermeldungen (3 Strings) i18n-migrieren | 15min | Low |
