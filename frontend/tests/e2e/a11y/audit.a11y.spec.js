/**
 * Accessibility tests for Audit view.
 * Uses axe-core to check WCAG 2.1 AA compliance.
 */

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { waitForAppLoad, createDebateViaAPI, startDebateViaAPI } from '../helpers.js';

test.describe('Audit — Accessibility', () => {
  /** Navigate to the Audit view via sidebar */
  async function goToAudit(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Audit Trail")');
  }

  test('has no WCAG 2.1 AA violations on empty state', async ({ page }) => {
    await waitForAppLoad(page);
    await goToAudit(page);
    await page.waitForTimeout(300);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('has no WCAG 2.1 AA violations with data', async ({ page, request }) => {
    const debate = await createDebateViaAPI(request, 'Audit a11y test');
    await startDebateViaAPI(request, debate.debate_id);

    await waitForAppLoad(page);
    await goToAudit(page);

    await page.fill('#debate-id', debate.debate_id);
    await page.click('button:has-text("Load Events")');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(300);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('table has proper headers with scope', async ({ page, request }) => {
    const debate = await createDebateViaAPI(request, 'Audit header test');
    await startDebateViaAPI(request, debate.debate_id);

    await waitForAppLoad(page);
    await goToAudit(page);

    await page.fill('#debate-id', debate.debate_id);
    await page.click('button:has-text("Load Events")');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });

    const headers = page.locator('table th');
    const count = await headers.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      const scope = await headers.nth(i).getAttribute('scope');
      expect(scope).toBe('col');
    }
  });
});
