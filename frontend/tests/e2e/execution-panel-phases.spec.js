/**
 * E2E — ExecutionPanel Phases Tab
 *
 * Verifies the workflow-observability phases history is reachable and
 * interactive from the workflow-execution view (the Blueprint canvas
 * reuse of the same component is exercised by `workflow.spec.js`).
 *
 * The component under test is `ExecutionPanel`, mounted by
 * `WorkflowExecutionView` when the route `#/execution/{sessionId}`
 * is visited.  We inject the `sessionId` via the URL (no real
 * workflow run required) and mock all backend endpoints the panel
 * touches:
 *
 *   - `GET  /api/v1/workflow-exec/{sid}/phase-snapshots`
 *   - `GET  /api/v1/workflow-exec/{sid}/phase-snapshots/{nodeId}`
 *   - `GET  /api/v1/workflow-exec/{sid}/stream`  (SSE — closed empty)
 *
 * Asserts (per `plans/phase5-workflow-observability-ux.md` step 13):
 *
 *   1. The 3-tab strip renders (Output / Current State / Phases).
 *   2. The Phases tab shows 3 rows (the 3 mock fixtures).
 *   3. Expanding row 1 calls the detail endpoint and shows the JSON.
 *   4. A 404 on detail gracefully renders the 'Snapshot not found' error.
 *
 * Requires: backend + frontend running (see `playwright.config.js`
 * `webServer`).  Network endpoints are mocked with `page.route`, so
 * no real workflow execution is needed.
 *
 * @see plans/phase5-workflow-observability-ux.md  (P5.3 + PR-3)
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from './helpers.js';

const SID = 'wf-sess-e2e-phases';
const FIXTURE_LIST = [
  {
    node_id: 'node-start',
    round: null,
    state_size: 128,
    created_at: '2026-06-14T03:00:00.000Z',
  },
  {
    node_id: 'node-gate-quality',
    round: 1,
    state_size: 1024,
    created_at: '2026-06-14T03:00:05.000Z',
  },
  {
    node_id: 'node-finalize',
    round: 1,
    state_size: 2048,
    created_at: '2026-06-14T03:00:10.000Z',
  },
];

const FIXTURE_DETAIL = {
  node_id: 'node-start',
  round: null,
  state_size: 128,
  created_at: '2026-06-14T03:00:00.000Z',
  state: { foo: 'bar', count: 42, nested: { ok: true } },
};

/**
 * Register the route mocks for a given test.  `mode` is:
 *  - 'ok'    : detail returns FIXTURE_DETAIL (default)
 *  - '404'   : detail returns 404 (snapshot absent)
 */
async function mockWorkflowApi(page, { mode = 'ok' } = {}) {
  // 1. List endpoint
  await page.route(
    `**/api/v1/workflow-exec/${SID}/phase-snapshots`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(FIXTURE_LIST),
      });
    },
  );

  // 2. Detail endpoint (one route per node so the test can drive each)
  for (const snap of FIXTURE_LIST) {
    await page.route(
      `**/api/v1/workflow-exec/${SID}/phase-snapshots/${encodeURIComponent(snap.node_id)}`,
      async (route) => {
        if (mode === '404') {
          await route.fulfill({
            status: 404,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'snapshot not found' }),
          });
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...FIXTURE_DETAIL,
            node_id: snap.node_id,
            state_size: snap.state_size,
            created_at: snap.created_at,
            round: snap.round,
          }),
        });
      },
    );
  }

  // 3. SSE stream — return a 200 with an empty body that the
  //    EventSource will treat as "no events".  We avoid leaving the
  //    connection hanging so the panel doesn't keep reconnecting.
  await page.route(
    `**/api/v1/workflow-exec/${SID}/stream`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: '',
      });
    },
  );
}

