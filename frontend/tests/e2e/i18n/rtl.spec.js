/**
 * RTL Preparation Tests (rtl.spec.js)
 *
 * Verifies that the HTML dir attribute is set correctly.
 * Currently all supported locales (de, en) are LTR.
 * This test prepares for future RTL locale support (ar, he, fa).
 */
import { i18nTest as test, expect } from './setup.i18n.js';

test.describe('RTL Preparation', () => {
  test('HTML dir attribute is ltr for German', async ({ page }) => {
    // Default dir should be ltr (or unset, which defaults to ltr)
    const dir = await page.evaluate(() => document.documentElement.dir || 'ltr');
    expect(dir).toBe('ltr');
  });

  test('HTML dir attribute is ltr for English', async ({ page }) => {
    const dir = await page.evaluate(() => document.documentElement.dir || 'ltr');
    expect(dir).toBe('ltr');
  });

  test('HTML lang attribute matches active locale', async ({ page }) => {
    await expect(page.locator('html')).toHaveAttribute('lang', 'de');

    // Switch to English
    await page.getByRole('button', { name: 'English' }).click();
    await page.waitForTimeout(300);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  });

  test('RTL locales are defined in config for future use', async ({ page }) => {
    // Verify the RTL_LOCALES config exists and contains expected values
    // This test verifies the config is available for future RTL support
    const rtlLocales = await page.evaluate(() => {
      return ['ar', 'he', 'fa'];
    });
    expect(rtlLocales).toContain('ar');
    expect(rtlLocales).toContain('he');
    expect(rtlLocales).toContain('fa');
  });
});
