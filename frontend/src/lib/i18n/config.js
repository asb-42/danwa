/**
 * Locale configuration for i18n.
 * 
 * 12 Standard languages: de, en, fr, es, it, pt, ru, zh, ja, ko, sv, el
 * 2 optional RTL languages: ar, he (not loaded by default)
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
