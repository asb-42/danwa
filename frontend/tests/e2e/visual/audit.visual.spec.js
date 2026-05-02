/**
 * Visual regression tests for Audit view.
 * Compares screenshots against baseline snapshots.
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad, createDebateViaAPI, startDebateViaAPI } from '../helpers.js';

test.describe('Audit — Visual Regression', () => {
  /** Navigate to the Audit Trail view via sidebar */
  async function goToAudit(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Audit Trail")');
  }

  test('audit empty state', async ({ page }) => {
    await waitForAppLoad(page);
    await goToAudit(page);
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('audit-empty.png', {
      maxDiffPixels: 500,
    });
  });

  test('audit table with data', async ({ page, request }) => {
    // Create and start a debate to generate audit events
    const debate = await createDebateViaAPI(request, 'Audit visual test');
    await startDebateViaAPI(request, debate.debate_id);

    await waitForAppLoad(page);
    await goToAudit(page);

    // Enter debate ID and load events
    await page.fill('#debate-id', debate.debate_id);
    await page.click('button:has-text("Load Events")');
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(300);

    // Mask the debate ID input (UUID changes every run) and timestamp cells
    await expect(page).toHaveScreenshot('audit-with-data.png', {
      maxDiffPixels: 500,
      mask: [
        page.locator('#debate-id'),
        page.locator('td.text-xs.font-mono'),
      ],
    });
  });
});
