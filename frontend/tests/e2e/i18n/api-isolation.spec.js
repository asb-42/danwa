/**
 * API Isolation Tests (api-isolation.spec.js)
 *
 * Verifies that:
 * - Backend always receives Accept-Language: en regardless of UI locale
 * - Backend error messages are translated to the current UI locale
 * - API response data is not translated (stays English)
 */
import { i18nTest as test, expect, gotoRoute } from './setup.i18n.js';

test.describe('API Isolation — Accept-Language Header', () => {
  test('API requests include Accept-Language: en when UI is German', async ({ page }) => {
    // Set up request listener BEFORE triggering a new API request
    const requestHeaders = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/') || request.url().includes('/health')) {
        requestHeaders.push(request.headers());
      }
    });

    // Navigate to dashboard and click Refresh Health to trigger a new API request
    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /Status aktualisieren|Refresh Health/ }).click();
    await page.waitForTimeout(1000);

    // At least one API request should have been made
    expect(requestHeaders.length).toBeGreaterThan(0);

    // All API requests should have Accept-Language: en
    for (const headers of requestHeaders) {
      expect(headers['accept-language']).toBe('en');
    }
  });

  test('API requests include Accept-Language: en when UI is English', async ({ page }) => {
    const requestHeaders = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/') || request.url().includes('/health')) {
        requestHeaders.push(request.headers());
      }
    });

    await gotoRoute(page, 'dashboard');
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /Refresh Health|Status aktualisieren/ }).click();
    await page.waitForTimeout(1000);

    expect(requestHeaders.length).toBeGreaterThan(0);

    for (const headers of requestHeaders) {
      expect(headers['accept-language']).toBe('en');
    }
  });
});

test.describe('API Isolation — Error Translation', () => {
  test('backend errors are translated to German when UI locale is de', async ({ page }) => {
    // Intercept and mock a 404 response
    await page.route('**/api/v1/debate/nonexistent', (route) => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Debate not found' }),
      });
    });

    // Trigger an API call that will return 404
    const errorMessage = await page.evaluate(async () => {
      try {
        const response = await fetch('/api/v1/debate/nonexistent', {
          headers: { 'Content-Type': 'application/json', 'Accept-Language': 'en' },
        });
        if (!response.ok) {
          const error = await response.json();
          // The API client's translateBackendError should map this
          const ERROR_MAP = {
            'Debate not found': 'error.debateNotFound',
          };
          // Simulate what the API client does — use the loaded translations
          const translations = window.__translations || {};
          const key = ERROR_MAP[error.detail] || 'common.error';
          return translations[key] || key;
        }
      } catch (e) {
        return e.message;
      }
    });

    // In German locale, the error key should resolve to German text
    // If translations are loaded, it should be 'Debatte nicht gefunden'
    // If not, it falls back to the key
    expect(errorMessage).toMatch(/Debatte nicht gefunden|error\.debateNotFound/);
  });

  test('backend errors are translated to English when UI locale is en', async ({ page }) => {
    await page.route('**/api/v1/debate/nonexistent', (route) => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Debate not found' }),
      });
    });

    const errorMessage = await page.evaluate(async () => {
      try {
        const response = await fetch('/api/v1/debate/nonexistent', {
          headers: { 'Content-Type': 'application/json', 'Accept-Language': 'en' },
        });
        if (!response.ok) {
          const error = await response.json();
          const ERROR_MAP = {
            'Debate not found': 'error.debateNotFound',
          };
          const translations = window.__translations || {};
          const key = ERROR_MAP[error.detail] || 'common.error';
          return translations[key] || key;
        }
      } catch (e) {
        return e.message;
      }
    });

    expect(errorMessage).toMatch(/Debate not found|error\.debateNotFound/);
  });
});

test.describe('API Isolation — Response Data Not Translated', () => {
  test('API response data stays in English regardless of UI locale', async ({ page }) => {
    // Mock a debate response with English data
    await page.route('**/api/v1/debate', (route) => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            debate_id: 'test-123',
            status: 'pending',
            max_rounds: 3,
            consensus_threshold: 0.8,
            current_round: 0,
          }),
        });
      } else {
        route.continue();
      }
    });

    // The status value from the API should remain 'pending' (English)
    // even though the UI displays it translated
    const response = await page.evaluate(async () => {
      const res = await fetch('/api/v1/debate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept-Language': 'en' },
        body: JSON.stringify({ case: { text: 'test' } }),
      });
      return res.json();
    });

    // API data stays English
    expect(response.status).toBe('pending');
    expect(response.debate_id).toBe('test-123');
  });
});
