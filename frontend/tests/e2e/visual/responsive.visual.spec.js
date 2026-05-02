/**
 * Visual regression tests for responsive layouts.
 * Tests mobile and tablet viewports across all views.
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from '../helpers.js';

test.describe('Responsive — Visual Regression', () => {
  test('dashboard on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 }); // iPhone SE
    await waitForAppLoad(page);
    await expect(page.locator('header')).toContainText('ok', { timeout: 5000 });
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('dashboard-mobile.png', {
      maxDiffPixels: 500,
    });
  });

  test('debate form on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 }); // iPad
    await waitForAppLoad(page);
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('debate-tablet.png', {
      maxDiffPixels: 500,
    });
  });

  test('audit view on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await waitForAppLoad(page);
    await page.click('nav[aria-label="Main navigation"] button:has-text("Audit Trail")');
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('audit-mobile.png', {
      maxDiffPixels: 500,
    });
  });

  test('config view on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await waitForAppLoad(page);
    await page.click('nav[aria-label="Main navigation"] button:has-text("Config")');
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('config-tablet.png', {
      maxDiffPixels: 500,
    });
  });
});
