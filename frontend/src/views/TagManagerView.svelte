<script>
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { addToast } from '../lib/stores.js';
  import { getTags, createTag, updateTag, deleteTag } from '../lib/api/tag.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let tags = $state([]);
  let isLoading = $state(true);
  let showForm = $state(false);
  let editingTag = $state(null);
  let newName = $state('');
  let newColor = $state('#3b82f6');
  let newParentId = $state('');
  let isSaving = $state(false);
  let isDeleting = $state(false);
  let confirmDelete = $state(null);

  const COLOR_PRESETS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  ];

  let tagsLoaded = false;
  onMount(() => {
    if ($currentTenant) loadTags();
  });

  $effect(() => {
    if ($currentTenant) loadTags();
  });

  async function loadTags() {
    if (!$currentTenant) return;
    isLoading = true;
    try {
      tags = await getTags($currentTenant.id);
      tagsLoaded = true;
    } catch (err) {
      addToast({ type: 'error', message: err.message || t('tags.loadError') });
    } finally {
      isLoading = false;
    }
  }

  function openCreate() {
    showForm = true;
    editingTag = null;
    newName = '';
    newColor = '#3b82f6';
    newParentId = '';
  }

  function openEdit(tag) {
    showForm = true;
    editingTag = tag;
    newName = tag.name;
    newColor = tag.color || '#3b82f6';
    newParentId = tag.parent_id || '';
  }

  function cancelForm() {
    showForm = false;
    editingTag = null;
  }

  async function handleSave() {
    if (!newName.trim() || !$currentTenant || isSaving) return;
    isSaving = true;
    try {
      if (editingTag) {
        await updateTag($currentTenant.id, editingTag.tag_id, {
          name: newName.trim(),
          color: newColor,
          parent_id: newParentId || null,
        });
        addToast({ type: 'success', message: t('tags.updated') });
      } else {
        await createTag($currentTenant.id, {
          name: newName.trim(),
          color: newColor,
          parent_id: newParentId || null,
        });
        addToast({ type: 'success', message: t('tags.created') });
      }
      cancelForm();
      await loadTags();
    } catch (err) {
      addToast({ type: 'error', message: err.message || t('tags.saveError') });
    } finally {
      isSaving = false;
    }
  }

  async function handleDelete(tag) {
    if (!$currentTenant || isDeleting) return;
    isDeleting = true;
    const target = confirmDelete ?? tag;
    try {
      await deleteTag($currentTenant.id, target.tag_id);
      addToast({ type: 'success', message: t('tags.deleted') });
      confirmDelete = null;
      await loadTags();
    } catch (err) {
      addToast({ type: 'error', message: err.message || t('tags.deleteError') });
    } finally {
      isDeleting = false;
    }
  }

  let parentOptions = $derived(
    editingTag
      ? tags.filter((t) => t.tag_id !== editingTag.tag_id)
      : tags
  );
</script>

<div class="max-w-4xl mx-auto">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-800 dark:text-white">{t('tags.title')}</h1>
    <button
      class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      onclick={openCreate}
    >
      + {t('tags.create')}
    </button>
  </div>

  <!-- Create / Edit form -->
  {#if showForm}
    <div class="mb-6 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        {editingTag ? t('tags.editTitle') : t('tags.createTitle')}
      </h2>
      <div class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('tags.name')}</label>
          <input
            type="text"
            bind:value={newName}
            class="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('tags.color')}</label>
          <div class="flex items-center gap-2">
            <input type="color" bind:value={newColor} class="w-10 h-10 rounded cursor-pointer border dark:border-gray-600" />
            <div class="flex gap-1.5">
              {#each COLOR_PRESETS as preset}
                <button
                  class="w-6 h-6 rounded-full border border-gray-300 dark:border-gray-600 transition-transform hover:scale-110 {newColor === preset ? 'ring-2 ring-offset-1 ring-blue-500 dark:ring-offset-gray-800' : ''}"
                  style="background-color: {preset}"
                  onclick={() => newColor = preset}
                />
              {/each}
            </div>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('tags.parentTag')}</label>
          <select
            bind:value={newParentId}
            class="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
          >
            <option value="">—</option>
            {#each parentOptions as tag}
              <option value={tag.tag_id}>{tag.name}</option>
            {/each}
          </select>
        </div>
        <div class="flex gap-2">
          <button
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            onclick={handleSave}
            disabled={isSaving || !newName.trim()}
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

  <!-- Tag list -->
  {#if isLoading}
    <div class="text-center py-12 text-gray-500">{t('common.loading')}</div>
  {:else if tags.length === 0}
    <div class="text-center py-12 text-gray-500">{t('tags.noTags')}</div>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {#each tags as tag}
        <div class="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div class="flex items-center gap-2 mb-2">
            <span
              class="inline-block w-4 h-4 rounded-full flex-shrink-0"
              style="background-color: {tag.color || '#e5e7eb'}"
            />
            <span class="font-medium text-gray-800 dark:text-white">{tag.name}</span>
          </div>
          {#if tag.parent_id}
            {@const parent = tags.find((t) => t.tag_id === tag.parent_id)}
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
              ← {parent ? parent.name : tag.parent_id}
            </p>
          {/if}
          <div class="flex gap-1 mt-2">
            <button
              class="px-2 py-1 text-xs border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:border-gray-600 transition-colors"
              onclick={() => openEdit(tag)}
            >
              {t('common.edit')}
            </button>
            <button
              class="px-2 py-1 text-xs border rounded text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 dark:border-gray-600 transition-colors"
              onclick={() => confirmDelete = tag}
            >
              {t('common.delete')}
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
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">{t('tags.confirmDelete', { name: confirmDelete.name })}</h3>
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">{t('tags.deleteConfirm')}</p>
        <div class="flex gap-2 justify-end">
          <button class="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 dark:border-gray-600 transition-colors" onclick={() => confirmDelete = null} disabled={isDeleting}>
            {t('common.cancel')}
          </button>
          <button class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50" onclick={() => handleDelete(confirmDelete)} disabled={isDeleting}>
            {isDeleting ? t('common.loading') : t('common.delete')}
          </button>
        </div>
      </div>
    </div>
  {/if}
