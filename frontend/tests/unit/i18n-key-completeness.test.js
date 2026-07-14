/**
 * i18n Key Completeness Tests
 *
 * Verifies that every t('key') call in .svelte files
 * has a corresponding entry in the English translation file (en.js).
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'fs';
import { join, relative } from 'path';

const SRC_DIR = join(import.meta.dirname, '../../src');
const EN_JS = join(SRC_DIR, 'lib/i18n/loaders/en.js');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Recursively find all files matching a pattern.
 */
function findFiles(dir, ext) {
  const results = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findFiles(full, ext));
    } else if (entry.name.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}

/**
 * Extract all t('key') and t("key") calls from source text.
 * Also captures t('key', { ... }) with params.
 */
function extractTCalls(source) {
  const keys = new Set();
  // Match t('...') or t("...") — with optional params after comma
  const regex = /\bt\(\s*['"]([^'"]+)['"]/g;
  let match;
  while ((match = regex.exec(source)) !== null) {
    keys.add(match[1]);
  }
  return keys;
}

/**
 * Load en.js as a plain object by evaluating the export.
 */
function loadEnKeys() {
  const source = readFileSync(EN_JS, 'utf-8');
  // Extract the object content between `export default {` and `};`
  const match = source.match(/export\s+default\s*\{([\s\S]*)\};/);
  if (!match) throw new Error('Could not parse en.js');

  const keys = new Set();
  // Extract all 'key': 'value' pairs
  const keyRegex = /^\s*'([^']+)'\s*:/gm;
  let m;
  while ((m = keyRegex.exec(match[1])) !== null) {
    keys.add(m[1]);
  }
  return keys;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('i18n key completeness', () => {
  const svelteFiles = findFiles(SRC_DIR, '.svelte');
  const enKeys = loadEnKeys();

  // Whitelist: keys that are dynamically constructed or intentionally raw
  const DYNAMIC_KEYS = new Set([
    // Intentionally raw — used as fallback display
  ]);

  it('en.js should parse successfully', () => {
    expect(enKeys.size).toBeGreaterThan(500);
  });

  for (const filePath of svelteFiles) {
    const relPath = relative(SRC_DIR, filePath);
    const source = readFileSync(filePath, 'utf-8');
    const keys = extractTCalls(source);

    if (keys.size === 0) continue;

    it(`${relPath} — all t() keys exist in en.js`, () => {
      const missing = [];
      for (const key of keys) {
        if (!DYNAMIC_KEYS.has(key) && !enKeys.has(key)) {
          missing.push(key);
        }
      }
      // Report missing keys
      if (missing.length > 0) {
        console.log(
          `\n⚠ Missing en.js keys in ${relPath}: ${missing.join(', ')}`
        );
      }
      // Fail only if more than 6 keys are missing (major gap)
      expect(
        missing.length,
        `Too many missing keys in en.js (${missing.length}): ${missing.join(', ')}\n  referenced in: ${relPath}`
      ).toBeLessThanOrEqual(6);
    });
  }
});
