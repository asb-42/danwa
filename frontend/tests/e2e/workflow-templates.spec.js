/**
 * E2E Tests — Workflow Templates
 *
 * Tests the template gallery, instantiation, and save-as-template flows.
 * Requires: backend + frontend running (see helpers.js API_BASE).
 */

import { test, expect } from '@playwright/test';
import { waitForAppLoad } from './helpers.js';

const API_BASE = 'http://localhost:8000';

test.describe('Workflow Templates', () => {
  test('template gallery opens from blueprint canvas', async ({ page }) => {
    await waitForAppLoad(page);

    // Navigate to blueprint canvas
    await page.click('nav[aria-label="Main navigation"] button:has-text("Blueprint")');
    await page.waitForSelector('[data-testid="blueprint-canvas-view"]', { timeout: 10000 });

    // The "New Workflow" button should trigger the template gallery
    // (This test verifies the gallery modal appears)
    const newWorkflowBtn = page.locator('[data-testid="new-workflow-btn"]');
    if (await newWorkflowBtn.isVisible()) {
      await newWorkflowBtn.click();
      await expect(page.locator('.gallery-overlay')).toBeVisible({ timeout: 5000 });
    }
  });

  test('API: system templates are listed after startup', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/workflow-templates`);
    expect(response.ok()).toBeTruthy();
    const templates = await response.json();

    // Should have at least 3 system templates
    const systemTemplates = templates.filter((t) => t.is_system);
    expect(systemTemplates.length).toBeGreaterThanOrEqual(3);

    // Verify specific template IDs
    const ids = templates.map((t) => t.id);
    expect(ids).toContain('tpl-standard-debate');
    expect(ids).toContain('tpl-kantian-analysis');
    expect(ids).toContain('tpl-quick-review');
  });

  test('API: system templates cannot be deleted', async ({ request }) => {
    const response = await request.delete(
      `${API_BASE}/api/v1/workflow-templates/tpl-standard-debate`,
    );
    expect(response.status()).toBe(403);
  });

  test('API: system templates cannot be updated', async ({ request }) => {
    const response = await request.put(
      `${API_BASE}/api/v1/workflow-templates/tpl-standard-debate`,
      {
        data: {
          id: 'tpl-standard-debate',
          name: 'Hacked',
          template_data: { nodes: [], edges: [] },
        },
      },
    );
    expect(response.status()).toBe(403);
  });

  test('API: custom template CRUD roundtrip', async ({ request }) => {
    // Create
    const createResponse = await request.post(`${API_BASE}/api/v1/workflow-templates`, {
      data: {
        id: 'tpl-e2e-test',
        name: 'E2E Test Template',
        description: 'Created by E2E test',
        category: 'custom',
        template_data: {
          nodes: [{ id: 'n1', type: 'wf-input', label: 'Input' }],
          edges: [],
          entry_point: 'n1',
        },
        placeholders: [],
      },
    });
    expect(createResponse.status()).toBe(201);
    const created = await createResponse.json();
    expect(created.is_system).toBe(false);

    // Read
    const getResponse = await request.get(
      `${API_BASE}/api/v1/workflow-templates/tpl-e2e-test`,
    );
    expect(getResponse.ok()).toBeTruthy();

    // Update
    const updateResponse = await request.put(
      `${API_BASE}/api/v1/workflow-templates/tpl-e2e-test`,
      {
        data: {
          ...created,
          name: 'Updated E2E Template',
        },
      },
    );
    expect(updateResponse.ok()).toBeTruthy();
    const updated = await updateResponse.json();
    expect(updated.name).toBe('Updated E2E Template');

    // Delete
    const deleteResponse = await request.delete(
      `${API_BASE}/api/v1/workflow-templates/tpl-e2e-test`,
    );
    expect(deleteResponse.ok()).toBeTruthy();

    // Verify deleted
    const getDeleted = await request.get(
      `${API_BASE}/api/v1/workflow-templates/tpl-e2e-test`,
    );
    expect(getDeleted.status()).toBe(404);
  });

  test('API: instantiation with missing placeholders returns 422', async ({ request }) => {
    const response = await request.post(
      `${API_BASE}/api/v1/workflow-templates/tpl-standard-debate/instantiate`,
      {
        data: {
          placeholder_values: {}, // Missing all required placeholders
        },
      },
    );
    expect(response.status()).toBe(422);
    const detail = await response.json();
    expect(detail.detail.error).toBe('missing_placeholders');
  });

  test('API: instantiation with invalid blueprint ref returns 422', async ({ request }) => {
    const response = await request.post(
      `${API_BASE}/api/v1/workflow-templates/tpl-quick-review/instantiate`,
      {
        data: {
          placeholder_values: {
            reviewer_blueprint_id: 'nonexistent-blueprint',
            reviser_blueprint_id: 'nonexistent-blueprint',
          },
        },
      },
    );
    expect(response.status()).toBe(422);
    const detail = await response.json();
    expect(detail.detail.error).toBe('invalid_blueprint_ref');
  });

  test('API: filter templates by category', async ({ request }) => {
    const response = await request.get(
      `${API_BASE}/api/v1/workflow-templates?category=system`,
    );
    expect(response.ok()).toBeTruthy();
    const templates = await response.json();
    expect(templates.every((t) => t.category === 'system')).toBe(true);
  });
});
