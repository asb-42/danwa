/**
 * Zod schemas mirroring backend Pydantic models.
 * Used by API contract tests to validate response shapes.
 */

import { z } from 'zod';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const DebateStatusEnum = z.enum(['pending', 'running', 'completed', 'failed']);
export const AgentRoleEnum = z.enum(['strategist', 'critic', 'optimizer', 'moderator']);

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export const HealthResponseSchema = z.object({
  status: z.string(),
  version: z.string(),
});

// ---------------------------------------------------------------------------
// Debate
// ---------------------------------------------------------------------------

export const DebateResponseSchema = z.object({
  debate_id: z.string().uuid(),
  status: DebateStatusEnum,
  created_at: z.string().datetime(),
});

export const AgentOutputSchema = z.object({
  role: AgentRoleEnum,
  content: z.string(),
  tokens_used: z.number().int().min(0),
});

export const RoundDataSchema = z.object({
  round: z.number().int().min(1),
  consensus: z.number().min(0).max(1),
  agent_outputs: z.array(AgentOutputSchema),
});

export const DebateStatusSchema = z.object({
  debate_id: z.string().uuid(),
  status: DebateStatusEnum,
  current_round: z.number().int().min(0),
  max_rounds: z.number().int().min(1),
  consensus_score: z.number().min(0).max(1).nullable(),
  rounds: z.array(RoundDataSchema),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  case_text: z.string().default(''),
  language: z.string().default('de'),
  llm_profile_id: z.string().default(''),
  anomalies: z.array(z.string()).default([]),
});

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export const AuditEventSchema = z.object({
  id: z.string().uuid(),
  debate_id: z.string().uuid(),
  round: z.number().int().min(1),
  agent: z.string(), // stored as plain string from SQLite
  action: z.string(),
  timestamp: z.string(), // ISO datetime string
  input_hash: z.string(),
  output_hash: z.string(),
  llm_model: z.string(),
  tokens_used: z.number().int().min(0),
});

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export const ErrorResponseSchema = z.object({
  detail: z.string(),
});
