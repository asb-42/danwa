/**
 * Shared test helpers for E2E tests.
 */

const API_BASE = 'http://localhost:8000';

/**
 * Create a debate via the API and return the response.
 */
export async function createDebateViaAPI(request, caseText = 'Test case', options = {}) {
  const response = await request.post(`${API_BASE}/api/v1/debate`, {
    data: {
      case: { text: caseText },
      agent_profile: [
        { role: 'strategist', llm_profile: 'default', temperature: 0.7 },
        { role: 'critic', llm_profile: 'default', temperature: 0.5 },
      ],
      max_rounds: options.max_rounds || 2,
      consensus_threshold: options.consensus_threshold || 0.8,
      enable_fact_check: false,
      enable_memory: false,
    },
  });
  return response.json();
}

/**
 * Start a debate via the API and return the response.
 */
export async function startDebateViaAPI(request, debateId) {
  const response = await request.post(`${API_BASE}/api/v1/debate/${debateId}/start`);
  return response.json();
}

/**
 * Wait for the frontend to be fully loaded (Svelte app mounted).
 */
export async function waitForAppLoad(page) {
  // Navigate with English locale so existing tests match English UI text.
  // i18n tests use their own fixture with explicit locale control.
  await page.goto('/?lang=en');
  // Wait for the Svelte app to mount and render the sidebar
  await page.waitForSelector('nav[aria-label="Main navigation"]', { timeout: 10000 });
  // Wait for i18n to finish loading English translations
  await page.waitForFunction(() => window.__locale === 'en', { timeout: 5000 });
}
