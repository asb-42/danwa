import { test, expect } from '@playwright/test';
import { waitForAppLoad } from './helpers.js';

test.describe('Configuration View', () => {
  /** Navigate to the Config view via sidebar */
  async function goToConfig(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Config")');
  }

  test('config form fields are rendered', async ({ page }) => {
    await waitForAppLoad(page);
    await goToConfig(page);

    // Form fields should be present
    await expect(page.locator('#cfg-rounds')).toBeVisible();
    await expect(page.locator('#cfg-threshold')).toBeVisible();
    await expect(page.locator('#cfg-llm')).toBeVisible();
    await expect(page.locator('#cfg-agent')).toBeVisible();
    await expect(page.locator('button:has-text("Save Configuration")')).toBeVisible();
  });

  test('save configuration shows confirmation', async ({ page }) => {
    await waitForAppLoad(page);
    await goToConfig(page);

    // Modify a field
    await page.fill('#cfg-rounds', '5');

    // Save
    await page.click('button:has-text("Save Configuration")');

    // Should show success message
    await expect(page.locator('text=Configuration saved')).toBeVisible();
  });

  test('placeholder sections are visible', async ({ page }) => {
    await waitForAppLoad(page);
    await goToConfig(page);

    // Placeholder sections
    await expect(page.locator('text=LLM Profiles')).toBeVisible();
    await expect(page.locator('text=Agent Profiles')).toBeVisible();
    await expect(page.locator('text=Prompt Variants')).toBeVisible();
  });
});
