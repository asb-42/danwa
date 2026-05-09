/**
 * A2A API client — discover and store A2A agent capabilities.
 */

import { request } from './api.js';

/**
 * Discover an A2A agent's capabilities.
 * @param {string} endpointUrl
 * @returns {Promise<{name, description, version, capabilities, skills, input_modes, output_modes}>}
 */
export function discoverA2A(endpointUrl) {
  return request('/api/v1/a2a/discover', {
    method: 'POST',
    body: JSON.stringify({ endpoint_url: endpointUrl }),
  });
}

/**
 * Store discovered A2A capabilities in a blueprint LLM profile.
 * @param {string} profileId
 * @param {Object} capabilities
 * @returns {Promise<{status, profile_id}>}
 */
export function saveA2ACapabilities(profileId, capabilities) {
  return request(`/api/v1/a2a/capabilities/${profileId}`, {
    method: 'POST',
    body: JSON.stringify({ capabilities }),
  });
}
