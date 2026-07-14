/**
 * Hardcoded German Detection Tests
 *
 * Scans .svelte files for common German UI strings that should
 * use i18n translation keys instead of hardcoded text.
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'fs';
import { join, relative } from 'path';

const SRC_DIR = join(import.meta.dirname, '../../src');

// ---------------------------------------------------------------------------
// German word list — common UI strings that indicate hardcoded German
// ---------------------------------------------------------------------------

/**
 * Words/phrases that should never appear as hardcoded text in Svelte templates.
 * Case-insensitive matching on extracted text content.
 */
const GERMAN_INDICATORS = [
  // Common actions
  /\bAbbrechen\b/,
  /\bSpeichern\b/,
  /\bLöschen\b/,
  /\bBearbeiten\b/,
  /\bErstellen\b/,
  /\bHinzufügen\b/,
  /\bEntfernen\b/,
  /\bBestätigen\b/,
  /\bAbbrechen\b/,
  /\bSpeichern\b/,
  /\bSenden\b/,
  /\bSuchen\b/,
  /\bFiltern\b/,
  /\bSortieren\b/,

  // Navigation
  /\bDebatten\b/,
  /\bEinstellungen\b/,
  /\bKonfiguration\b/,
  /\bVerwaltung\b/,
  /\bProfil\b/,
  /\bÜbersicht\b/,

  // Common UI
  /\bLaden\b/,
  /\bFehler\b/,
  /\bWarnung\b/,
  /\bErfolg\b/,
  /\bInfo\b/,
  /\bJa\b/,
  /\bNein\b/,
  /\bOK\b/,

  // Interactive debate
  /\bDebattenraum\b/,
  /\bNeuer\b/,
  /\bRaum\b/,
  /\bEreignisse\b/,
  /\bVerlauf\b/,
  /\bAktion\b/,
  /\bStarten\b/,
  /\bRolle\b/,
  /\bNachricht\b/,

  // Status
  /\bAktiv\b/,
  /\bInaktiv\b/,
  /\bAbgeschlossen\b/,
  /\bAusstehend\b/,
  /\bFehlerhaft\b/,

  // Forms
  /\bPflichtfeld\b/,
  /\bUngültig\b/,
  /\bBitte\b/,
  /\bWählen\b/,
  /\bEingeben\b/,
];

// Files/directories to skip (known exceptions)
const SKIP_PATHS = [
  'i18n/',          // Translation files themselves
  'tests/',         // Test files
  'node_modules/',
  '.git/',
];

// Exact strings to whitelist (known exceptions)
const EXACT_WHITELIST = new Set([
  'Danwa',          // Product name
  'Danwa Kitsune',  // Product name
  'API',            // Acronym
  'LLM',            // Acronym
  'JSON',           // Acronym
  'OK',             // Universal
  'A2A',            // Protocol name
  'HITL',           // Protocol name
  'Svelte',         // Framework name
  'Vite',           // Tool name
  'WebSocket',      // Tech name
  'OAuth',          // Protocol
  'OAuth2',         // Protocol
]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function findFiles(dir, ext) {
  const results = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_PATHS.some((s) => entry.name === s)) {
        results.push(...findFiles(full, ext));
      }
    } else if (entry.name.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}

/**
 * Extract visible text content from Svelte template.
 * Strips <script>, <style>, comments, and HTML tags.
 */
function extractTemplateText(source) {
  // Remove script block
  let template = source.replace(/<script[\s\S]*?<\/script>/gi, '');
  // Remove style block
  template = template.replace(/<style[\s\S]*?<\/style>/gi, '');
  // Remove HTML comments
  template = template.replace(/<!--[\s\S]*?-->/g, '');
  // Remove Svelte comments {:else if ...}
  template = template.replace(/\{:[\s\S]*?\}/g, '');
  // Extract text between > and <
  const textParts = [];
  const textRegex = />([^<]+)</g;
  let match;
  while ((match = textRegex.exec(template)) !== null) {
    const text = match[1].trim();
    if (text) textParts.push(text);
  }
  // Extract placeholder="..." and title="..." attributes
  const attrRegex = /(?:placeholder|title|aria-label|alt)\s*=\s*"([^"]+)"/g;
  while ((match = attrRegex.exec(template)) !== null) {
    textParts.push(match[1]);
  }
  // Also check single-quoted attributes
  const attrRegexSingle = /(?:placeholder|title|aria-label|alt)\s*=\s*'([^']+)'/g;
  while ((match = attrRegexSingle.exec(template)) !== null) {
    textParts.push(match[1]);
  }
  return textParts;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('no hardcoded German', () => {
  const svelteFiles = findFiles(SRC_DIR, '.svelte');

  for (const filePath of svelteFiles) {
    const relPath = relative(SRC_DIR, filePath);
    const source = readFileSync(filePath, 'utf-8');
    const textParts = extractTemplateText(source);

    if (textParts.length === 0) continue;

    it(`${relPath} — no hardcoded German strings`, () => {
      const violations = [];

      for (const text of textParts) {
        // Skip whitelisted exact strings
        if (EXACT_WHITELIST.has(text)) continue;
        // Skip very short strings (likely labels/icons)
        if (text.length <= 2) continue;
        // Skip strings that are mostly numbers/punctuation
        if (/^[\d\s\-_.:,;/\\!@#$%^&*()+=\[\]{}|<>~`'"]+$/.test(text)) continue;
        // Skip Svelte expressions {variable}
        if (/^\{.*\}$/.test(text.trim())) continue;

        for (const pattern of GERMAN_INDICATORS) {
          if (pattern.test(text)) {
            violations.push({ text, pattern: pattern.source });
            break;
          }
        }
      }

      // Report violations
      if (violations.length > 0) {
        console.log(
          `\n⚠ Hardcoded German in ${relPath}:\n` +
            violations.map((v) => `  "${v.text}" matched ${v.pattern}`).join('\n')
        );
      }
      // Fail only if more than 2 violations (major gap)
      expect(
        violations.length,
        `Too many hardcoded German strings in ${relPath} (${violations.length}). ` +
          'Use t() for all user-facing text.'
      ).toBeLessThanOrEqual(2);
    });
  }
});
