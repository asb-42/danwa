/**
 * API Contract Tests — validate that FastAPI responses match Zod schemas.
 * Prevents frontend breakage from backend API changes.
 */

import { test, expect } from '@playwright/test';
import {
  HealthResponseSchema,
  DebateResponseSchema,
  DebateStatusSchema,
  AuditEventSchema,
  ErrorResponseSchema,
} from './schemas.js';

const API_BASE = 'http://localhost:8000';

test.describe('API Contract Tests', () => {
  // -----------------------------------------------------------------------
  // Health
  // -----------------------------------------------------------------------

  test('GET /health matches HealthResponseSchema', async ({ request }) => {
    const response = await request.get(`${API_BASE}/health`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    const result = HealthResponseSchema.safeParse(data);
    expect(result.success).toBeTruthy();
    if (!result.success) {
      console.error('Health schema errors:', result.error.issues);
    }
  });

  // -----------------------------------------------------------------------
  // Debate — Create
  // -----------------------------------------------------------------------

  test('POST /api/v1/debate matches DebateResponseSchema', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/v1/debate`, {
      data: {
        case: { text: 'Contract test case' },
        agent_profile: [
          { role: 'strategist', llm_profile: 'default', temperature: 0.7 },
          { role: 'critic', llm_profile: 'default', temperature: 0.5 },
        ],
        max_rounds: 2,
        consensus_threshold: 0.8,
        enable_fact_check: false,
        enable_memory: false,
      },
    });
    expect(response.status()).toBe(201);

    const data = await response.json();
    const result = DebateResponseSchema.safeParse(data);
    expect(result.success).toBeTruthy();
    if (!result.success) {
      console.error('DebateResponse schema errors:', result.error.issues);
    }
  });

  // -----------------------------------------------------------------------
  // Debate — Get Status
  // -----------------------------------------------------------------------

  test('GET /api/v1/debate/{id} matches DebateStatusSchema', async ({ request }) => {
    // Create a debate first
    const createRes = await request.post(`${API_BASE}/api/v1/debate`, {
      data: {
        case: { text: 'Status schema test' },
        max_rounds: 2,
        consensus_threshold: 0.8,
      },
    });
    const created = await createRes.json();

    // Get status
    const response = await request.get(`${API_BASE}/api/v1/debate/${created.debate_id}`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    const result = DebateStatusSchema.safeParse(data);
    expect(result.success).toBeTruthy();
    if (!result.success) {
      console.error('DebateStatus schema errors:', result.error.issues);
    }
  });

  // -----------------------------------------------------------------------
  // Debate — Start (returns DebateStatusSchema)
  // -----------------------------------------------------------------------

  test('POST /api/v1/debate/{id}/start matches DebateStatusSchema', async ({ request }) => {
    // Create a debate
    const createRes = await request.post(`${API_BASE}/api/v1/debate`, {
      data: {
        case: { text: 'Start schema test' },
        max_rounds: 2,
        consensus_threshold: 0.8,
      },
    });
    const created = await createRes.json();

    // Start it
    const response = await request.post(`${API_BASE}/api/v1/debate/${created.debate_id}/start`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    const result = DebateStatusSchema.safeParse(data);
    expect(result.success).toBeTruthy();
    if (!result.success) {
      console.error('Start response schema errors:', result.error.issues);
    }

    // Verify it completed
    expect(data.status).toBe('completed');
    expect(data.rounds.length).toBeGreaterThan(0);
    expect(data.consensus_score).not.toBeNull();
  });

  // -----------------------------------------------------------------------
  // Audit — Events
  // -----------------------------------------------------------------------

  test('GET /api/v1/audit/{id} matches AuditEventSchema[]', async ({ request }) => {
    // Create and start a debate to generate audit events
    const createRes = await request.post(`${API_BASE}/api/v1/debate`, {
      data: {
        case: { text: 'Audit schema test' },
        max_rounds: 2,
        consensus_threshold: 0.8,
      },
    });
    const created = await createRes.json();

    await request.post(`${API_BASE}/api/v1/debate/${created.debate_id}/start`);

    // Get audit events
    const response = await request.get(`${API_BASE}/api/v1/audit/${created.debate_id}`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBeGreaterThan(0);

    // Validate each event
    for (const event of data) {
      const result = AuditEventSchema.safeParse(event);
      expect(result.success).toBeTruthy();
      if (!result.success) {
        console.error('AuditEvent schema errors:', result.error.issues, 'Event:', event);
      }
    }
  });

  test('GET /api/v1/audit/{id} returns empty array for unknown debate', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/audit/00000000-0000-0000-0000-000000000000`);
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBe(0);
  });

  // -----------------------------------------------------------------------
  // Error responses
  // -----------------------------------------------------------------------

  test('GET /api/v1/debate/invalid-id matches ErrorResponseSchema', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/debate/nonexistent-id`);
    expect(response.status()).toBe(404);

    const data = await response.json();
    const result = ErrorResponseSchema.safeParse(data);
    expect(result.success).toBeTruthy();
    if (!result.success) {
      console.error('ErrorResponse schema errors:', result.error.issues);
    }
  });

  test('POST /api/v1/debate with empty case returns 422', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/v1/debate`, {
      data: {
        case: { text: '' },
      },
    });
    expect(response.status()).toBe(422);

    const data = await response.json();
    // FastAPI validation errors have 'detail' array
    expect(data.detail).toBeDefined();
  });

  test('POST /api/v1/debate/{id}/start on already started debate returns 409', async ({ request }) => {
    // Create and start a debate
    const createRes = await request.post(`${API_BASE}/api/v1/debate`, {
      data: {
        case: { text: 'Double start test' },
        max_rounds: 1,
        consensus_threshold: 0.8,
      },
    });
    const created = await createRes.json();
    await request.post(`${API_BASE}/api/v1/debate/${created.debate_id}/start`);

    // Try to start again
    const response = await request.post(`${API_BASE}/api/v1/debate/${created.debate_id}/start`);
    expect(response.status()).toBe(409);

    const data = await response.json();
    const result = ErrorResponseSchema.safeParse(data);
    expect(result.success).toBeTruthy();
  });
});
