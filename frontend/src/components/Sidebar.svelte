<script>
  import { i18n } from '../lib/i18n/index.js';
  import { currentDebate } from '../lib/stores.js';
  import { appVersion } from '../lib/stores.js';
  import ProjectSelector from './ProjectSelector.svelte';

  let { navigate, currentRoute } = $props();

  let projectSelector;

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let hasActiveDebate = $derived(
    $currentDebate && ['pending', 'running'].includes($currentDebate.status)
  );

  const routeGroups = {
    projects: ['projects'],
    blueprint: ['blueprint'],
    config: ['config'],
    modules: ['modules'],
    proposals: ['proposals'],
  };

  function isActive(route) {
    const group = routeGroups[route];
    if (group) {
      return group.some((r) => currentRoute === r || currentRoute?.startsWith(r + '/'));
    }
    return currentRoute === route;
  }

  function isActiveAny(routes) {
    return routes.some((r) => isActive(r));
  }

  let navSections = $derived([
    {
      id: 'run',
      label: t('nav.section.run'),
      items: [
        ...(hasActiveDebate ? [{ id: 'debate', label: t('nav.debate'), icon: '💬', route: 'debate' }] : []),
        { id: 'input', label: t('nav.input'), icon: '💬', route: 'input' },
        { id: 'output', label: t('nav.output'), icon: '🖨️', route: 'output' },
        { id: 'documents', label: t('nav.documents'), icon: '📄', route: 'documents' },
        { id: 'archive', label: t('nav.archive'), icon: '📚', route: 'archive' },
      ],
    },
    {
      id: 'build',
      label: t('nav.section.build'),
      items: [
        {
          id: 'canvas',
          label: t('nav.canvas'),
          icon: '🧩',
          route: 'blueprint',
          children: [
            { id: 'blueprints', label: t('nav.blueprints'), route: 'blueprint' },
            { id: 'workflows', label: t('nav.workflows'), route: 'blueprint' },
          ],
        },
        {
          id: 'management',
          label: t('nav.section.management'),
          isSubHeader: true,
        },
        { id: 'llm-profiles', label: t('nav.llmProfiles'), icon: '🤖', route: 'config' },
        { id: 'service-llm', label: t('nav.serviceLlm'), icon: '🔧', route: 'config' },
        { id: 'roles-personas', label: t('nav.rolesPersonas'), icon: '👤', route: 'config' },
        { id: 'modules', label: t('nav.modules'), icon: '🧩', route: 'modules' },
        { id: 'translation', label: t('nav.translation'), icon: '🌐', route: 'translation' },
      ],
    },
    {
      id: 'config',
      label: t('nav.section.config'),
      items: [
        { id: 'projects', label: t('nav.projects'), icon: '📁', route: 'projects' },
        { id: 'audit', label: t('nav.audit'), icon: '📋', route: 'audit' },
        { id: 'backup', label: t('nav.backup'), icon: '💾', route: 'config' },
      ],
    },
  ]);
</script>

<aside class="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
  <!-- Logo / Brand -->
  <div class="h-16 flex items-center px-6 border-b border-gray-200 dark:border-gray-700">
    <span class="text-xl font-bold text-gray-800 dark:text-white">Danwa</span>
    <span class="ml-2 text-xs text-gray-500 dark:text-gray-400">v{$appVersion || '…'}</span>
  </div>

  <!-- Project Selector -->
  <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
    <ProjectSelector bind:this={projectSelector} {navigate} />
  </div>

  <!-- Navigation -->
  <nav class="flex-1 overflow-y-auto px-4 py-4" aria-label="Main navigation">
    <!-- Dashboard (standalone, above sections) -->
    <button
      class="w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors mb-3
        {currentRoute === 'dashboard'
          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
          : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}"
      onclick={() => navigate('dashboard')}
      aria-current={currentRoute === 'dashboard' ? 'page' : undefined}
    >
      <span class="mr-3 text-lg" aria-hidden="true">📊</span>
      {t('nav.dashboard')}
    </button>

    {#each navSections as section}
      <!-- Section divider -->
      <div class="border-t border-gray-200 dark:border-gray-700 my-3" />

      <!-- Section header -->
      <p class="px-3 mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
        {section.label}
      </p>

      <!-- Section items -->
      <div class="space-y-0.5">
        {#each section.items as item}
          {#if item.isSubHeader}
            <!-- Sub-header (e.g. "Management") -->
            <div class="flex items-center px-3 py-1.5 mt-2 mb-1">
              <span class="flex-1 text-xs font-medium text-gray-500 dark:text-gray-400">
                {item.label}
              </span>
              <span class="flex-1 border-t border-gray-200 dark:border-gray-700" />
            </div>
          {:else if item.children}
            <!-- Parent item with children (e.g. Canvas) -->
            <div>
              <button
                class="w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors
                  {isActive(item.route)
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}"
                onclick={() => navigate(item.route)}
                aria-current={isActive(item.route) ? 'page' : undefined}
              >
                <span class="mr-3 text-lg" aria-hidden="true">{item.icon}</span>
                {item.label}
              </button>
              <!-- Children (indented) -->
              <div class="ml-8 mt-0.5 space-y-0.5">
                {#each item.children as child}
                  <button
                    class="w-full flex items-center px-3 py-1.5 rounded-md text-sm transition-colors
                      {isActive(child.route) && child.id === currentRoute
                        ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/50 dark:text-blue-300 font-medium'
                        : 'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700'}"
                    onclick={() => navigate(child.route)}
                  >
                    {child.label}
                  </button>
                {/each}
              </div>
            </div>
          {:else}
            <!-- Regular nav item -->
            <button
              class="w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors
                {isActive(item.route)
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}"
              onclick={() => navigate(item.route)}
              aria-current={isActive(item.route) ? 'page' : undefined}
            >
              <span class="mr-3 text-lg" aria-hidden="true">{item.icon}</span>
              {item.label}
            </button>
          {/if}
        {/each}
      </div>
    {/each}
  </nav>

  <!-- Footer -->
  <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
    <p class="text-xs text-gray-500 dark:text-gray-400">
      {t('app.version', { version: $appVersion || '…' })}
    </p>
  </div>
</aside>
