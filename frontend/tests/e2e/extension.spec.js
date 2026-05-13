import { test, expect } from '@playwright/test';
import { waitForAppLoad, createDebateViaAPI, startDebateViaAPI } from './helpers.js';

test.describe('Extension / Extra Rounds', () => {
  /** Navigate to the Debate view via sidebar */
  async function goToDebate(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
  }

  test('create debate form shows extension checkbox', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Extension checkbox should be visible
    await expect(page.locator('text=Allow additional rounds')).toBeVisible();
  });

  test('create debate with extension enabled stores the flag', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Fill in the form
    await page.fill('#case-text', 'Should AI be regulated by governments?');
    await page.fill('#max-rounds', '3');
    await page.fill('#consensus-threshold', '0.9');

    // Enable extension checkbox
    await page.check('input:has-label("Allow additional rounds")');

    // Submit
    await page.click('button[type="submit"]:has-text("Create Debate")');

    // Should show the current debate card
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
  });

  test('debate with extension enabled shows extension panel when consensus not reached', async ({ page, request }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create a debate with extension enabled via API (faster & more reliable)
    const debate = await createDebateViaAPI(request, 'Test extension debate', {
      max_rounds: 2,
      consensus_threshold: 0.99, // High threshold ensures no consensus
      enable_extra_rounds: true,
    });

    const debateId = debate.debate_id;

    // Start the debate
    await startDebateViaAPI(request, debateId);

    // Reload the page to pick up the running debate
    await page.reload();
    await waitForAppLoad(page);

    // Wait for the debate to be running
    await expect(page.locator('text=running')).toBeVisible({ timeout: 15000 });

    // Wait for extension request panel to appear
    // (consensus not reached + extra rounds enabled triggers the extension request)
    await expect(page.locator('text=Extension requested')).toBeVisible({ timeout: 20000 });

    // Verify extension panel shows consensus and threshold info
    await expect(page.locator('text=Current consensus')).toBeVisible();
    await expect(page.locator('text=Threshold')).toBeVisible();
  });

  test('extension panel shows grant and deny buttons', async ({ page, request }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate with extension enabled and high threshold
    const debate = await createDebateViaAPI(request, 'Extension buttons test', {
      max_rounds: 2,
      consensus_threshold: 0.99,
      enable_extra_rounds: true,
    });

    const debateId = debate.debate_id;
    await startDebateViaAPI(request, debateId);

    await page.reload();
    await waitForAppLoad(page);

    // Wait for running state
    await expect(page.locator('text=running')).toBeVisible({ timeout: 15000 });

    // Wait for extension panel
    await expect(page.locator('text=Extension requested')).toBeVisible({ timeout: 20000 });

    // Both grant and deny buttons should be visible
    await expect(page.locator('text=Grant extension')).toBeVisible();
    await expect(page.locator('text=Deny extension')).toBeVisible();
  });

  test('debate without extension enabled does not show extension panel', async ({ page, request }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create a debate WITHOUT extension enabled
    const debate = await createDebateViaAPI(request, 'No extension debate', {
      max_rounds: 2,
      consensus_threshold: 0.99,
      enable_extra_rounds: false,
    });

    const debateId = debate.debate_id;
    await startDebateViaAPI(request, debateId);

    await page.reload();
    await waitForAppLoad(page);

    // Wait for running state
    await expect(page.locator('text=running')).toBeVisible({ timeout: 15000 });

    // Extension panel should NOT appear
    await expect(page.locator('text=Extension requested')).not.toBeVisible({ timeout: 20000 });
  });
});
