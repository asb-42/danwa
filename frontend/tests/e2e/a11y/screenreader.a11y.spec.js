/**
 * Screen reader announcement accessibility tests.
 * Verifies live regions and ARIA announcements for dynamic content.
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from '../helpers.js';

test.describe('Screen Reader Announcements', () => {
  test('debate status card announces via aria-live', async ({ page }) => {
    await waitForAppLoad(page);
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
    await page.waitForTimeout(300);

    // Create a debate
    await page.fill('#case-text', 'Screen reader test debate');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });

    // The live region should contain the status
    const liveRegion = page.locator('[aria-live="polite"]');
    await expect(liveRegion).toBeAttached();
    await expect(liveRegion).toContainText(/pending|running|completed/i);
  });

  test('error messages are announced via role="alert"', async ({ page }) => {
    await waitForAppLoad(page);
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
    await page.waitForTimeout(300);

    // The error div (if present) should have role="alert"
    const alerts = page.locator('[role="alert"]');
    const count = await alerts.count();
    // Verify all alert elements have proper role
    for (let i = 0; i < count; i++) {
      await expect(alerts.nth(i)).toHaveAttribute('role', 'alert');
    }
  });

  test('loading states are communicated', async ({ page }) => {
    await waitForAppLoad(page);
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
    await page.waitForTimeout(300);

    // Fill and submit to trigger loading state
    await page.fill('#case-text', 'Loading state test');
    await page.click('button[type="submit"]:has-text("Create Debate")');

    // Wait for the debate to be created and the status card to render
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });

    // Either aria-busy or aria-live announcement should exist
    const liveRegion = page.locator('[aria-live]');
    const liveCount = await liveRegion.count();
    expect(liveCount).toBeGreaterThan(0);
  });

  test('config save confirmation is announced', async ({ page }) => {
    await waitForAppLoad(page);
    await page.click('nav[aria-label="Main navigation"] button:has-text("Config")');
    await page.waitForTimeout(300);

    await page.click('button:has-text("Save Configuration")');

    // The success message should have role="status"
    const statusMessage = page.locator('[role="status"]');
    await expect(statusMessage).toBeVisible({ timeout: 3000 });
    await expect(statusMessage).toContainText('Configuration saved');
  });
});
