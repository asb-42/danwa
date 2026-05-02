import { test, expect } from '@playwright/test';
import { waitForAppLoad, createDebateViaAPI, startDebateViaAPI } from './helpers.js';

test.describe('Debate Flow', () => {
  /** Navigate to the Debate view via sidebar */
  async function goToDebate(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
  }

  test('create debate form is rendered', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Form elements should be present
    await expect(page.locator('#case-text')).toBeVisible();
    await expect(page.locator('#max-rounds')).toBeVisible();
    await expect(page.locator('#consensus-threshold')).toBeVisible();
    await expect(page.locator('button[type="submit"]:has-text("Create Debate")')).toBeVisible();
  });

  test('create debate via form shows status card', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Fill in the form
    await page.fill('#case-text', 'Should AI be regulated by governments?');
    await page.fill('#max-rounds', '2');
    await page.fill('#consensus-threshold', '0.8');

    // Submit
    await page.click('button[type="submit"]:has-text("Create Debate")');

    // Should show the current debate card
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=pending')).toBeVisible();
    await expect(page.locator('button:has-text("Start Debate")')).toBeVisible();
  });

  test('start debate updates status to completed', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create a debate
    await page.fill('#case-text', 'Test debate for E2E');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });

    // Start the debate
    await page.click('button:has-text("Start Debate")');

    // Should eventually show COMPLETED (dummy nodes run instantly)
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 15000 });
  });

  test('empty case text disables submit button', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Submit button should be disabled when textarea is empty
    const submitBtn = page.locator('button[type="submit"]:has-text("Create Debate")');
    await expect(submitBtn).toBeDisabled();

    // Fill whitespace only — button should remain disabled
    await page.fill('#case-text', '   ');
    await expect(submitBtn).toBeDisabled();
  });

  test('debate status shows round and consensus info', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'Round info test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');

    // After completion, should show round info
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Round:')).toBeVisible();
    await expect(page.locator('text=Consensus:')).toBeVisible();
  });
});
