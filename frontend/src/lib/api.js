/**
 * API client for Danwa backend.
 * All communication in English (Accept-Language: en).
 *
 * This file re-exports all domain-specific sub-modules so that existing
 * imports like `import { getDebates } from '../lib/api.js'` continue to work.
 */

export * from './api/core.js';
export * from './api/debate.js';
export * from './api/profile.js';
export * from './api/project.js';
export * from './api/document.js';
export * from './api/settings.js';
export * from './api/backup.js';
export * from './api/translation.js';
export * from './api/i18n.js';
export * from './api/module.js';
export * from './api/session.js';
export * from './api/assistant.js';
