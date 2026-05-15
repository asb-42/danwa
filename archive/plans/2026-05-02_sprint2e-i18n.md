# Sprint 2e: Internationalization & Localization Tests

## Goal
The debate engine UI must work for both German and English users. The backend/FastAPI communicates in English, but the forum/Drupal is German. Clean separation: UI strings are translatable, API communication stays English.

## Architecture

### Key Principle
- **UI layer**: Translatable via i18n store (Svelte stores + lazy-loaded translation files)
- **API layer**: Always English (`Accept-Language: en` header)
- **Backend errors**: Translated client-side before display

### i18n Initialization

```javascript
// src/lib/i18n/config.js
export const SUPPORTED_LOCALES = ['de', 'en'];
export const DEFAULT_LOCALE = 'de';
export const LOCALE_NAMES = { de: 'Deutsch', en: 'English' };
export const RTL_LOCALES = ['ar', 'he', 'fa']; // Future preparation
```

### Translation Store

```javascript
// src/lib/i18n/index.js
import { writable, derived } from 'svelte/store';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from './config.js';

export const locale = writable(DEFAULT_LOCALE);

function createI18nStore() {
  const translations = new Map();
  let currentLocale = DEFAULT_LOCALE;

  async function loadLocale(lang) {
    if (translations.has(lang)) return translations.get(lang);
    const module = await import(`./loaders/${lang}.js`);
    translations.set(lang, module.default);
    return module.default;
  }

  const { subscribe, set } = writable({});

  return {
    subscribe,
    async setLocale(lang) {
      if (!SUPPORTED_LOCALES.includes(lang)) {
        console.warn(`Unsupported locale: ${lang}, falling back to ${DEFAULT_LOCALE}`);
        lang = DEFAULT_LOCALE;
      }
      currentLocale = lang;
      locale.set(lang);
      const dict = await loadLocale(lang);
      set(dict);
    },
    t(key, params = {}) {
      const dict = translations.get(currentLocale) || {};
      let text = dict[key] || key;
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
      });
      return text;
    }
  };
}

export const i18n = createI18nStore();
i18n.setLocale(DEFAULT_LOCALE);

export function t(key, params = {}) {
  return i18n.t(key, params);
}
```

### Translation Files

Translation keys organized by domain:

| Domain | Example Keys |
|--------|-------------|
| Navigation | `nav.dashboard`, `nav.debate`, `nav.audit`, `nav.config` |
| Dashboard | `dashboard.title`, `dashboard.totalDebates`, `dashboard.completed`, `dashboard.avgConsensus` |
| Debate | `debate.title`, `debate.caseLabel`, `debate.startButton`, `debate.status`, `debate.round` |
| Agents | `agent.strategist`, `agent.critic`, `agent.optimizer`, `agent.moderator` |
| Audit | `audit.title`, `audit.time`, `audit.debate`, `audit.round`, `audit.agent` |
| Config | `config.title`, `config.llmProvider`, `config.maxRounds`, `config.save` |
| Common | `common.loading`, `common.error`, `common.retry`, `common.cancel` |
| Errors | `error.backendDisconnected`, `error.debateNotFound`, `error.invalidInput` |

### API Isolation

```javascript
// src/lib/api.js (extension)
const API_HEADERS = {
  'Content-Type': 'application/json',
  'Accept-Language': 'en'  // Backend always English
};

function translateBackendError(backendMessage) {
  const errorMap = {
    'Debate not found': 'error.debateNotFound',
    'Invalid input': 'error.invalidInput',
    'Backend connection lost': 'error.backendDisconnected'
  };
  const key = errorMap[backendMessage] || 'common.error';
  return i18n.t(key);
}
```

### Svelte Component Integration

```svelte
<!-- App.svelte -->
<script>
  import { onMount } from 'svelte';
  import { i18n, locale, t } from './lib/i18n/index.js';
  import LanguageSwitcher from './components/LanguageSwitcher.svelte';

  let translations = {};

  onMount(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const urlLang = urlParams.get('lang');
    const storedLang = localStorage.getItem('locale');
    const initialLang = urlLang || storedLang || 'de';
    i18n.setLocale(initialLang);

    const unsub = i18n.subscribe(dict => { translations = dict; });
    return unsub;
  });

  function _(key, params = {}) { return translations[key] || key; }
</script>

<LanguageSwitcher />
<h2>{_('dashboard.title')}</h2>
<button>{_('debate.startButton')}</button>
```

