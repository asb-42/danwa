/**
 * Locale configuration for i18n.
 *
 * English is the only bundled system language (SSOT).
 * All other languages are optional language-pack modules.
 *
 * Custom locales (registered via backend) are added dynamically at runtime
 * by discoverLanguagePacks() in index.js.
 */

export const SUPPORTED_LOCALES = ['en'];

export const DEFAULT_LOCALE = 'en';

/** Display names for all known locales (bundled + module-installable). */
export const LOCALE_NAMES = {
  en: 'English',
  de: 'Deutsch',
  fr: 'Français',
  es: 'Español',
  it: 'Italiano',
  pt: 'Português',
  ru: 'Русский',
  zh: '中文',
  ja: '日本語',
  ko: '한국어',
  sv: 'Svenska',
  el: 'Ελληνικά',
  ar: 'العربية',
  he: 'עברית',
};

export const RTL_LOCALES = new Set(['ar', 'he', 'fa']);

/** Runtime-registered custom locales. Populated by discoverLanguagePacks() on mount. */
export const customLocales = new Map();

/**
 * Register a custom locale discovered from the backend.
 * @param {{ locale: string, name: string, is_rtl: boolean }} info
 */
export function registerCustomLocale(info) {
  customLocales.set(info.locale, { name: info.name, isRtl: info.is_rtl });
  if (info.is_rtl) RTL_LOCALES.add(info.locale);
}

/**
 * Get the display name for any locale (bundled or custom).
 */
export function getLocaleName(code) {
  return customLocales.get(code)?.name || LOCALE_NAMES[code] || code;
}

/**
 * Get the combined list of all available locales (bundled + custom).
 */
export function getAllLocales() {
  const bundled = SUPPORTED_LOCALES.filter(l => !customLocales.has(l));
  const custom = [...customLocales.keys()];
  return [...bundled, ...custom];
}

// How many string IDs to load per HTTP batch request
export const HTTP_BATCH_SIZE = 200;
