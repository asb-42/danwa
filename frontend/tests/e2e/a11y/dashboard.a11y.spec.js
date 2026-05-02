/**
 * Accessibility tests for Dashboard view.
 * Uses axe-core to check WCAG 2.1 AA compliance.
 */

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { waitForAppLoad } from '../helpers.js';

test.describe('Dashboard — Accessibility', () => {
  test('has no WCAG 2.1 AA violations', async ({ page }) => {
    await waitForAppLoad(page);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('has proper landmark roles', async ({ page }) => {
    await waitForAppLoad(page);

    await expect(page.locator('main, [role="main"]')).toBeAttached();
    await expect(page.locator('nav, [role="navigation"]')).toBeAttached();
    await expect(page.locator('header, [role="banner"]')).toBeAttached();
  });

  test('has skip-to-content link', async ({ page }) => {
    await waitForAppLoad(page);

    const skipLink = page.locator('a[href="#main-content"]');
    await expect(skipLink).toBeAttached();
  });
});
