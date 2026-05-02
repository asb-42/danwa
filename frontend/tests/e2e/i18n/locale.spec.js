/**
 * Translation Completeness Tests (locale.spec.js)
 *
 * Verifies that all UI strings are translated for both de and en locales.
 * No raw translation keys (e.g. "dashboard.title") should be visible in the DOM.
 */
import { i18nTest as test, expect, gotoRoute } from './setup.i18n.js';

/**
 * Helper: collect all visible text nodes and check for raw translation keys.
 */
async function assertNoRawKeys(page) {
  const rawKeys = await page.evaluate(() => {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null,
      false
    );
    const keys = [];
    let node;
    while ((node = walker.nextNode())) {
      const text = node.textContent.trim();
      if (text && /^(nav|dashboard|debate|audit|config|common|error|agent|status|lang)\.[a-zA-Z]+$/.test(text)) {
        keys.push(text);
      }
    }
    return keys;
  });
  expect(rawKeys).toEqual([]);
}

test.describe('Translation Completeness — German (de)', () => {
  test.use({ locale: 'de' });

  test('no raw translation keys visible on dashboard', async ({ page }) => {
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });

  test('dashboard stats have German labels', async ({ page }) => {
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Backend-Status')).toBeVisible();
    await expect(page.getByText('Debatten gesamt')).toBeVisible();
  });

  test('navigation items are translated to German', async ({ page }) => {
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Debatte' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Prüfpfad' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Konfiguration' })).toBeVisible();
  });

  test('debate form labels are translated to German', async ({ page }) => {
    await gotoRoute(page, 'debate');
    await page.waitForTimeout(500);
    await expect(page.getByText('Neue Debatte')).toBeVisible();
    await expect(page.getByText('Fallbeschreibung')).toBeVisible();
    await expect(page.getByText('Maximale Runden')).toBeVisible();
    await expect(page.getByText('Konsens-Schwellenwert')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Debatte erstellen' })).toBeVisible();
  });

  test('no raw translation keys visible on debate page', async ({ page }) => {
    await gotoRoute(page, 'debate');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });

  test('config page labels are translated to German', async ({ page }) => {
    await gotoRoute(page, 'config');
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'Konfiguration' })).toBeVisible();
    await expect(page.getByText('Debatten-Standardwerte')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Konfiguration speichern' })).toBeVisible();
  });

  test('no raw translation keys visible on config page', async ({ page }) => {
    await gotoRoute(page, 'config');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });

  test('audit page labels are translated to German', async ({ page }) => {
    await gotoRoute(page, 'audit');
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'Prüfpfad', exact: true })).toBeVisible();
    await expect(page.getByText('Debatten-ID')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ereignisse laden' })).toBeVisible();
  });

  test('no raw translation keys visible on audit page', async ({ page }) => {
    await gotoRoute(page, 'audit');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });
});

test.describe('Translation Completeness — English (en)', () => {
  test.use({ locale: 'en' });

  test('no raw translation keys visible on dashboard', async ({ page }) => {
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });

  test('dashboard stats have English labels', async ({ page }) => {
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Backend Status')).toBeVisible();
    await expect(page.getByText('Total Debates')).toBeVisible();
  });

  test('navigation items are translated to English', async ({ page }) => {
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Debate' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Audit Trail' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Configuration' })).toBeVisible();
  });

  test('debate form labels are translated to English', async ({ page }) => {
    await gotoRoute(page, 'debate');
    await page.waitForTimeout(500);
    await expect(page.getByText('New Debate')).toBeVisible();
    await expect(page.getByText('Case Description')).toBeVisible();
    await expect(page.getByText('Max Rounds')).toBeVisible();
    await expect(page.getByText('Consensus Threshold')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create Debate' })).toBeVisible();
  });

  test('no raw translation keys visible on debate page', async ({ page }) => {
    await gotoRoute(page, 'debate');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });

  test('config page labels are translated to English', async ({ page }) => {
    await gotoRoute(page, 'config');
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'Configuration' })).toBeVisible();
    await expect(page.getByText('Debate Defaults')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save Configuration' })).toBeVisible();
  });

  test('no raw translation keys visible on config page', async ({ page }) => {
    await gotoRoute(page, 'config');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });

  test('audit page labels are translated to English', async ({ page }) => {
    await gotoRoute(page, 'audit');
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'Audit Trail' })).toBeVisible();
    await expect(page.getByText('Debate ID')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Load Events' })).toBeVisible();
  });

  test('no raw translation keys visible on audit page', async ({ page }) => {
    await gotoRoute(page, 'audit');
    await page.waitForTimeout(500);
    await assertNoRawKeys(page);
  });
});

test.describe('Language Switcher', () => {
  test('switching from German to English updates all labels', async ({ page }) => {
    // Start in German (default from fixture)
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await expect(page.getByText('Debatten gesamt')).toBeVisible();

    // Switch to English
    await page.getByRole('button', { name: 'English' }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText('Total Debates')).toBeVisible();
  });

  test('switching from English to German updates all labels', async ({ page }) => {
    // Start in German (default from fixture), switch to English first
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await expect(page.getByText('Debatten gesamt')).toBeVisible();

    // Switch to English
    await page.getByRole('button', { name: 'English' }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText('Total Debates')).toBeVisible();

    // Switch back to German
    await page.getByRole('button', { name: 'Deutsch' }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText('Debatten gesamt')).toBeVisible();
  });

  test('language choice persists in localStorage', async ({ page }) => {
    // Start in German
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(300);

    // Switch to English
    await page.getByRole('button', { name: 'English' }).click();
    await page.waitForTimeout(300);

    // Check localStorage
    const stored = await page.evaluate(() => localStorage.getItem('locale'));
    expect(stored).toBe('en');
  });

  test('HTML lang attribute is set correctly', async ({ page }) => {
    await expect(page.locator('html')).toHaveAttribute('lang', 'de');

    // Switch to English
    await page.getByRole('button', { name: 'English' }).click();
    await page.waitForTimeout(300);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  });
});