test.describe('ExecutionPanel — Phases tab (P5.3)', () => {
  test('mounts the panel and renders the 3-tab strip', async ({ page }) => {
    await waitForAppLoad(page);
    await mockWorkflowApi(page);

    // The WorkflowExecutionView accepts sessionId via route param.
    await page.goto(`/?lang=en#/execution/${SID}`);
    await expect(page.locator('[data-testid="execution-panel"]')).toBeVisible({
      timeout: 10000,
    });

    // The tab strip should be present with all three tabs.
    const tablist = page.getByRole('tablist', { name: 'Execution panel views' });
    await expect(tablist).toBeVisible();

    const outputTab = page.locator('[data-testid="exec-tab-log"]');
    const stateTab = page.locator('[data-testid="exec-tab-state"]');
    const phasesTab = page.locator('[data-testid="exec-tab-phases"]');
    await expect(outputTab).toBeVisible();
    await expect(stateTab).toBeVisible();
    await expect(phasesTab).toBeVisible();

    // Output tab is the default
    await expect(outputTab).toHaveAttribute('aria-selected', 'true');
  });

  test('Phases tab shows 3 rows from the mocked list endpoint', async ({ page }) => {
    await waitForAppLoad(page);
    await mockWorkflowApi(page);

    await page.goto(`/?lang=en#/execution/${SID}`);
    await expect(page.locator('[data-testid="execution-panel"]')).toBeVisible({
      timeout: 10000,
    });

    // Switch to the Phases tab
    await page.locator('[data-testid="exec-tab-phases"]').click();
    await expect(
      page.locator('[data-testid="exec-tabpanel-phases"]'),
    ).toBeVisible();

    // Three rows should render, one per fixture
    const rows = page.locator('[data-testid="phase-row"]');
    await expect(rows).toHaveCount(3, { timeout: 5000 });

    // Row 0 carries the first node id
    await expect(rows.nth(0)).toHaveAttribute('data-node-id', FIXTURE_LIST[0].node_id);
    await expect(rows.nth(1)).toHaveAttribute('data-node-id', FIXTURE_LIST[1].node_id);
    await expect(rows.nth(2)).toHaveAttribute('data-node-id', FIXTURE_LIST[2].node_id);

    // The list's `aria-label` documents the intent for screen readers
    await expect(
      page.locator('[aria-label="Phase snapshots in execution order"]'),
    ).toBeVisible();
  });

  test('expanding row 1 fetches and shows the JSON state', async ({ page }) => {
    await waitForAppLoad(page);
    await mockWorkflowApi(page);

    await page.goto(`/?lang=en#/execution/${SID}`);
    await expect(page.locator('[data-testid="execution-panel"]')).toBeVisible({
      timeout: 10000,
    });
    await page.locator('[data-testid="exec-tab-phases"]').click();
    await expect(page.locator('[data-testid="phase-row"]')).toHaveCount(3, {
      timeout: 5000,
    });

    // Expand the first row.
    const firstRow = page.locator('[data-testid="phase-row"]').first();
    const firstHeader = firstRow.locator('button.phase-header');
    await expect(firstHeader).toHaveAttribute('aria-expanded', 'false');
    await firstHeader.click();
    await expect(firstHeader).toHaveAttribute('aria-expanded', 'true');

    // The detail panel renders the JSON in a <pre> with the expected
    // content.  We assert on a unique substring to verify the
    // fixture reached the DOM.
    const detail = firstRow.locator('[data-testid="phase-detail"]');
    await expect(detail).toBeVisible();
    await expect(detail.locator('pre.phase-state')).toContainText('"foo": "bar"');
    await expect(detail.locator('pre.phase-state')).toContainText('"count": 42');
  });

  test('a 404 on the detail endpoint renders a graceful error', async ({ page }) => {
    await waitForAppLoad(page);
    await mockWorkflowApi(page, { mode: '404' });

    await page.goto(`/?lang=en#/execution/${SID}`);
    await expect(page.locator('[data-testid="execution-panel"]')).toBeVisible({
      timeout: 10000,
    });
    await page.locator('[data-testid="exec-tab-phases"]').click();
    await expect(page.locator('[data-testid="phase-row"]')).toHaveCount(3, {
      timeout: 5000,
    });

    // Expand any row — all detail calls will 404 in this mode.
    const firstHeader = page
      .locator('[data-testid="phase-row"]')
      .first()
      .locator('button.phase-header');
    await firstHeader.click();

    // The widget should show its 'Snapshot not found' error instead
    // of crashing.  role=alert is set on the error message.
    const errorAlert = page
      .locator('[data-testid="phase-row"]')
      .first()
      .locator('[role="alert"]');
    await expect(errorAlert).toBeVisible({ timeout: 5000 });
    await expect(errorAlert).toContainText('not found');
  });
});
