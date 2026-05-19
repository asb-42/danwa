/**
 * ELK.js Singleton Service
 *
 * Provides a single shared ELK.js instance for all layout calculations
 * across Blueprint, Workflow, and Dashboard components.
 *
 * ELK.js bundles a complete Java port (~1.2MB). Instantiating it multiple
 * times creates separate Web Workers and multiplies memory usage.
 * This module ensures exactly one instance is created (lazy-loaded on first use).
 */

import ELK from 'elkjs/lib/elk.bundled.js';

/** @type {ELK | null} */
let elkInstance = null;

/**
 * Get (or create) the singleton ELK.js instance.
 * @returns {ELK}
 */
export function getElk() {
  if (!elkInstance) {
    elkInstance = new ELK();
  }
  return elkInstance;
}

/**
 * Run ELK layout on the given graph definition.
 * @param {Object} graph - ELK graph object
 * @returns {Promise<Object>} Layout result
 */
export async function runLayout(graph) {
  return getElk().layout(graph);
}
