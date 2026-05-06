/**
 * E2E Tests — Workflow Visualization
 *
 * Tests that the workflow graph is visible during and after a debate,
 * and that the OOB input panel appears when a debate is running.
 *
 * Requires: backend + frontend running (see helpers.js API_BASE).
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad, createDebateViaAPI, startDebateViaAPI } from './helpers.js';

test.describe('Workflow Visualization', () => {
  /** Navigate to the Debate view via sidebar */
  async function goToDebate(page) {
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
  }

  test('workflow graph container appears after debate completes', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'Workflow visualization E2E test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');

    // Wait for completion
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 30000 });

    // The workflow graph container should be visible
    // WorkflowGraph.svelte renders a .workflow-graph-container div
    await expect(page.locator('.workflow-graph-container')).toBeVisible({ timeout: 5000 });
  });

  test('workflow canvas renders with Svelte Flow viewport', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'Canvas rendering test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');

    // Wait for completion
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 30000 });

    // Svelte Flow renders a .svelte-flow container
    await expect(page.locator('.svelte-flow')).toBeVisible({ timeout: 5000 });
  });

  test('workflow graph shows agent nodes after debate', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'Agent nodes test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');

    // Wait for completion
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 30000 });

    // Wait for workflow graph to appear
    await expect(page.locator('.svelte-flow')).toBeVisible({ timeout: 5000 });

    // Svelte Flow should have rendered nodes (the .svelte-flow__node elements)
    // At minimum, we should have the input node and some agent nodes
    const nodes = page.locator('.svelte-flow__node');
    await expect(nodes.first()).toBeVisible({ timeout: 5000 });
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThan(0);
  });

  test('workflow graph does not appear for pending debate', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create a debate but don't start it
    await page.fill('#case-text', 'Pending debate test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });

    // Workflow graph should NOT be visible for pending debates
    // (the {#if} guard in DebateView only shows it for running/completed/failed)
    const graphContainer = page.locator('.workflow-graph-container');
    await expect(graphContainer).not.toBeVisible();
  });

  test('OOB input panel is not visible for completed debate', async ({ page }) => {
    await waitForAppLoad(page);
    await goToDebate(page);

    // Create and start a debate
    await page.fill('#case-text', 'OOB panel visibility test');
    await page.click('button[type="submit"]:has-text("Create Debate")');
    await expect(page.locator('text=Current Debate')).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("Start Debate")');

    // Wait for completion
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 30000 });

    // OOB panel should NOT be visible after completion (isRunning is false)
    // The OOB panel has a textarea with the inject-context placeholder
    const oobPanel = page.locator('textarea[placeholder*="context"], textarea[placeholder*="Kontext"]');
    await expect(oobPanel).not.toBeVisible();
  });
});
