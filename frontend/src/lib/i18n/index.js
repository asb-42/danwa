/**
 * i18n store for Svelte.
 * Lazy-loads translation files and provides a reactive `t()` function.
 */

import { writable, derived, get } from 'svelte/store';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from './config.js';

/** Reactive store holding the current locale code. */
export const locale = writable(DEFAULT_LOCALE);

/** Internal map of loaded translation dictionaries. */
const translations = new Map();

/** Currently active locale (synchronous access for `t()`). */
let currentLocale = DEFAULT_LOCALE;

/**
 * Load a translation dictionary for the given locale.
 * Uses dynamic import for lazy-loading.
 */
async function loadLocale(lang) {
  if (translations.has(lang)) return translations.get(lang);
  const module = await import(`./loaders/${lang}.js`);
  translations.set(lang, module.default);
  return module.default;
}

/**
 * Create the main i18n store.
 * Subscribing gives you the current translation dictionary.
 */
function createI18nStore() {
  const { subscribe, set } = writable({});

  return {
    subscribe,
    /**
     * Switch to a new locale. Loads translations if needed.
     * Falls back to DEFAULT_LOCALE for unsupported locales.
     */
    async setLocale(lang) {
      if (!SUPPORTED_LOCALES.includes(lang)) {
        console.warn(`Unsupported locale: ${lang}, falling back to ${DEFAULT_LOCALE}`);
        lang = DEFAULT_LOCALE;
      }
      currentLocale = lang;
      locale.set(lang);
      const dict = await loadLocale(lang);
      set(dict);
      // Expose locale for E2E tests
      window.__locale = lang;
      // Set HTML lang attribute
      document.documentElement.lang = lang;
    },

    /**
     * Translate a key with optional parameter interpolation.
     * Parameters are replaced using `{paramName}` syntax.
     * Returns the key itself if no translation is found.
     */
    t(key, params = {}) {
      const dict = translations.get(currentLocale) || {};
      let text = dict[key] || key;
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
      });
      return text;
    },

    /**
     * Get the current locale code synchronously.
     */
    getLocale() {
      return currentLocale;
    }
  };
}

export const i18n = createI18nStore();

// NOTE: Do NOT call i18n.setLocale() here at module level.
// App.svelte's onMount handles initialization based on URL/localStorage.
// Calling it here would race with the onMount call and could override the user's locale.

/**
 * Convenience function for translating keys.
 * Can be used outside Svelte components.
 */
export function t(key, params = {}) {
  return i18n.t(key, params);
}

/**
 * Format a number according to the current locale.
 * German: 0,87 | English: 0.87
 */
export function formatNumber(value, options = {}) {
  return new Intl.NumberFormat(currentLocale, options).format(value);
}

/**
 * Format a date according to the current locale.
 * German: DD.MM.YYYY | English: YYYY-MM-DD
 */
export function formatDate(date, options = {}) {
  const defaults = { year: 'numeric', month: '2-digit', day: '2-digit' };
  return new Intl.DateTimeFormat(currentLocale, { ...defaults, ...options }).format(new Date(date));
}

/**
 * Pluralization helper.
 * Uses Intl.PluralRules for locale-aware plural forms.
 */
export function pluralize(count, key) {
  const pr = new Intl.PluralRules(currentLocale);
  const category = pr.select(count); // 'one', 'other', etc.
  const pluralKey = `${key}.${category}`;
  const dict = translations.get(currentLocale) || {};
  const text = dict[pluralKey] || dict[`${key}.other`] || dict[key] || key;
  return text.replace('{count}', count);
}
