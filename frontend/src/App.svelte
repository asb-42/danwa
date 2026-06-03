<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { route, routeParams, addToast } from './lib/stores.js';
  import { getHealth } from './lib/api.js';
  import { healthStatus, appVersion } from './lib/stores.js';
  import { getVersion } from './lib/api.js';
  import { i18n, tStore, discoverLanguagePacks, setToastCallback } from './lib/i18n/index.js';
  import { isAuthenticated } from './lib/stores/auth.svelte.js';
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
import WorkflowExecutionView from './views/WorkflowExecutionView.svelte';
import TranslationDashboard from './views/TranslationDashboard.svelte';
import ModulesView from './views/ModulesView.svelte';
import ProposalsView from './views/ProposalsView.svelte';
import ManageView from './views/ManageView.svelte';
import MvpDebateView from './views/MvpDebateView.svelte';
import BundleComposerView from './views/BundleComposerView.svelte';
import LoginView from './views/LoginView.svelte';
import UserManagement from './views/UserManagement.svelte';
import ProfileView from './views/ProfileView.svelte';
import TenantSettingsView from './views/TenantSettingsView.svelte';
import CasesView from './views/CasesView.svelte';
import TagManagerView from './views/TagManagerView.svelte';
import BYOKManager from './views/BYOKManager.svelte';
import ServerHealthView from './views/ServerHealthView.svelte';
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

  // Update document.title on route or locale change so the browser tab
  // shows the current view in the user's language, not just the URL.
  $effect(() => {
    const dict = $i18n;
    const currentRoute = get(route);
    const titleKey = `nav.${currentRoute}`;
    const routeTitle = dict?.[titleKey] || dict?.['app.title'] || 'Debate Engine';
    const appTitle = dict?.['app.title'] || 'Debate Engine';
    document.title = currentRoute === 'dashboard' || !dict?.[titleKey]
      ? appTitle
      : `${routeTitle} · ${appTitle}`;
  });
</script>

{#if !$isAuthenticated}
<LoginView />
{:else}
<Layout {navigate} currentRoute={$route}>
  <svelte:boundary onerror={(e, reset) => {
    console.error('[App] View crashed:', e);
    addToast({ type: 'error', message: $tStore('app.viewCrashed', { error: e.message }) });
  }}>
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
    {:else if $route === 'execution'}
      <WorkflowExecutionView sessionId={$routeParams[0] || null} {navigate} />
    {:else if $route === 'blueprint'}
      <BlueprintCanvasView layoutId={$routeParams[0] || null} routeParams={$routeParams} {navigate} />
    {:else if $route === 'bundle-composer'}
      <BundleComposerView />
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
    {:else if $route === 'users'}
      <UserManagement />
    {:else if $route === 'profile'}
      <ProfileView />
    {:else if $route === 'tenant-settings'}
      <TenantSettingsView />
    {:else if $route === 'my-keys'}
      <BYOKManager />
    {:else if $route === 'server-health'}
      <ServerHealthView />
    {:else if $route === 'case-list'}
      <CasesView {navigate} />
    {:else if $route === 'tags'}
      <TagManagerView />
    {:else}
      <Dashboard {navigate} />
    {/if}

    {#snippet failed(error, reset)}
      <div class="view-error" role="alert" aria-live="assertive">
        <h2>{$tStore('app.viewCrashedTitle')}</h2>
        <p>{$tStore('app.viewCrashedMessage', { error: error.message })}</p>
        <div class="view-error-actions">
          <button class="btn btn-primary" onclick={() => reset()}>{$tStore('common.retry')}</button>
          <button class="btn" onclick={() => navigate('dashboard')}>{$tStore('app.backToDashboard')}</button>
        </div>
      </div>
    {/snippet}
  </svelte:boundary>
  <ToastContainer />
</Layout>
{/if}
