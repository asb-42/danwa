<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { route, routeParams, addToast, healthStatus, appVersion } from './lib/stores.js';
  import { getHealth, getVersion } from './lib/api.js';
  import { i18n, tStore, discoverLanguagePacks, setToastCallback } from './lib/i18n/index.js';
  import { isAuthenticated } from './lib/stores/auth.svelte.js';
  import Layout from './components/Layout.svelte';
  // LoginView stays eager — it's the first thing users see and is small.
  import LoginView from './views/LoginView.svelte';
  import ToastContainer from './components/ToastContainer.svelte';
  import ErrorPanel from './components/feedback/ErrorPanel.svelte';

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
      {#await import('./views/Dashboard.svelte') then Mod}<Mod.default {navigate} />{/await}
    {:else if $route === 'debate'}
      {#await import('./views/DebateView.svelte') then Mod}<Mod.default debateId={$routeParams[0] || null} {navigate} />{/await}
    {:else if $route === 'documents'}
      {#await import('./views/DocumentsView.svelte') then Mod}<Mod.default {navigate} />{/await}
    {:else if $route === 'archive'}
      {#await import('./views/ArchiveView.svelte') then Mod}<Mod.default {navigate} />{/await}
    {:else if $route === 'audit'}
      {#await import('./views/AuditView.svelte') then Mod}<Mod.default debateId={$routeParams[0] || null} />{/await}
    {:else if $route === 'config'}
      {#await import('./views/ConfigView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'manage'}
      {#await import('./views/ManageView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'execution'}
      {#await import('./views/WorkflowExecutionView.svelte') then Mod}<Mod.default sessionId={$routeParams[0] || null} {navigate} />{/await}
    {:else if $route === 'replay'}
      {#await import('./views/ReplayView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'diff'}
      {#await import('./views/DiffView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'proposals'}
      {#await import('./views/ProposalsView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'mvp-debate'}
      {#await import('./views/MvpDebateView.svelte') then Mod}<Mod.default debateId={$routeParams[0] || null} {navigate} />{/await}
    {:else if $route === 'users'}
      {#await import('./views/UserManagement.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'profile'}
      {#await import('./views/ProfileView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'tenant-settings'}
      {#await import('./views/TenantSettingsView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'my-keys'}
      {#await import('./views/BYOKManager.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'server-health'}
      {#await import('./views/ServerHealthView.svelte') then Mod}<Mod.default />{/await}
    {:else if $route === 'case-list'}
      {#await import('./views/CasesView.svelte') then Mod}<Mod.default {navigate} />{/await}
    {:else if $route === 'workspace'}
      {#await import('./views/WorkspaceView.svelte') then Mod}<Mod.default {navigate} />{/await}
    {:else if $route === 'inbox'}
      {#await import('./views/InboxView.svelte') then Mod}<Mod.default {navigate} />{/await}
    {:else if $route === 'browse'}
      {#await import('./views/BrowseView.svelte') then Mod}<Mod.default {navigate} />{/await}
    {:else if $route === 'tags'}
      {#await import('./views/TagManagerView.svelte') then Mod}<Mod.default />{/await}
    {:else}
      {#await import('./views/Dashboard.svelte') then Mod}<Mod.default {navigate} />{/await}
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
  <ErrorPanel />
  <ToastContainer />
</Layout>
{/if}
