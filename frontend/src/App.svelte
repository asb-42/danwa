<script>
  import { onMount } from 'svelte';
  import { route, routeParams, addToast } from './lib/stores.js';
  import { getHealth } from './lib/api.js';
  import { healthStatus, appVersion } from './lib/stores.js';
  import { getVersion } from './lib/api.js';
  import { i18n, discoverLanguagePacks, setToastCallback } from './lib/i18n/index.js';
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
  import ReplayView from './views/ReplayView.svelte';
  import DiffView from './views/DiffView.svelte';
  import OutputComposerView from './views/OutputComposerView.svelte';
import InputComposerView from './views/InputComposerView.svelte';
import TranslationDashboard from './views/TranslationDashboard.svelte';
import ModulesView from './views/ModulesView.svelte';
import ProposalsView from './views/ProposalsView.svelte';
import ManageView from './views/ManageView.svelte';
import MvpDebateView from './views/MvpDebateView.svelte';
import ToastContainer from './components/ToastContainer.svelte';

  // Register toast callback for i18n fallback warnings
  setToastCallback(addToast);

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
    route.set(parsed.route);
    routeParams.set(parsed.params);
  }

  onMount(async () => {
    // Set initial route from hash
    applyRoute();

    // Listen for hash changes
    const onHashChange = () => {
      applyRoute();
    };
    window.addEventListener('hashchange', onHashChange);

    // Initialize i18n from URL param, localStorage, or default
    // Discover language packs first so custom locales are available
    await discoverLanguagePacks();

    const urlParams = new URLSearchParams(window.location.search);
    const urlLang = urlParams.get('lang');
    const storedLang = localStorage.getItem('locale');
    const initialLang = urlLang || storedLang || 'de';
    i18n.setLocale(initialLang);

    // Health check on mount
    getHealth()
      .then((data) => {
        healthStatus.set({ status: data.status, version: data.version });
      })
      .catch(() => {
        healthStatus.set({ status: 'unreachable', version: '' });
      });

    // Load application version from API
    getVersion()
      .then((data) => {
        appVersion.set(data.version);
      })
      .catch(() => {
        appVersion.set('');
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
  {:else if $route === 'manage'}
    <ManageView />
  {:else if $route === 'blueprint'}
    <BlueprintCanvasView layoutId={$routeParams[0] || null} {navigate} />
  {:else if $route === 'replay'}
    <ReplayView />
  {:else if $route === 'diff'}
    <DiffView />
  {:else if $route === 'output'}
    <OutputComposerView />
  {:else if $route === 'input'}
    <InputComposerView />
   {:else if $route === 'translation'}
    <TranslationDashboard {navigate} />
  {:else if $route === 'modules'}
    <ModulesView {navigate} />
  {:else if $route === 'proposals'}
    <ProposalsView />
  {:else if $route === 'mvp-debate'}
    <MvpDebateView debateId={$routeParams[0] || null} {navigate} />
  {:else}
    <Dashboard {navigate} />
  {/if}
  <ToastContainer />
</Layout>
