/**
 * Accessibility tests for Debate view.
 * Uses axe-core to check WCAG 2.1 AA compliance.
 */

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { waitForAppLoad } from '../helpers.js';

test.describe('Debate — Accessibility', () => {
  /** Navigate to the Debate view via sidebar */
  async function goToDebate(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
  }

  test('has no WCAG 2.1 AA violations on empty form', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);
    await page.waitForTimeout(300);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('has no WCAG 2.1 AA violations with filled form', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    await page.fill('#case-text', 'Accessibility test debate');
    await page.fill('#max-rounds', '5');
    await page.fill('#consensus-threshold', '0.9');
    await page.waitForTimeout(300);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('form inputs have associated labels', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    const inputs = page.locator('input:not([type="hidden"]), textarea');
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
