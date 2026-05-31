/**
 * Transcript Normalizer — Converts JSON state blobs into readable Markdown
 * for display in the debate execution UI.
 *
 * Called from DebateExecutionDisplay and ExecutionPanel when node content
 * contains structured JSON (transactional drafting output) rather than
 * plain text.
 */

function extractJsonFromText(text) {
  let idx = text.indexOf('{');
  const arrIdx = text.indexOf('[');
  if (arrIdx >= 0 && (idx < 0 || arrIdx < idx)) idx = arrIdx;
  if (idx < 0) return text;
  let depth = 0;
  let inStr = false;
  let escape = false;
  let end = -1;
  for (let i = idx; i < text.length; i++) {
    const ch = text[i];
    if (escape) { escape = false; continue; }
    if (inStr) {
      if (ch === '\\') { escape = true; }
      else if (ch === '"') { inStr = false; }
      continue;
    }
    if (ch === '"') { inStr = true; continue; }
    if (ch === '{' || ch === '[') depth++;
    else if (ch === '}' || ch === ']') {
      depth--;
      if (depth === 0) { end = i + 1; break; }
    }
  }
  if (end < 0) return text;
  return text.slice(idx, end);
}

/**
 * Normalize a single node output's content for display.
 * Tries to parse content as JSON; if it matches known transactional drafting
 * structures (zero_draft, critic_items, build_responses, pragmatist evaluations),
 * converts to Markdown. Otherwise returns the original content unchanged.
 *
 * @param {string} content - Raw content from SSE node.complete event
 * @param {string} role - Agent role (strategist, critic, builder, pragmatist, etc.)
 * @returns {string} Normalized Markdown content
 */
export function normalizeTranscriptContent(content, role) {
  if (!content || typeof content !== 'string') return content || '';

  // Strip markdown code fences (```json ... ``` or ``` ... ```) that LLMs
  // often wrap around JSON responses
  let cleaned = content.trim();
  const fenceMatch = cleaned.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenceMatch) {
    cleaned = fenceMatch[1].trim();
  }

  let parsed;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    // Try to extract JSON from surrounding text
    const extracted = extractJsonFromText(cleaned);
    if (extracted !== cleaned) {
      try {
        parsed = JSON.parse(extracted);
      } catch {
        return content;
      }
    } else {
      return content;
    }
  }

  if (parsed === null || parsed === undefined) return content;
  if (typeof parsed === 'string') return parsed;

  const r = role ? role.toLowerCase() : '';

  // Strategist: zero_draft key
  if (r === 'strategist' && parsed.zero_draft) {
    return formatZeroDraft(parsed.zero_draft);
  }

  // Critic: array of critic items with flaw/severity/principle/target
  if (r === 'critic' && Array.isArray(parsed)) {
    const items = parsed.filter(i => i.flaw || i.severity);
    if (items.length > 0) {
      return items.map((item, i) => formatCriticItem(item, i)).join('\n\n---\n\n');
    }
  }

  // Critic: object with critic_items key
  if (r === 'critic' && parsed.critic_items && Array.isArray(parsed.critic_items)) {
    return parsed.critic_items.map((item, i) => formatCriticItem(item, i)).join('\n\n---\n\n');
  }

  // Builder/Optimizer: array of build responses with response_to/option_a/option_b
  if ((r === 'optimizer' || r === 'builder') && Array.isArray(parsed)) {
    const items = parsed.filter(i => i.response_to || i.option_a);
    if (items.length > 0) {
      return items.map((item, i) => formatBuildResponse(item, i)).join('\n\n---\n\n');
    }
  }

  // Builder/Optimizer: object with build_responses key
  if ((r === 'optimizer' || r === 'builder') && parsed.build_responses && Array.isArray(parsed.build_responses)) {
    return parsed.build_responses.map((item, i) => formatBuildResponse(item, i)).join('\n\n---\n\n');
  }

  // Pragmatist: object with evaluations array
  if (r === 'pragmatist' && parsed.evaluations && Array.isArray(parsed.evaluations)) {
    const lines = parsed.evaluations.map((ev, i) => formatPragmatistEvaluation(ev, i));
    if (parsed.reality_score !== undefined) {
      const pct = (parsed.reality_score * 100).toFixed(1);
      lines.push(`\n**Reality Score:** ${pct}%`);
    }
    if (parsed.blocking_concerns && parsed.blocking_concerns.length > 0) {
      lines.push('\n**Blocking Concerns:**');
      for (const c of parsed.blocking_concerns) {
        lines.push(`- ${c}`);
      }
    }
    return lines.join('\n');
  }

  // Pragmatist: array of evaluations (without wrapper object)
  if (r === 'pragmatist' && Array.isArray(parsed)) {
    const items = parsed.filter(i => i.verdict || i.feasibility !== undefined);
    if (items.length > 0) {
      return items.map((ev, i) => formatPragmatistEvaluation(ev, i)).join('\n\n---\n\n');
    }
  }

  // Unknown structure — return original JSON as-is
  return content;
}

function formatZeroDraft(text) {
  const snippet = text.length > 1000 ? text.slice(0, 1000) + '...' : text;
  return `**Zero-Draft erstellt:**\n\n${snippet}`;
}

function formatCriticItem(item, index) {
  const parts = [
    `**Kritik ${index + 1}** (${item.severity || 'mittel'}): ${item.flaw || item.issue || ''}`,
  ];
  if (item.principle) parts.push(`*Prinzip:* ${item.principle}`);
  if (item.target) parts.push(`*Betrifft:* ${item.target}`);
  if (item.suggestion || item.recommendation) parts.push(`*Vorschlag:* ${item.suggestion || item.recommendation}`);
  return parts.join('\n\n');
}

function formatBuildResponse(item, index) {
  const parts = [
    `**Lösung für ${item.response_to || item.target || `Position ${index + 1}`}**`,
  ];
  if (item.option_a) parts.push(`\n**A (Konservativ):** ${item.option_a}`);
  if (item.option_b) parts.push(`\n**B (Radikal):** ${item.option_b}`);
  if (item.recommendation) parts.push(`\n**Empfohlen:** ${item.recommendation}`);
  if (item.rationale) parts.push(`\n*Begründung:* ${item.rationale}`);
  return parts.join('');
}

function formatPragmatistEvaluation(ev, index) {
  const label = ev.response_to ? `Evaluation für ${ev.response_to}` : `Evaluation ${index + 1}`;
  const parts = [`**${label}**`];
  if (ev.verdict) {
    const icon = ev.verdict === 'accept' ? '✅' : ev.verdict === 'revise' ? '🔄' : '❌';
    parts.push(`${icon} **Verdict:** ${ev.verdict}`);
  }
  if (ev.feasibility !== undefined) {
    const pct = (ev.feasibility * 100).toFixed(1);
    parts.push(`*Machbarkeit:* ${pct}%`);
  }
  if (ev.process_risk) parts.push(`*Prozessrisiko:* ${ev.process_risk}`);
  if (ev.revision_note) parts.push(`*Anmerkung:* ${ev.revision_note}`);
  return parts.join('\n\n');
}
