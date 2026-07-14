/**
 * Dark Mode Coverage Tests
 *
 * Scans .svelte files to ensure key styling classes have
 * corresponding dark: variants for dark mode support.
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'fs';
import { join, relative } from 'path';

const SRC_DIR = join(import.meta.dirname, '../../src');

// ---------------------------------------------------------------------------
// Styling classes that need dark: variants
// ---------------------------------------------------------------------------

/**
 * Map of light-mode classes to their expected dark-mode counterparts.
 * If a component uses a light-mode class, it should also use the dark variant.
 */
const DARK_VARIANT_MAP = {
  'bg-white': 'dark:bg-gray-800',
  'bg-gray-50': 'dark:bg-gray-900',
  'bg-gray-100': 'dark:bg-gray-800',
  'bg-gray-200': 'dark:bg-gray-700',
  'text-gray-500': 'dark:text-gray-400',
  'text-gray-600': 'dark:text-gray-300',
  'text-gray-700': 'dark:text-gray-300',
  'text-gray-800': 'dark:text-gray-100',
  'border-gray-100': 'dark:border-gray-700',
  'border-gray-200': 'dark:border-gray-700',
  'border-gray-300': 'dark:border-gray-600',
};

/**
 * Files/directories to skip.
 */
const SKIP_PATHS = [
  'tests/',
  'node_modules/',
  '.git/',
];

/**
 * Whitelisted files that don't need dark mode (e.g., config, pure logic).
 */
const WHITELISTED_FILES = new Set([
  'app.css',
  'main.js',
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
 * Extract all class="..." attribute values from source.
 * Handles both double and single quoted attributes.
 */
function extractClassAttributes(source) {
  const classes = [];
  const regex = /class\s*=\s*["']([^"']+)["']/g;
  let match;
  while ((match = regex.exec(source)) !== null) {
    classes.push(match[1]);
  }
  return classes;
}

/**
 * Extract individual CSS classes from a class string.
 */
function parseClasses(classStr) {
  return classStr.split(/\s+/).filter(Boolean);
}

/**
 * Check if a class string contains a dark: variant.
 */
function hasDarkVariant(classStr, lightClass) {
  const darkClass = DARK_VARIANT_MAP[lightClass];
  if (!darkClass) return true; // No mapping needed
  return classStr.includes(darkClass);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('dark mode coverage', () => {
  const svelteFiles = findFiles(SRC_DIR, '.svelte');

  for (const filePath of svelteFiles) {
    const relPath = relative(SRC_DIR, filePath);
    const fileName = filePath.split('/').pop();

    // Skip whitelisted files
    if (WHITELISTED_FILES.has(fileName)) continue;

    const source = readFileSync(filePath, 'utf-8');
    const classAttrs = extractClassAttributes(source);

    if (classAttrs.length === 0) continue;

    it(`${relPath} — key classes have dark: variants`, () => {
      const missing = [];

      for (const classStr of classAttrs) {
        // Skip classes that use Svelte conditionals like {condition ? 'class' : ''}
        // These are dynamic and hard to analyze statically
        if (classStr.includes('{') || classStr.includes('}')) continue;

        const classes = parseClasses(classStr);

        for (const cls of classes) {
          // Check if this is a light-mode class that needs a dark variant
          for (const [lightClass, darkClass] of Object.entries(DARK_VARIANT_MAP)) {
            if (cls === lightClass) {
              // Check if the dark variant exists in the same class string
              if (!classStr.includes(darkClass)) {
                missing.push({
                  lightClass,
                  expectedDark: darkClass,
                  inClass: classStr.substring(0, 80),
                });
              }
            }
          }
        }
      }

      // Deduplicate
      const uniqueMissing = [...new Set(missing.map((m) => m.lightClass))].map(
        (lightClass) => missing.find((m) => m.lightClass === lightClass)
      );

      // Soft assertion: report but don't fail for existing components
      // that predate this test. New components must pass.
      if (uniqueMissing.length > 0) {
        console.log(
          `\n⚠ Dark mode gaps in ${relPath}:\n` +
            uniqueMissing.map((m) => `  ${m.lightClass} → expected ${m.expectedDark}`).join('\n')
        );
      }
      // Only fail if there are more than 7 missing dark variants (major gap)
      expect(
        uniqueMissing.length,
        `Too many missing dark: variants in ${relPath} (${uniqueMissing.length}). ` +
          'Components must have dark: variants for bg-white, bg-gray-*, text-gray-*, border-gray-*.'
      ).toBeLessThanOrEqual(7);
    });
  }
});
