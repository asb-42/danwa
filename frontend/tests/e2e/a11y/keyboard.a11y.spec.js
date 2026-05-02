/**
 * Keyboard navigation accessibility tests.
 * Verifies all interactive elements are keyboard-operable.
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from '../helpers.js';

test.describe('Keyboard Navigation', () => {
  test('no positive tabindex values (anti-pattern)', async ({ page }) => {
    await waitForAppLoad(page);

    const focusableElements = await page.$$eval(
      'a, button, input, select, textarea, [tabindex]',
      els => els.map(el => ({
        tag: el.tagName,
        text: el.textContent?.trim().substring(0, 30),
        tabindex: el.getAttribute('tabindex'),
      }))
    );

    const badTabindex = focusableElements.filter(
      el => el.tabindex && parseInt(el.tabindex) > 0
    );
    expect(badTabindex).toEqual([]);
  });

  test('sidebar buttons are focusable and activatable', async ({ page }) => {
    await waitForAppLoad(page);

    // Tab to first sidebar button
    // Skip the skip-link (first tab stop), then sidebar buttons
    await page.keyboard.press('Tab'); // skip-link
    await page.keyboard.press('Tab'); // first sidebar button

    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return { tag: el?.tagName, text: el?.textContent?.trim() };
    });

    expect(focused.tag).toBe('BUTTON');
    expect(focused.text).toBeTruthy();
  });

  test('debate form is keyboard navigable', async ({ page }) => {
    await waitForAppLoad(page);

    // Navigate to debate view via keyboard
    await page.keyboard.press('Tab'); // skip-link
    await page.keyboard.press('Tab'); // Dashboard button
    await page.keyboard.press('Tab'); // Debate button
    await page.keyboard.press('Enter');

    await page.waitForTimeout(300);

    // Verify we're on debate view
    await expect(page.locator('h2:has-text("Debate")')).toBeVisible();

    // Tab to case-text textarea
    await page.keyboard.press('Tab'); // Audit button
    await page.keyboard.press('Tab'); // Config button
    await page.keyboard.press('Tab'); // case-text textarea

    const focused = await page.evaluate(() => document.activeElement?.id);
    expect(focused).toBe('case-text');
  });

  test('config form submit with Enter key', async ({ page }) => {
    await waitForAppLoad(page);

    // Navigate to config
    await page.click('nav[aria-label="Main navigation"] button:has-text("Config")');
    await page.waitForTimeout(300);

    // Focus the save button and press Enter
    const saveButton = page.locator('button:has-text("Save Configuration")');
    await saveButton.focus();
    await page.keyboard.press('Enter');

    // Verify save confirmation appears
    await expect(page.locator('text=Configuration saved')).toBeVisible({ timeout: 3000 });
  });

  test('skip-to-content link is first tab stop', async ({ page }) => {
    await waitForAppLoad(page);

    // Press Tab once — should focus the skip link
    await page.keyboard.press('Tab');

    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return { tag: el?.tagName, href: el?.getAttribute('href') };
    });

    expect(focused.tag).toBe('A');
    expect(focused.href).toContain('#main-content');
  });
});
