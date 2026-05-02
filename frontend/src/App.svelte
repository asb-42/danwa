<script>
  import { onMount } from 'svelte';
  import { route } from './lib/stores.js';
  import { getHealth } from './lib/api.js';
  import { healthStatus } from './lib/stores.js';
  import Layout from './components/Layout.svelte';
  import Dashboard from './views/Dashboard.svelte';
  import DebateView from './views/DebateView.svelte';
  import AuditView from './views/AuditView.svelte';
  import ConfigView from './views/ConfigView.svelte';

  // Hash-based routing
  function parseHash() {
    const hash = window.location.hash.slice(1) || '/dashboard';
    const parts = hash.split('/').filter(Boolean);
    return parts[0] || 'dashboard';
  }

  function navigate(path) {
    window.location.hash = `#/${path}`;
  }

  onMount(() => {
    // Set initial route from hash
    $route = parseHash();

    // Listen for hash changes
    const onHashChange = () => {
      $route = parseHash();
    };
    window.addEventListener('hashchange', onHashChange);

    // Health check on mount
    getHealth()
      .then((data) => {
        $healthStatus = { status: data.status, version: data.version };
      })
      .catch(() => {
        $healthStatus = { status: 'unreachable', version: '' };
      });

    return () => {
      window.removeEventListener('hashchange', onHashChange);
    };
  });
</script>

<Layout {navigate} currentRoute={$route}>
  {#if $route === 'dashboard'}
    <Dashboard />
  {:else if $route === 'debate'}
    <DebateView />
  {:else if $route === 'audit'}
    <AuditView />
  {:else if $route === 'config'}
    <ConfigView />
  {:else}
    <Dashboard />
  {/if}
</Layout>
