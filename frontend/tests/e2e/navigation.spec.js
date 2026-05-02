import { test, expect } from '@playwright/test';
import { waitForAppLoad } from './helpers.js';

test.describe('Navigation & Hash Router', () => {
  test('default route shows dashboard', async ({ page }) => {
    await waitForAppLoad(page);
    await expect(page.locator('h2')).toContainText('Dashboard');
  });

  test('sidebar navigation links work', async ({ page }) => {
    await waitForAppLoad(page);

    // Navigate to Debate
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
    await expect(page.locator('h2')).toContainText('Debate');

    // Navigate to Audit Trail
    await page.click('button:has-text("Audit Trail")');
    await expect(page.locator('h2')).toContainText('Audit Trail');

    // Navigate to Config
    await page.click('button:has-text("Config")');
    await expect(page.locator('h2')).toContainText('Configuration');

    // Navigate back to Dashboard
    await page.click('button:has-text("Dashboard")');
    await expect(page.locator('h2')).toContainText('Dashboard');
  });

  test('active sidebar item is highlighted', async ({ page }) => {
    await waitForAppLoad(page);

    // Dashboard should be active by default
    const dashboardBtn = page.locator('nav[aria-label="Main navigation"] button:has-text("Dashboard")');
    await expect(dashboardBtn).toHaveAttribute('aria-current', 'page');

    // Navigate to Debate — Debate should become active
    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
    const debateBtn = page.locator('nav[aria-label="Main navigation"] button:has-text("Debate")');
    await expect(debateBtn).toHaveAttribute('aria-current', 'page');
    // Dashboard should no longer be active
    await expect(dashboardBtn).not.toHaveAttribute('aria-current', 'page');
  });

  test('hash URL updates on navigation', async ({ page }) => {
    await waitForAppLoad(page);

    await page.click('nav[aria-label="Main navigation"] button:has-text("Debate")');
    expect(page.url()).toContain('#/debate');

    await page.click('button:has-text("Audit Trail")');
    expect(page.url()).toContain('#/audit');

    await page.click('button:has-text("Config")');
    expect(page.url()).toContain('#/config');
  });

  test('direct hash URL navigates to correct view', async ({ page }) => {
    await page.goto('/?lang=en#/debate');
    await page.waitForSelector('nav[aria-label="Main navigation"]', { timeout: 10000 });
    await page.waitForFunction(() => window.__locale === 'en', { timeout: 5000 });
    await expect(page.locator('h2')).toContainText('Debate');
  });

  test('unknown hash falls back to dashboard', async ({ page }) => {
    await page.goto('/?lang=en#/nonexistent');
    await page.waitForSelector('nav[aria-label="Main navigation"]', { timeout: 10000 });
    await page.waitForFunction(() => window.__locale === 'en', { timeout: 5000 });
    await expect(page.locator('h2')).toContainText('Dashboard');
  });
});
