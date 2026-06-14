<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { activeCase, addToast } from '../lib/stores.js';
  import { getCases, createCase, updateCase, deleteCase } from '../lib/api/case.js';
  import TagPicker from '../components/TagPicker.svelte';

  let { navigate } = $props();

  let t = $derived($tStore);

  let cases = $state([]);
  let isLoading = $state(true);
  let showCreateForm = $state(false);
  let editingCase = $state(null);
  let newTitle = $state('');
  let newDescription = $state('');
  let newTags = $state([]);
  let isSaving = $state(false);
  let confirmDelete = $state(null);

  onMount(() => {
    if ($currentTenant) loadCases();
  });

  $effect(() => {
    if ($currentTenant) loadCases();
  });

  async function loadCases() {
    if (!$currentTenant) return;
    isLoading = true;
    try {
      cases = await getCases($currentTenant.id);
    } catch (err) {
      if (import.meta.env.DEV) console.warn('Failed to load cases:', err);
    } finally {
      isLoading = false;
    }
  }

  function openCreate() {
    showCreateForm = true;
    editingCase = null;
    newTitle = '';
    newDescription = '';
    newTags = [];
  }

  function openEdit(c) {
    showCreateForm = true;
    editingCase = c;
    newTitle = c.title;
    newDescription = c.description || '';
    newTags = c.tags || [];
  }

  function cancelForm() {
    showCreateForm = false;
    editingCase = null;
    newTitle = '';
    newDescription = '';
    newTags = [];
  }

  async function handleSave() {
    if (import.meta.env.DEV) console.debug('[CasesView] handleSave:', { newTitle: newTitle.trim(), editingCase: !!editingCase, tenant: $currentTenant });
    if (!newTitle.trim() || !$currentTenant) return;
    isSaving = true;
    try {
      if (editingCase) {
        await updateCase($currentTenant.id, editingCase.id, {
          title: newTitle.trim(),
          description: newDescription.trim(),
          tags: newTags,
        });
      } else {
        const c = await createCase($currentTenant.id, {
          title: newTitle.trim(),
          description: newDescription.trim(),
          tags: newTags,
        });
        activeCase.set({ id: c.id, title: c.title });
        addToast({ message: t('cases.caseCreated'), type: 'success' });
      }
      cancelForm();
      await loadCases();
    } catch (err) {
      addToast({ type: 'error', message: t('cases.saveFailed', { error: err.message }) });
    } finally {
      isSaving = false;
    }
  }

  async function handleDelete(c) {
    if (!$currentTenant) return;
    confirmDelete = null;
    try {
      await deleteCase($currentTenant.id, c.id);
      if ($activeCase?.id === c.id) activeCase.set(null);
      await loadCases();
    } catch (err) {
      addToast({ type: 'error', message: t('cases.deleteFailed', { error: err.message }) });
    }
  }

  function selectCase(c) {
    activeCase.set({ id: c.id, title: c.title });
  }

  /**
   * Case-Space Phase 5.6: clicking a row's "Open in Workspace"
   * button sets the active case and navigates to the Workspace
   * view, where the user can manage it (edit, delete, tag, etc.).
   */
  function openInWorkspace(c) {
    if (!c) return;
    activeCase.set({ id: c.id, title: c.title });
    if (typeof navigate === 'function') {
      navigate('workspace');
    } else if (typeof window !== 'undefined') {
      window.location.hash = '#/workspace';
    }
  }
</script>

