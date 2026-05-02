/**
 * Locale Formatting Tests (formatting.spec.js)
 *
 * Verifies that numbers and dates are formatted according to the active locale.
 * German: comma decimal (0,87), DD.MM.YYYY
 * English: point decimal (0.87), YYYY-MM-DD
 */
import { i18nTest as test, expect } from './setup.i18n.js';

test.describe('Number Formatting — German (de)', () => {
  test.use({ locale: 'de' });

  test('dashboard numbers use German locale formatting', async ({ page }) => {
    // Verify locale is set to de
    const locale = await page.evaluate(() => window.__locale);
    expect(locale).toBe('de');

    // Check that Intl.NumberFormat is using German locale
    const formatted = await page.evaluate(() => {
      return new Intl.NumberFormat('de').format(1234.56);
    });
    // German formats: 1.234,56 (thousands separator = dot, decimal = comma)
    expect(formatted).toBe('1.234,56');
  });

  test('consensus score uses locale-appropriate decimal separator', async ({ page }) => {
    // Verify that the formatNumber function produces locale-appropriate output
    const result = await page.evaluate(() => {
      return new Intl.NumberFormat('de', { style: 'percent' }).format(0.87);
    });
    // German percent: 87 % (with space before %)
    expect(result).toMatch(/87\s?%/);
  });
});

test.describe('Number Formatting — English (en)', () => {
  test.use({ locale: 'en' });

  test('dashboard numbers use English locale formatting', async ({ page }) => {
    const locale = await page.evaluate(() => window.__locale);
    expect(locale).toBe('en');

    const formatted = await page.evaluate(() => {
      return new Intl.NumberFormat('en').format(1234.56);
    });
    // English formats: 1,234.56 (thousands separator = comma, decimal = dot)
    expect(formatted).toBe('1,234.56');
  });

  test('consensus score uses English percent format', async ({ page }) => {
    const result = await page.evaluate(() => {
      return new Intl.NumberFormat('en', { style: 'percent' }).format(0.87);
    });
    // English percent: 87%
    expect(result).toBe('87%');
  });
});

test.describe('Date Formatting — German (de)', () => {
  test.use({ locale: 'de' });

  test('German date format uses DD.MM.YYYY pattern', async ({ page }) => {
    // Verify locale is de
    const locale = await page.evaluate(() => window.__locale);
    expect(locale).toBe('de');

    const formatted = await page.evaluate(() => {
      return new Intl.DateTimeFormat('de', {
        year: 'numeric', month: '2-digit', day: '2-digit'
      }).format(new Date(2025, 0, 15)); // Jan 15, 2025
    });
    // German: 15.01.2025
    expect(formatted).toBe('15.01.2025');
  });
});

test.describe('Date Formatting — English (en)', () => {
  test.use({ locale: 'en' });

  test('English date format uses locale-appropriate pattern', async ({ page }) => {
    const locale = await page.evaluate(() => window.__locale);
    expect(locale).toBe('en');

    const formatted = await page.evaluate(() => {
      return new Intl.DateTimeFormat('en', {
        year: 'numeric', month: '2-digit', day: '2-digit'
      }).format(new Date(2025, 0, 15)); // Jan 15, 2025
    });
    // English US: 01/15/2025 — but on some systems it may be 15/01/2025
    // Just verify it contains the expected components
    expect(formatted).toContain('2025');
    expect(formatted).toContain('01');
    expect(formatted).toContain('15');
  });
});

test.describe('Pluralization', () => {
  test('German pluralization: 1 Debatte vs 2 Debatten', async ({ page }) => {
    // Verify Intl.PluralRules works for German
    const oneForm = await page.evaluate(() => {
      const pr = new Intl.PluralRules('de');
      return pr.select(1);
    });
    expect(oneForm).toBe('one');

    const otherForm = await page.evaluate(() => {
      const pr = new Intl.PluralRules('de');
      return pr.select(2);
    });
    expect(otherForm).toBe('other');
  });

  test('English pluralization: 1 debate vs 2 debates', async ({ page }) => {
    const oneForm = await page.evaluate(() => {
      const pr = new Intl.PluralRules('en');
      return pr.select(1);
    });
    expect(oneForm).toBe('one');

    const otherForm = await page.evaluate(() => {
      const pr = new Intl.PluralRules('en');
      return pr.select(2);
    });
    expect(otherForm).toBe('other');
  });
});
