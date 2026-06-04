<script>
  import { onMount } from 'svelte';
  import { activeProject } from '../lib/stores.js';
  import { getProjects } from '../lib/api.js';
  import { tStore } from '../lib/i18n/index.js';

  let { compact = false, navigate = undefined } = $props();

  let t = $derived($tStore);

  let projects = $state([]);
  let isOpen = $state(false);
  let isLoading = $state(false);

  onMount(async () => {
    await loadProjects();
  });

  async function loadProjects() {
    isLoading = true;
    try {
      projects = await getProjects();
      // Auto-select default project if nothing is selected
      if (!$activeProject && projects.length > 0) {
        const defaultProject = projects.find(p => p.is_system) || projects[0];
        activeProject.set({ id: defaultProject.id, name: defaultProject.name });
      }
      // Validate that active project still exists
      if ($activeProject && !projects.find(p => p.id === $activeProject.id)) {
        activeProject.set(projects.length > 0
          ? { id: projects[0].id, name: projects[0].name }
          : null);
      }
    } catch (err) {
      if (import.meta.env.DEV) console.warn('Could not load projects:', err);
    } finally {
      isLoading = false;
    }
  }

  function selectProject(project) {
    activeProject.set({ id: project.id, name: project.name });
    isOpen = false;
  }

  function handleClickOutside(event) {
    if (!event.target.closest('.project-selector')) {
      isOpen = false;
    }
  }

  // Re-export loadProjects so parent can trigger refresh
  export function refresh() {
    return loadProjects();
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="project-selector relative" class:w-full={!compact}>
  <button
    class="w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg
           border border-gray-200 dark:border-gray-600
           bg-white dark:bg-gray-700 text-gray-800 dark:text-white
           hover:border-blue-400 dark:hover:border-blue-500
           focus:ring-2 focus:ring-blue-500 focus:border-blue-500
           transition-colors"
    onclick={(e) => { e.stopPropagation(); isOpen = !isOpen; if (isOpen) loadProjects(); }}
    aria-haspopup="listbox"
    aria-expanded={isOpen}
  >
    <span class="flex items-center gap-2 truncate">
      <span class="text-base" aria-hidden="true">📁</span>
      {#if $activeProject}
        <span class="truncate">{$activeProject.name}</span>
      {:else}
        <span class="text-gray-400 dark:text-gray-500">{t('projects.noActiveProject')}</span>
      {/if}
    </span>
    <svg class="w-4 h-4 text-gray-400 flex-shrink-0 transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  {#if isOpen}
    <div
      class="absolute z-50 mt-1 w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg
             border border-gray-200 dark:border-gray-700 max-h-64 overflow-y-auto"
      role="listbox"
    >
      {#if isLoading}
        <div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
          {t('common.loading')}
        </div>
      {:else if projects.length === 0}
        <div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
          {t('projects.noProjects')}
        </div>
      {:else}
        {#each projects as project}
          <button
            class="w-full text-left px-3 py-2 text-sm flex items-center justify-between
                   hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors
                   {$activeProject?.id === project.id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}"
            onclick={() => selectProject(project)}
            role="option"
            aria-selected={$activeProject?.id === project.id}
          >
            <span class="truncate">
              {project.name}
              {#if project.is_system}
                <span class="text-xs text-gray-400 dark:text-gray-500 ml-1">({t('projects.systemProject')})</span>
              {/if}
            </span>
            {#if $activeProject?.id === project.id}
              <span class="text-blue-600 dark:text-blue-400 flex-shrink-0">✓</span>
            {/if}
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</div>
