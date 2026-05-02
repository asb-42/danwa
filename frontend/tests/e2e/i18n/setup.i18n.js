/**
 * i18n test setup — provides a test fixture that navigates to a page
 * with a specific locale and waits for translations to load.
 */
import { test as base, expect } from '@playwright/test';

/**
 * Helper: navigate to a hash route without full page reload.
 * This preserves the i18n state (translations already loaded).
 */
export async function gotoRoute(page, route) {
  await page.evaluate((r) => { window.location.hash = `#/${r}`; }, route);
  // Wait for Svelte to react to the hash change
  await page.waitForTimeout(300);
}

/**
 * Extended test fixture with locale support.
 * Navigates to /?lang=${locale}, waits for translations to load,
 * then persists the locale to localStorage.
 */
export const i18nTest = base.extend({
  locale: ['de', { option: true }],
  page: async ({ page, locale }, use) => {
    // Navigate with lang query param
    await page.goto(`/?lang=${locale}`);
    // Wait for i18n to initialize — window.__locale is set by i18n.setLocale()
    await page.waitForFunction(
      (expectedLocale) => window.__locale === expectedLocale,
      locale,
      { timeout: 5000 }
    );
    // Persist to localStorage so subsequent navigations pick it up
    await page.evaluate((lang) => localStorage.setItem('locale', lang), locale);
    await use(page);
  }
});

export { expect };
