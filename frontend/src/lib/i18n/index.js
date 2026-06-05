/**
 * i18n store for Svelte.
 *
 * Architecture (3-level fallback):
 * 1. Local cached translations (from bundled loaders or HTTP cache)
 * 2. HTTP fetch from backend /api/v1/i18n/{locale}
 * 3. Key itself as ultimate fallback
 *
 * English is the only bundled language (SSOT). All other languages
 * are loaded via language-pack modules (discoverLanguagePacks).
 */

import { writable, derived, get } from 'svelte/store';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES, RTL_LOCALES, customLocales, getLocaleName, registerCustomLocale } from './config.js';

// Eagerly import English as the only bundled SSOT locale.
import enDict from './loaders/en.js';

/** Reactive store holding the current locale code. */
export const locale = writable(DEFAULT_LOCALE);

/** Internal map of loaded translation dictionaries. */
const translations = new Map();
translations.set('en', enDict);

/** Currently active locale. */
let currentLocale = DEFAULT_LOCALE;

/** Track which locales are served by the backend (auto-detected). */
let backendAvailable = false;

/** Track if fallback warning was already shown this session. */
let fallbackWarningShown = false;

/** Callback set by App.svelte to show toast notifications. */
let _toastCallback = null;

/**
 * Register a toast callback for i18n fallback warnings.
 * Called once from App.svelte on mount.
 */
export function setToastCallback(fn) {
  _toastCallback = fn;
}

// ---------------------------------------------------------------------------
// HTTP Loading
// ---------------------------------------------------------------------------

/**
 * Fetch translations from the backend API.
 * Falls back gracefully if no backend is available.
 */
async function fetchTranslationsFromBackend(lang) {
  try {
    const res = await fetch(`/api/v1/i18n/${lang}`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.translations || {};
  } catch {
    backendAvailable = false;
    return null;
  }
}

/**
 * Load a translation dictionary for the given locale.
 * Priority: bundled static → HTTP backend → empty dict.
 */
async function loadLocale(lang) {
  if (translations.has(lang)) return translations.get(lang);

  // 1. Try bundled static loader
  let dict = null;
  try {
    const mod = await import(`./loaders/${lang}.js`);
    dict = mod.default;
  } catch {
    // No static loader for this locale — try backend
  }

  // 2. Try HTTP backend
  if (!dict) {
    if (!backendAvailable) {
      // Probe backend once
      try {
        const res = await fetch('/api/v1/i18n/locales');
        if (res.ok) {
          backendAvailable = true;
        }
      } catch {
        backendAvailable = false;
      }
    }

    if (backendAvailable) {
      dict = await fetchTranslationsFromBackend(lang);
    }
  }

  // 3. Ultimate fallback: empty dict (will fall back key-by-key to en)
  if (!dict) {
    dict = {};
  }

  translations.set(lang, dict);
  return dict;
}

// ---------------------------------------------------------------------------
// i18n Store
// ---------------------------------------------------------------------------

function createI18nStore() {
  const { subscribe, set } = writable(enDict);

  return {
    subscribe,

    /**
     * Switch to a new locale.
     * Supports bundled locales and dynamically registered custom locales.
     *
     * Race fix: the locale store and the dictionary are updated atomically
     * AFTER the new dict is loaded, so components never re-render with the
     * new locale name pointing at the previous (or empty) dictionary during
     * the in-flight network load.
     */
    async setLocale(lang) {
      const isBundled = SUPPORTED_LOCALES.includes(lang);
      const isCustom = customLocales.has(lang);

      if (!isBundled && !isCustom) {
        // Probe backend — try to load from langpack namespace
        const probe = await fetchTranslationsFromBackend(lang);
        if (!probe) {
          console.warn(`[i18n] Locale '${lang}' not available as language pack, falling back to English`);
          if (_toastCallback) {
            _toastCallback({
              message: `UI language "${getLocaleName(lang)}" is not installed. Install the "lang-${lang}" language pack from Build → Modules → Translations, or switch to English.`,
              type: 'warning',
              timeout: 10000,
            });
          }
          lang = DEFAULT_LOCALE;
        }
      }

      // Load the dictionary first; keep currentLocale + locale store in sync
      // with what the dictionary actually contains.
      const dict = await loadLocale(lang);

      currentLocale = lang;
      locale.set(lang);
      set(dict);

      // Persist user preference
      try { localStorage.setItem('locale', lang); } catch {}

      // Update HTML attributes
      document.documentElement.lang = lang;
      document.documentElement.dir = RTL_LOCALES.has(lang) ? 'rtl' : 'ltr';

      // Expose for E2E tests
      window.__locale = lang;
    },

    /**
     * Translate a key with optional parameter interpolation.
     * Fallback chain: locale → en → key
     */
    t(key, params = {}) {
      const dict = translations.get(currentLocale) || {};
      let text = dict[key];
      let usedFallback = false;

      // Level 1: exact key in current locale
      if (text === undefined && currentLocale !== 'en') {
        // Level 2: try English fallback
        const enDict = translations.get('en') || {};
        text = enDict[key];
        if (text !== undefined) {
          usedFallback = true;
        }
      }

      // Level 3: key itself
      if (text === undefined) {
        text = key;
        usedFallback = true;
      }

      // Show one-time fallback warning per session.
      // Deferred via queueMicrotask to avoid Svelte 5 "state_unsafe_mutation"
      // error — i18n.t() is called inside a $derived (tStore), so we must
      // not mutate state synchronously here.
      if (usedFallback && !fallbackWarningShown && currentLocale !== 'en') {
        fallbackWarningShown = true;
        if (_toastCallback) {
          const cb = _toastCallback;
          const msg = `Some UI strings are not yet translated to ${getLocaleName(currentLocale)}. Showing English fallback.`;
          queueMicrotask(() => cb({ message: msg, type: 'warning', timeout: 8000 }));
        }
      }

      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
      });
      return text;
    },

    /**
     * Translate with locale-aware pluralization.
     * keys: { one: "...", other: "..." } — indexed by Intl.PluralRules category
     */
    tn(count, keys) {
      const pr = new Intl.PluralRules(currentLocale);
      const category = pr.select(count);
      const key = keys[category] || keys.other || keys.one || '';
      return this.t(key, { count });
    },

    /** Check if current locale is RTL. */
    isRTL() {
      return RTL_LOCALES.has(currentLocale);
    },

    getLocale() { return currentLocale; },
  };
}

