/**
 * Visual regression tests for Dashboard view.
 * Compares screenshots against baseline snapshots.
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from '../helpers.js';

test.describe('Dashboard — Visual Regression', () => {
  test('dashboard default state', async ({ page }) => {
    await waitForAppLoad(page);
    // Wait for health check to complete and render
    await expect(page.locator('header')).toContainText('ok', { timeout: 5000 });
    // Small delay for animations to settle
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('dashboard-default.png', {
      maxDiffPixels: 500,
    });
  });

  test('dashboard with stats cards visible', async ({ page }) => {
    await waitForAppLoad(page);
    await expect(page.locator('header')).toContainText('ok', { timeout: 5000 });
    await page.waitForTimeout(500);

    // Verify the stats cards area is visible
    await expect(page.locator('h2')).toContainText('Dashboard');
    await expect(page).toHaveScreenshot('dashboard-stats.png', {
      maxDiffPixels: 500,
    });
  });
});
