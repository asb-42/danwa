/**
 * Visual regression tests for Debate view.
 * Compares screenshots against baseline snapshots.
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from '../helpers.js';

test.describe('Debate — Visual Regression', () => {
  /** Navigate to the Debate view via sidebar */
  async function goToDebate(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
  }

  test('empty debate form', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('debate-empty.png', {
      maxDiffPixels: 500,
    });
  });

  test('debate form with filled values', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    await page.fill('#case-text', 'Should AI be regulated by governments?');
    await page.fill('#max-rounds', '5');
    await page.fill('#consensus-threshold', '0.9');
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('debate-filled.png', {
      maxDiffPixels: 500,
    });
  });

  test('debate pending status card', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create a debate
    await page.fill('#case-text', 'Visual regression test debate');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(300);

    // Mask the debate ID (UUID changes every run)
    await expect(page).toHaveScreenshot('debate-pending.png', {
      maxDiffPixels: 500,
      mask: [page.locator('code')],
    });
  });

  test('debate completed status card', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'Completed debate visual test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(300);

    // Mask the debate ID (UUID changes every run)
    await expect(page).toHaveScreenshot('debate-completed.png', {
      maxDiffPixels: 500,
      mask: [page.locator('code')],
    });
  });
});
