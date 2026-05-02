/**
 * Accessibility tests for Config view.
 * Uses axe-core to check WCAG 2.1 AA compliance.
 */

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { waitForAppLoad } from '../helpers.js';

test.describe('Config — Accessibility', () => {
  /** Navigate to the Config view via sidebar */
  async function goToConfig(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Config")');
  }

  test('has no WCAG 2.1 AA violations', async ({ page }) => {
    await waitForAppLoad(page);
    await goToConfig(page);
    await page.waitForTimeout(300);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('form inputs have associated labels', async ({ page }) => {
    await waitForAppLoad(page);
    await goToConfig(page);

    const inputs = page.locator('input:not([type="hidden"])');
    const count = await inputs.count();
    for (let i = 0; i < count; i++) {
      const id = await inputs.nth(i).getAttribute('id');
      const ariaLabel = await inputs.nth(i).getAttribute('aria-label');
      const ariaLabelledBy = await inputs.nth(i).getAttribute('aria-labelledby');
      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        const hasLabel = await label.count() > 0;
        expect(hasLabel || ariaLabel || ariaLabelledBy).toBeTruthy();
      } else {
        expect(ariaLabel || ariaLabelledBy).toBeTruthy();
      }
    }
  });
});
