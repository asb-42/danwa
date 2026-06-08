/**
 * Application entry point.
 *
 * Mounts the root Svelte 5 `App` component and installs a global
 * `unhandledrejection` handler that forwards uncaught promise
 * rejections to the Unified Feedback Store so they surface as
 * classified error cards in the UI rather than being silently lost.
 */

import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';
import { feedbackStore } from './lib/stores/feedback.svelte.js';

// T-15: Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason;
  const message = reason?.message || String(reason || 'Unknown error');
  feedbackStore.reportError('unknown', `Unhandled error: ${message}`, String(reason));
});

const app = mount(App, {
  target: document.getElementById('app'),
});

export default app;