```svelte
<!-- components/LanguageSwitcher.svelte -->
<script>
  import { locale, i18n } from '../lib/i18n/index.js';
  import { SUPPORTED_LOCALES, LOCALE_NAMES } from '../lib/i18n/config.js';

  async function switchLanguage(lang) {
    await i18n.setLocale(lang);
    localStorage.setItem('locale', lang);
    document.documentElement.lang = lang;
  }
</script>

<div class="flex gap-2" role="group" aria-label="Language selection">
  {#each SUPPORTED_LOCALES as lang}
    <button
      on:click={() => switchLanguage(lang)}
      class="px-3 py-1 text-sm rounded transition-colors
             {$locale === lang ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}"
      aria-pressed={$locale === lang}
      aria-label={LOCALE_NAMES[lang]}
    >
      {lang.toUpperCase()}
    </button>
  {/each}
</div>
```

## Directory Structure (extension)

```
frontend/
├── src/
│   ├── lib/
│   │   ├── i18n/
│   │   │   ├── index.js           # i18n store initialization
│   │   │   ├── config.js          # Locale configuration
│   │   │   └── loaders/           # Lazy-loaded translations
│   │   │       ├── de.js
│   │   │       └── en.js
│   ├── components/
│   │   └── LanguageSwitcher.svelte
│   └── views/
│       └── ... (translated views)
├── tests/
│   └── e2e/
│       └── i18n/
│           ├── setup.i18n.js      # Language context for tests
│           ├── locale.spec.js     # Translation completeness
│           ├── rtl.spec.js        # RTL preparation
│           ├── formatting.spec.js # Numbers, dates, pluralization
│           └── api-isolation.spec.js  # UI language vs API language
```

## E2E Test Coverage

### Translation Completeness (`locale.spec.js`)

| Test | Locales | Check |
|------|---------|-------|
| All navigation items translated | de, en | No raw keys visible |
| No untranslated keys visible | de, en | No `domain.key` patterns in DOM |
| Dashboard stats have translated labels | de, en | Expected text visible |
| Debate form labels translated | de, en | Labels match locale |
| Agent names translated | de, en | Strategist/Stratege etc. |
| Error messages translated | de, en | Error text matches locale |

### Locale Formatting (`formatting.spec.js`)

| Test | Locale | Expected |
|------|--------|----------|
| German number format | de | `0,87` (comma decimal) |
| English number format | en | `0.87` (point decimal) |
| Date formatting | de | `DD.MM.YYYY` |
| Date formatting | en | `YYYY-MM-DD` |
| Pluralization | de | `1 Debatte` vs `2 Debatten` |

### API Isolation (`api-isolation.spec.js`)

| Test | Check |
|------|-------|
| Backend receives English headers | `Accept-Language: en` regardless of UI locale |
| Backend errors translated to UI locale | 404 → `Debatte nicht gefunden` (de) / `Debate not found` (en) |
| API response data not translated | Backend data stays English, only UI chrome translated |

### RTL Preparation (`rtl.spec.js`)

| Test | Check |
|------|-------|
| HTML `dir` attribute set | `ltr` or `rtl` |
| CSS logical properties used | `margin-inline-start` instead of `margin-left` |

### Test Setup

```javascript
// tests/e2e/i18n/setup.i18n.js
import { test as base, expect } from '@playwright/test';

export const i18nTest = base.extend({
  locale: ['de', { option: true }],
  page: async ({ page, locale }, use) => {
    await page.goto(`/#dashboard?lang=${locale}`);
    await page.waitForFunction(
      (expectedLocale) => window.__locale === expectedLocale,
      locale,
      { timeout: 5000 }
    );
    await use(page);
  }
});

export { expect };
```

## package.json Scripts

```json
{
  "scripts": {
    "test:i18n": "playwright test tests/e2e/i18n/",
    "test:i18n:de": "playwright test tests/e2e/i18n/ --project=chromium --grep-invert 'en'",
    "test:i18n:en": "playwright test tests/e2e/i18n/ --project=chromium --grep-invert 'de'"
  }
}
```

## Deliverables

- [ ] `npm run test:i18n` passes for both `de` and `en`
- [ ] No raw translation keys visible in UI
- [ ] API communication stays English (`Accept-Language: en`)
- [ ] Backend errors displayed in UI locale
- [ ] Numbers/dates formatted per locale
- [ ] HTML `lang` and `dir` attributes set correctly
- [ ] Language switcher persists choice in `localStorage`
- [ ] CI pipeline runs i18n tests for both locales