export const i18n = createI18nStore();

/**
 * Reactive translation helper.
 *
 * Re-emits a new `t(key, params)` closure whenever the i18n store updates
 * (i.e. on locale change), so components can do:
 *
 *   import { tStore } from '../lib/i18n/index.js';
 *   let t = $derived($tStore);
 *   <p>{t('common.welcome')}</p>
 *
 * Internally delegates to `i18n.t()` which implements the 3-level fallback
 * chain (current locale → en → key), so missing translations show the
 * English text instead of a raw key like "common.welcome".
 */
export const tStore = derived(i18n, () => (key, params = {}) => i18n.t(key, params));

/**
 * Convenience function for translating keys.
 * Can be used outside Svelte components.
 */
export function t(key, params = {}) {
  return i18n.t(key, params);
}

/**
 * Convenience function for plural-aware translation.
 */
export function tn(count, keys) {
  return i18n.tn(count, keys);
}

/**
 * Format a number according to the current locale.
 */
export function formatNumber(value, options = {}) {
  return new Intl.NumberFormat(currentLocale, options).format(value);
}

/**
 * Format a date according to the current locale.
 */
export function formatDate(date, options = {}) {
  const defaults = { year: 'numeric', month: '2-digit', day: '2-digit' };
  return new Intl.DateTimeFormat(currentLocale, { ...defaults, ...options }).format(new Date(date));
}

/**
 * Relative time formatter (e.g. "vor 3 Stunden", "3 hours ago").
 */
export function formatRelativeTime(value, unit, options = {}) {
  const rtf = new Intl.RelativeTimeFormat(currentLocale, { numeric: 'auto', ...options });
  return rtf.format(value, unit);
}

/**
 * List/Set/Duration formatters.
 */
export function formatList(items) {
  return new Intl.ListFormat(currentLocale, { type: 'conjunction' }).format(items);
}

/**
 * Discover installed language-pack modules and register them as custom locales.
 * Called once at app startup.
 */
export async function discoverLanguagePacks() {
  try {
    const res = await fetch('/api/v1/modules/?category=translations');
    if (!res.ok) return;
    const modules = await res.json();
    for (const mod of modules) {
      if (mod.type !== 'language-pack') continue;
      // Only register explicitly enabled language packs
      if (mod.enabled !== true) continue;
      const locale = mod.language || mod.module_id.replace(/^lang-/, '').replace(/-[^-]+$/, '');
      if (!locale || SUPPORTED_LOCALES.includes(locale)) continue;
      if (customLocales.has(locale)) continue;

      const name = mod.name?.en || mod.name?.[Object.keys(mod.name || {})[0]] || locale;
      registerCustomLocale({ locale, name, is_rtl: RTL_LOCALES.has(locale) });
      console.log(`[i18n] Registered language pack: ${locale} (${name})`);
    }
  } catch (e) {
    console.warn('[i18n] Failed to discover language packs:', e);
  }
}
