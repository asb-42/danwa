/**
 * Locale configuration for i18n.
 *
 * 12 Standard languages: de, en, fr, es, it, pt, ru, zh, ja, ko, sv, el
 * 2 optional RTL languages: ar, he (not loaded by default)
 *
 * Custom locales (registered via backend) are added dynamically at runtime.
 */

export const SUPPORTED_LOCALES = [
  'de',  // Deutsch
  'en',  // English
  'fr',  // Français
  'es',  // Español
  'it',  // Italiano
  'pt',  // Português
  'ru',  // Русский
  'zh',  // 中文
  'ja',  // 日本語
  'ko',  // 한국어
  'sv',  // Svenska
  'el',  // Ελληνικά
  'ar',  // العربية (RTL, optional)
  'he',  // עברית (RTL, optional)
];

export const DEFAULT_LOCALE = 'de';

export const LOCALE_NAMES = {
  de: 'Deutsch',
  en: 'English',
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

/** Runtime-registered custom locales. Populated by LanguageSwitcher on mount. */
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

// Plural tags per locale (based on Intl.PluralRules)
export const PLURAL_TAGS = {
  de: ['one', 'other'],
  en: ['one', 'other'],
  fr: ['one', 'other'],
  es: ['one', 'other'],
  it: ['one', 'other'],
  pt: ['one', 'other'],
  ru: ['one', 'few', 'many', 'other'],
  zh: ['other'],
  ja: ['other'],
  ko: ['one', 'other'],
  sv: ['one', 'other'],
  el: ['one', 'other'],
  ar: ['zero', 'one', 'two', 'few', 'many', 'other'],
  he: ['one', 'two', 'many', 'other'],
};

// How many string IDs to load per HTTP batch request
export const HTTP_BATCH_SIZE = 200;
