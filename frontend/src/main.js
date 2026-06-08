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
