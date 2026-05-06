<script>
  import { onMount } from 'svelte';
  import { activeProject, loading, error } from '../lib/stores.js';
  import { getProjects, createProject, updateProject, deleteProject } from '../lib/api.js';
  import { i18n, formatDate } from '../lib/i18n/index.js';

  let { navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let projects = $state([]);
  let isLoading = $state(false);
  let statusMessage = $state('');

  // Modal state
  let showModal = $state(false);
  let modalMode = $state('create'); // 'create' | 'edit'
  let formData = $state({ name: '', description: '' });
  let formErrors = $state({});
  let isSaving = $state(false);

  // Delete confirmation
  let showDeleteConfirm = $state(false);
  let deleteTarget = $state(null);
  let isDeleting = $state(false);

  onMount(async () => {
    await loadProjects();
  });

  async function loadProjects() {
    isLoading = true;
    $error = null;
    try {
      projects = await getProjects();
    } catch (err) {
      $error = err.message;
      projects = [];
    } finally {
      isLoading = false;
    }
  }

  // --- Modal ---
  function openCreate() {
    modalMode = 'create';
    formData = { name: '', description: '' };
    formErrors = {};
    showModal = true;
  }

  function openEdit(project) {
    modalMode = 'edit';
    formData = { id: project.id, name: project.name, description: project.description || '' };
    formErrors = {};
    showModal = true;
  }

  function closeModal() {
    showModal = false;
    formErrors = {};
  }

  function validateForm() {
    const errors = {};
    if (!formData.name?.trim()) errors.name = t('config.required');
    formErrors = errors;
    return Object.keys(errors).length === 0;
  }

  async function handleSave() {
    if (!validateForm()) return;
    isSaving = true;
    try {
      if (modalMode === 'create') {
        const project = await createProject(formData.name.trim(), formData.description.trim());
        statusMessage = `✓ ${t('projects.projectCreated')}`;
        // Auto-select newly created project
        $activeProject = { id: project.id, name: project.name };
      } else {
        await updateProject(formData.id, {
          name: formData.name.trim(),
          description: formData.description.trim(),
        });
        statusMessage = `✓ ${t('projects.projectUpdated')}`;
        // Update active project name if it was renamed
        if ($activeProject?.id === formData.id) {
          $activeProject = { id: formData.id, name: formData.name.trim() };
        }
      }
      showModal = false;
      await loadProjects();
    } catch (err) {
      $error = err.message;
    } finally {
      isSaving = false;
    }
  }

  // --- Delete ---
  function confirmDelete(project) {
    deleteTarget = project;
    showDeleteConfirm = true;
  }

  function closeDeleteConfirm() {
    showDeleteConfirm = false;
    deleteTarget = null;
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    isDeleting = true;
    try {
      await deleteProject(deleteTarget.id);
      // If deleted project was active, clear selection
      if ($activeProject?.id === deleteTarget.id) {
        $activeProject = null;
      }
      showDeleteConfirm = false;
      deleteTarget = null;
      statusMessage = `✓ ${t('projects.projectDeleted')}`;
      await loadProjects();
    } catch (err) {
      $error = err.message;
    } finally {
      isDeleting = false;
    }
  }

  function selectProject(project) {
    $activeProject = { id: project.id, name: project.name };
  }
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('projects.title')}</h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
      onclick={openCreate}
    >
      + {t('projects.create')}
    </button>
  </div>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  {#if statusMessage}
    <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
      {statusMessage}
    </div>
  {/if}

  {#if isLoading}
    <div class="flex items-center justify-center h-32">
      <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
    </div>
  {:else if projects.length === 0}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 border border-gray-200 dark:border-gray-700 text-center">
      <p class="text-4xl mb-4">📁</p>
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">{t('projects.onboardingTitle')}</h3>
      <p class="text-gray-500 dark:text-gray-400 mb-6">{t('projects.onboardingMessage')}</p>
      <button
        class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        onclick={openCreate}
      >
        + {t('projects.create')}
      </button>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each projects as project}
        <div
          class="bg-white dark:bg-gray-800 rounded-lg shadow border transition-all
                 {$activeProject?.id === project.id
                   ? 'border-blue-500 ring-2 ring-blue-200 dark:ring-blue-800'
                   : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'}"
        >
          <div class="p-5">
            <div class="flex items-start justify-between mb-3">
              <div class="flex-1 min-w-0">
                <h3 class="text-lg font-semibold text-gray-800 dark:text-white truncate">
                  {project.name}
                  {#if project.is_system}
                    <span class="text-xs font-normal px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 ml-2">
                      {t('projects.systemProject')}
                    </span>
                  {/if}
                </h3>
                {#if project.description}
                  <p class="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                    {project.description}
                  </p>
                {/if}
              </div>
              {#if $activeProject?.id === project.id}
                <span class="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 flex-shrink-0 ml-2">
                  {t('config.active')}
                </span>
              {/if}
            </div>

            <div class="text-xs text-gray-400 dark:text-gray-500 space-y-1 mb-4">
              <p>{t('projects.createdAt')}: {formatDate(project.created_at)}</p>
              <p>{t('projects.updatedAt')}: {formatDate(project.updated_at)}</p>
            </div>

            <div class="flex items-center gap-2">
              {#if $activeProject?.id !== project.id}
                <button
                  class="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg
                         bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300
                         hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
                  onclick={() => selectProject(project)}
                >
                  {t('projects.selectProject')}
                </button>
              {:else}
                <button
                  class="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg
                         bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300
                         hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                  onclick={() => navigate('projects/' + project.id + '/settings')}
                >
                  ⚙️ {t('projects.settings')}
                </button>
              {/if}

              <button
                class="px-3 py-1.5 text-xs font-medium rounded-lg
                       text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                onclick={() => openEdit(project)}
              >
                {t('common.edit')}
              </button>

              {#if !project.is_system}
                <button
                  class="px-3 py-1.5 text-xs font-medium rounded-lg
                         text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  onclick={() => confirmDelete(project)}
                >
                  {t('common.delete')}
                </button>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- ============================================================ -->
<!-- MODAL: Create / Edit Project                                  -->
<!-- ============================================================ -->
{#if showModal}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeModal} role="dialog" aria-modal="true" tabindex="-1">
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg mx-4"
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {modalMode === 'create' ? t('projects.createTitle') : t('projects.editTitle')}
        </h3>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none"
          onclick={closeModal}
        >
          ✕
        </button>
      </div>

      <!-- Form -->
      <div class="px-6 py-4 space-y-4">
        <div>
          <label for="project-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('projects.name')} *
          </label>
          <input
            id="project-name"
            type="text"
            bind:value={formData.name}
            class="w-full px-3 py-2 border rounded-lg text-sm
              {formErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
              bg-white dark:bg-gray-700 text-gray-900 dark:text-white
              focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="My Project"
          />
          {#if formErrors.name}<p class="text-xs text-red-500 mt-1">{formErrors.name}</p>{/if}
        </div>

        <div>
          <label for="project-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('projects.description')}
          </label>
          <textarea
            id="project-desc"
            bind:value={formData.description}
            rows="3"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Optional project description..."
          ></textarea>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={closeModal}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? '...' : t('common.save')}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ============================================================ -->
<!-- DELETE CONFIRMATION DIALOG                                    -->
<!-- ============================================================ -->
{#if showDeleteConfirm && deleteTarget}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeDeleteConfirm} role="dialog" aria-modal="true" tabindex="-1">
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6"
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    >
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
        {t('projects.editTitle')}
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">
        {t('projects.deleteConfirm', { name: deleteTarget.name })}
      </p>
      <div class="flex items-center justify-end gap-3">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={closeDeleteConfirm}
          disabled={isDeleting}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleDelete}
          disabled={isDeleting}
        >
          {isDeleting ? '...' : t('common.delete')}
        </button>
      </div>
    </div>
  </div>
{/if}
