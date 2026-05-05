<script>
  import { i18n } from '../lib/i18n/index.js';
  import ProjectSelector from './ProjectSelector.svelte';

  export let navigate;
  export let currentRoute;

  let projectSelector;

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  $: navItems = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: '📊' },
    { id: 'debate', label: t('nav.debate'), icon: '💬' },
    { id: 'archive', label: t('nav.archive'), icon: '📚' },
    { id: 'audit', label: t('nav.audit'), icon: '📋' },
    { id: 'projects', label: t('nav.projects'), icon: '📁' },
    { id: 'config', label: t('nav.config'), icon: '⚙️' },
  ];

  function isActive(item) {
    if (item.id === 'projects') {
      return currentRoute === 'projects' || currentRoute?.startsWith('projects/');
    }
    return currentRoute === item.id;
  }
</script>

<aside class="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
  <!-- Logo / Brand -->
  <div class="h-16 flex items-center px-6 border-b border-gray-200 dark:border-gray-700">
    <span class="text-xl font-bold text-gray-800 dark:text-white">Danwa</span>
    <span class="ml-2 text-xs text-gray-500 dark:text-gray-400">v2.0</span>
  </div>

  <!-- Project Selector -->
  <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
    <ProjectSelector bind:this={projectSelector} {navigate} />
  </div>

  <!-- Navigation -->
  <nav class="flex-1 px-4 py-4 space-y-1" aria-label="Main navigation">
    {#each navItems as item}
      <button
        class="w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors
          {isActive(item)
            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
            : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}"
        on:click={() => navigate(item.id)}
        aria-current={isActive(item) ? 'page' : undefined}
      >
        <span class="mr-3 text-lg" aria-hidden="true">{item.icon}</span>
        {item.label}
      </button>
    {/each}
  </nav>

  <!-- Footer -->
  <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
    <p class="text-xs text-gray-500 dark:text-gray-400">
      Debate-Agent v2.0
    </p>
  </div>
</aside>
