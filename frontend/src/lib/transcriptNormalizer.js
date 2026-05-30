/**
 * Transcript Normalizer — Converts JSON state blobs into readable Markdown
 * for display in the debate execution UI.
 *
 * Called from DebateExecutionDisplay when node content contains
 * structured JSON (transactional drafting output) rather than plain text.
 */

/**
 * Normalize a single node output's content for display.
 * Tries to parse content as JSON; if it matches known transactional drafting
 * structures (zero_draft, critic_items, build_responses), converts to Markdown.
 * Otherwise returns the original content unchanged.
 *
 * @param {string} content - Raw content from SSE node.complete event
 * @param {string} role - Agent role (strategist, critic, optimizer, etc.)
 * @returns {string} Normalized Markdown content
 */
export function normalizeTranscriptContent(content, role) {
  if (!content || typeof content !== 'string') return content || '';

  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch {
    // Not JSON — return as-is
    return content;
  }

  if (parsed === null || parsed === undefined) return content;
  if (typeof parsed === 'string') return parsed;

  // Strategist: zero_draft key
  if (role === 'strategist' && parsed.zero_draft) {
    return formatZeroDraft(parsed.zero_draft);
  }

  // Critic: array of critic items with flaw/severity/principle/target
  if (role === 'critic' && Array.isArray(parsed)) {
    const items = parsed.filter(i => i.flaw || i.severity);
    if (items.length > 0) {
      return items.map((item, i) => formatCriticItem(item, i)).join('\n\n---\n\n');
    }
  }

  // Critic: object with critic_items key
  if (role === 'critic' && parsed.critic_items && Array.isArray(parsed.critic_items)) {
    return parsed.critic_items.map((item, i) => formatCriticItem(item, i)).join('\n\n---\n\n');
  }

  // Builder/Optimizer: array of build responses with response_to/option_a/option_b
  if ((role === 'optimizer' || role === 'builder') && Array.isArray(parsed)) {
    const items = parsed.filter(i => i.response_to || i.option_a);
    if (items.length > 0) {
      return items.map((item, i) => formatBuildResponse(item, i)).join('\n\n---\n\n');
    }
  }

  // Builder/Optimizer: object with build_responses key
  if ((role === 'optimizer' || role === 'builder') && parsed.build_responses && Array.isArray(parsed.build_responses)) {
    return parsed.build_responses.map((item, i) => formatBuildResponse(item, i)).join('\n\n---\n\n');
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
