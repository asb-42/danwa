import { test, expect } from '@playwright/test';
import { waitForAppLoad, createDebateViaAPI, startDebateViaAPI } from './helpers.js';

test.describe('Audit Trail View', () => {
  /** Navigate to the Audit Trail view via sidebar */
  async function goToAudit(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Audit Trail")');
  }

  test('audit view renders search form', async ({ page }) => {
    await waitForAppLoad(page);
    await goToAudit(page);

    // Search form should be present
    await expect(page.locator('#debate-id')).toBeVisible();
    await expect(page.locator('button:has-text("Load Events")')).toBeVisible();
  });

  test('audit view shows empty state when no events', async ({ page }) => {
    await waitForAppLoad(page);
    await goToAudit(page);

    // Should show empty state message
    await expect(page.locator('text=No audit events found')).toBeVisible();
  });

  test('audit view loads events after debate completion', async ({ page, request }) => {
    // Create and start a debate via API to generate audit events
    const debate = await createDebateViaAPI(request, 'Audit test case');
    expect(debate.debate_id).toBeTruthy();
    await startDebateViaAPI(request, debate.debate_id);

    await waitForAppLoad(page);
    await goToAudit(page);

    // Enter the debate ID and load events
    await page.fill('#debate-id', debate.debate_id);
    await page.click('button:has-text("Load Events")');

    // Should show audit events in the table
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });
    // Should have at least one row with agent badge
    await expect(page.locator('.bg-purple-100, .dark\\:bg-purple-900').first()).toBeVisible();
  });
});
