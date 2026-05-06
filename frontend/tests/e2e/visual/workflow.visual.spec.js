/**
 * Visual regression tests for Workflow Visualization.
 * Compares screenshots against baseline snapshots.
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from '../helpers.js';

test.describe('Workflow — Visual Regression', () => {
  /** Navigate to the Debate view via sidebar */
  async function goToDebate(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
  }

  test('workflow graph after completed debate', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'Workflow visual regression test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 30000 });

    // Wait for workflow graph to render
    await expect(page.locator('.svelte-flow')).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(500); // Allow ELK layout to settle

    // Screenshot the workflow graph area
    const workflowContainer = page.locator('.workflow-graph-container');
    await expect(workflowContainer).toHaveScreenshot('workflow-graph-completed.png', {
      maxDiffPixels: 1000,
    });
  });

  test('workflow graph with node detail panel', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'Node detail visual test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 30000 });

    // Wait for workflow graph
    await expect(page.locator('.svelte-flow')).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(500);

    // Click on a node to open the detail panel
    const firstNode = page.locator('.svelte-flow__node').first();
    if (await firstNode.isVisible()) {
      await firstNode.click();
      await page.waitForTimeout(300);
    }

    // Screenshot with detail panel open
    const workflowContainer = page.locator('.workflow-graph-container');
    await expect(workflowContainer).toHaveScreenshot('workflow-graph-with-detail.png', {
      maxDiffPixels: 1000,
    });
  });
});