<div class="max-w-4xl mx-auto p-6 text-gray-900 dark:text-gray-100">
  <!-- Case-Space Phase 5.6 banner: explain that the workspace
       is the new home, and offer a "Switch to the Workspace"
       button so power-users can still find this read-only view. -->
  <div
    class="mb-4 p-3 border rounded-md
           bg-blue-50 dark:bg-blue-900/20
           border-blue-200 dark:border-blue-700
           text-blue-900 dark:text-blue-100"
    role="status"
  >
    <div class="flex items-start gap-2">
      <span aria-hidden="true">💡</span>
      <div class="flex-1 text-sm">
        <p class="font-medium">
          {t('caseSpace.migration.caseSpaceBannerTitle') ??
            'Case management has moved to the Workspace.'}
        </p>
        <p>
          {t('caseSpace.migration.caseSpaceBannerBody') ??
            'For day-to-day work (creating / editing / deleting cases, switching the active case) please use the new Workspace view. This page is kept for quick reference only.'}
        </p>
      </div>
      <button
        type="button"
        class="shrink-0 inline-flex items-center px-3 py-1.5 rounded-md
               bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium
               focus:outline-none focus:ring-2 focus:ring-blue-500"
        data-testid="go-to-workspace"
        onclick={() => navigate?.('workspace')}
      >
        {t('caseSpace.migration.openWorkspace') ?? 'Open Workspace →'}
      </button>
    </div>
  </div>

  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{t('cases.title')}</h1>
    <button
      class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700
             focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
      onclick={openCreate}
    >
      + {t('cases.create')}
    </button>
  </div>

  <!-- Create / Edit form -->
  {#if showCreateForm}
    <div class="mb-6 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        {editingCase ? t('cases.editTitle') : t('cases.createTitle')}
      </h2>
      <div class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('cases.title_label')}</label>
          <input
            type="text"
            bind:value={newTitle}
            class="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('cases.description')}</label>
          <textarea
            bind:value={newDescription}
            rows="3"
            class="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
          ></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('cases.tags')}</label>
          <TagPicker bind:value={newTags} />
        </div>
        <div class="flex gap-2">
          <button
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600 disabled:opacity-50 transition-colors"
            onclick={handleSave}
            disabled={isSaving || !newTitle.trim()}
          >
            {isSaving ? t('common.loading') : t('common.save')}
          </button>
          <button
            class="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 dark:border-gray-600 transition-colors"
            onclick={cancelForm}
          >
            {t('common.cancel')}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Case list -->
  {#if isLoading}
    <div class="text-center py-12 text-gray-500">{t('common.loading')}</div>
  {:else if cases.length === 0}
    <div class="text-center py-12 text-gray-500">{t('cases.noCases')}</div>
  {:else}
    <div class="space-y-2">
      {#each cases as c}
        <div
          class="flex items-center justify-between p-4
                 bg-white dark:bg-gray-800
                 border border-gray-200 dark:border-gray-700
                 rounded-lg hover:shadow-sm transition-shadow cursor-pointer
                 {$activeCase?.id === c.id ? 'ring-2 ring-blue-400 dark:ring-blue-500' : ''}"
          onclick={() => openInWorkspace(c)}
        >
          <div class="flex-1 min-w-0">
            <h3 class="font-medium text-gray-800 dark:text-white truncate">{c.title}</h3>
            {#if c.description}
              <p class="text-sm text-gray-500 dark:text-gray-400 truncate mt-0.5">{c.description}</p>
            {/if}
            {#if c.tags && c.tags.length > 0}
              <div class="flex gap-1 mt-1.5 flex-wrap">
                {#each c.tags as tagId}
                  <span class="px-1.5 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{tagId.slice(0, 8)}…</span>
                {/each}
              </div>
            {/if}
          </div>
          <div class="flex items-center gap-2 ml-4">
            {#if $activeCase?.id === c.id}
              <span
                class="px-2 py-0.5 text-xs rounded-full
                       bg-blue-100 dark:bg-blue-900/40
                       text-blue-800 dark:text-blue-200 font-medium"
              >
                {t('cases.activeCase')}
              </span>
            {/if}
            <button
              type="button"
              class="shrink-0 px-3 py-1 text-xs font-medium rounded-md
                     bg-blue-600 hover:bg-blue-700 text-white
                     focus:outline-none focus:ring-2 focus:ring-blue-500
                     transition-colors"
              data-testid="open-in-workspace"
              onclick={(e) => { e.stopPropagation(); openInWorkspace(c); }}
            >
              {t('caseSpace.migration.openInWorkspace') ??
                'Open in Workspace →'}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Delete confirmation modal -->
{#if confirmDelete}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onclick={() => confirmDelete = null}>
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-md mx-4" onclick={(e) => e.stopPropagation()}>
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">{t('cases.confirmDelete', { name: confirmDelete.title })}</h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">{t('cases.deleteConfirm')}</p>
      <div class="flex gap-2 justify-end">
        <button class="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 dark:border-gray-600 transition-colors" onclick={() => confirmDelete = null}>
          {t('common.cancel')}
        </button>
        <button class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors" onclick={() => handleDelete(confirmDelete)}>
          {t('common.delete')}
        </button>
      </div>
    </div>
  </div>
{/if}
