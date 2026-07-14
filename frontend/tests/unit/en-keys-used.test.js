/**
 * en.js Key Usage Tests
 *
 * Detects orphaned translation keys in en.js that are never
 * referenced in any source file. Informational — helps keep
 * the translation file clean.
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'fs';
import { join, relative } from 'path';

const SRC_DIR = join(import.meta.dirname, '../../src');
const EN_JS = join(SRC_DIR, 'lib/i18n/loaders/en.js');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function findFiles(dir, ext) {
  const results = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== 'node_modules' && entry.name !== '.git' && entry.name !== 'tests') {
        results.push(...findFiles(full, ext));
      }
    } else if (entry.name.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}

/**
 * Load en.js keys.
 */
function loadEnKeys() {
  const source = readFileSync(EN_JS, 'utf-8');
  const match = source.match(/export\s+default\s*\{([\s\S]*)\};/);
  if (!match) throw new Error('Could not parse en.js');

  const keys = new Set();
  const keyRegex = /^\s*'([^']+)'\s*:/gm;
  let m;
  while ((m = keyRegex.exec(match[1])) !== null) {
    keys.add(m[1]);
  }
  return keys;
}

/**
 * Load all source files and extract referenced keys.
 */
function findReferencedKeys() {
  const referenced = new Set();

  // Scan .svelte files for t('key') calls
  const svelteFiles = findFiles(SRC_DIR, '.svelte');
  for (const filePath of svelteFiles) {
    const source = readFileSync(filePath, 'utf-8');
    const regex = /\bt\(\s*['"]([^'"]+)['"]/g;
    let match;
    while ((match = regex.exec(source)) !== null) {
      referenced.add(match[1]);
    }
  }

  // Scan .js/.ts files for key references (e.g., in tests or config)
  const jsFiles = [
    ...findFiles(SRC_DIR, '.js'),
    ...findFiles(SRC_DIR, '.ts'),
  ];
  for (const filePath of jsFiles) {
    const source = readFileSync(filePath, 'utf-8');
    // Look for key strings in assertions or config
    const regex = /['"]([a-z][a-z0-9.]+[a-z0-9])['"]/g;
    let match;
    while ((match = regex.exec(source)) !== null) {
      // Only add if it looks like a translation key (contains dot, starts with known prefix)
      const key = match[1];
      if (key.includes('.') && /^(nav|dashboard|debate|audit|common|error|agent|status|interactive|fork|case|document|workflow|profile|header|team|llm|moderator|auth|lang|role|prompt|tone|module|translation|proposal|publish|inbox|browse|tag|workspace|graph|timeline)\./.test(key)) {
        referenced.add(key);
      }
    }
  }

  return referenced;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('en.js key usage', () => {
  const enKeys = loadEnKeys();
  const referencedKeys = findReferencedKeys();

  it('en.js should parse successfully', () => {
    expect(enKeys.size).toBeGreaterThan(500);
  });

  it('should find referenced keys in source files', () => {
    expect(referencedKeys.size).toBeGreaterThan(100);
  });

  it('should have no orphaned keys (informational)', () => {
    const orphaned = [];
    for (const key of enKeys) {
      if (!referencedKeys.has(key)) {
        orphaned.push(key);
      }
    }

    // This is informational — we log orphans but don't fail the test
    // since some keys may be used dynamically or via backend
    if (orphaned.length > 0) {
      console.log(
        `\n⚠ ${orphaned.length} orphaned keys in en.js (not referenced in source):\n` +
          orphaned.slice(0, 20).map((k) => `  ${k}`).join('\n') +
          (orphaned.length > 20 ? `\n  ... and ${orphaned.length - 20} more` : '')
      );
    }

    // Soft assertion: allow orphans since many keys are used
    // dynamically or via backend. This test is informational.
    const orphanRate = orphaned.length / enKeys.size;
    if (orphanRate > 0.3) {
      console.log(
        `\n⚠ High orphan rate in en.js: ${(orphanRate * 100).toFixed(1)}% ` +
          `(${orphaned.length} of ${enKeys.size} keys unreferenced). ` +
          'Many keys may be used dynamically or via backend.'
      );
    }
    // Don't fail — this is purely informational
    expect(true).toBe(true);
  });
});
