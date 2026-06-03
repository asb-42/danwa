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

/**
 * Display names for all known locales.
 *
 * Starts with 'en' (the only bundled language). All other entries are
 * added dynamically at runtime by registerCustomLocale() when
 * language-pack modules are discovered (via discoverLanguagePacks()).
 */
export const LOCALE_NAMES = {
  en: 'English',
};

export const RTL_LOCALES = new Set(['ar', 'he', 'fa']);

/** Runtime-registered custom locales. Populated by discoverLanguagePacks() on mount. */
export const customLocales = new Map();

/**
 * Register a custom locale discovered from the backend or a language-pack module.
 * Updates both the customLocales Map and LOCALE_NAMES so all consumers
 * (LanguageSwitcher, getLocaleName, getAllLocales) see consistent data.
 *
 * @param {{ locale: string, name: string, is_rtl: boolean }} info
 */
export function registerCustomLocale(info) {
  customLocales.set(info.locale, { name: info.name, isRtl: info.is_rtl });
  // Keep LOCALE_NAMES in sync — this is the single source of truth for display names
  if (!LOCALE_NAMES[info.locale]) {
    LOCALE_NAMES[info.locale] = info.name;
  }
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
  const all = [...bundled, ...custom];
  // Sort alphabetically by display name (keep 'en' first as default)
  return all.sort((a, b) => {
    if (a === 'en') return -1;
    if (b === 'en') return 1;
    const nameA = (customLocales.get(a)?.name || LOCALE_NAMES[a] || a).toLowerCase();
    const nameB = (customLocales.get(b)?.name || LOCALE_NAMES[b] || b).toLowerCase();
    return nameA.localeCompare(nameB);
  });
}

// How many string IDs to load per HTTP batch request
export const HTTP_BATCH_SIZE = 200;
