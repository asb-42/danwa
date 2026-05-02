import { test, expect } from '@playwright/test';
import { waitForAppLoad } from './helpers.js';

test.describe('Health & Backend Connection', () => {
  test('backend health endpoint returns ok', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.status).toBe('ok');
    expect(data.version).toBeTruthy();
  });

  test('frontend shows backend status indicator', async ({ page }) => {
    await waitForAppLoad(page);
    // The header should show the health status
    const header = page.locator('header');
    await expect(header).toBeVisible();
    // Status text should show "ok" after health check completes
    await expect(page.locator('header')).toContainText('ok');
  });
});
