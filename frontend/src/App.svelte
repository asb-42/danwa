<script>
  import { onMount } from 'svelte';
  import { route, routeParams } from './lib/stores.js';
  import { getHealth } from './lib/api.js';
  import { healthStatus } from './lib/stores.js';
  import { i18n } from './lib/i18n/index.js';
  import Layout from './components/Layout.svelte';
  import Dashboard from './views/Dashboard.svelte';
  import DebateView from './views/DebateView.svelte';
  import DocumentsView from './views/DocumentsView.svelte';
  import AuditView from './views/AuditView.svelte';
  import ConfigView from './views/ConfigView.svelte';
  import ArchiveView from './views/ArchiveView.svelte';
  import ProjectsView from './views/ProjectsView.svelte';
  import ProjectSettings from './components/ProjectSettings.svelte';
  import BlueprintCanvasView from './views/BlueprintCanvasView.svelte';

  // Hash-based routing — supports #/route and #/route/param
  function parseHash() {
    const hash = window.location.hash.slice(1) || '/dashboard';
    const parts = hash.split('/').filter(Boolean);
    return {
      route: parts[0] || 'dashboard',
      params: parts.slice(1),
    };
  }

  function navigate(path) {
    window.location.hash = `#/${path}`;
  }

  function applyRoute() {
    const parsed = parseHash();
    $route = parsed.route;
    $routeParams = parsed.params;
  }

  onMount(() => {
    // Set initial route from hash
    applyRoute();

    // Listen for hash changes
    const onHashChange = () => {
      applyRoute();
    };
    window.addEventListener('hashchange', onHashChange);

    // Initialize i18n from URL param, localStorage, or default
    const urlParams = new URLSearchParams(window.location.search);
    const urlLang = urlParams.get('lang');
    const storedLang = localStorage.getItem('locale');
    const initialLang = urlLang || storedLang || 'de';
    i18n.setLocale(initialLang);

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
    <Dashboard {navigate} />
  {:else if $route === 'debate'}
    <DebateView debateId={$routeParams[0] || null} {navigate} />
  {:else if $route === 'documents'}
    <DocumentsView {navigate} />
  {:else if $route === 'archive'}
    <ArchiveView {navigate} />
  {:else if $route === 'audit'}
    <AuditView />
  {:else if $route === 'projects' && $routeParams.length >= 2 && $routeParams[1] === 'settings'}
    <ProjectSettings projectId={$routeParams[0]} {navigate} />
  {:else if $route === 'projects'}
    <ProjectsView {navigate} />
  {:else if $route === 'config'}
    <ConfigView />
  {:else if $route === 'blueprint'}
    <BlueprintCanvasView />
  {:else}
    <Dashboard {navigate} />
  {/if}
</Layout>
