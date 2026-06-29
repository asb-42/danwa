<script>
  /**
   * TagPicker — inline multi-select tag component.
   * Allows selecting existing tags and creating new ones on the fly.
   */
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { addToast } from '../lib/stores.js';
  import { getTags, createTag } from '../lib/api/tag.js';

  // onchange default is a no-op wrapper so a parent that forgets
  // to wire it produces a visible runtime error in dev builds
  // (TypeError: onchange is not a function) instead of silently
  // doing nothing.  See InboxView line ~471 (must use lowercase
  // 'onchange' to match this prop name -- Svelte 5 is
  // case-sensitive for $props() destructuring).
  let { value = [], onchange = () => { throw new TypeError('TagPicker: parent did not bind onchange'); }, caseId = null } = $props();

  let t = $derived($tStore);

  let tags = $state([]);
  let caseTags = $state([]); // Top-N tags from the active case (Phase 3.5)
  let search = $state('');
  let isOpen = $state(false);
  let isCreating = $state(false);
  let suggestionsDismissed = $state(false);

  onMount(() => {
    if ($currentTenant) loadTags();
    if (caseId && $currentTenant) loadCaseTags(caseId);
  });

  $effect(() => {
    if ($currentTenant) loadTags();
  });

  $effect(() => {
    // Reload case-tag suggestions when the active case changes.
    if (caseId && $currentTenant) {
      loadCaseTags(caseId);
    } else {
      caseTags = [];
    }
  });

  async function loadTags() {
    if (!$currentTenant) return;
    try {
      tags = await getTags($currentTenant.id);
    } catch (err) {
      if (import.meta.env.DEV) console.warn('Failed to load tags:', err);
    }
  }

  /**
   * Phase 3.5: load the active case's tags and surface the top 3
   * as one-click "Suggested tags" buttons above the main tag list.
   * Dismissed as soon as the user picks a tag manually.
   */
  async function loadCaseTags(cid) {
    try {
      const mod = await import('../lib/api/case.js');
      const c = await mod.getCase($currentTenant.id, cid);
      const ids = (c?.tag_ids || c?.tags || []).slice(0, 3);
      // Resolve to full tag objects from the already-loaded list.
      caseTags = ids
        .map((id) => tags.find((t) => t.id === id) || { id, name: id })
        .filter(Boolean);
    } catch (err) {
      if (import.meta.env.DEV) console.warn('Failed to load case tags:', err);
      caseTags = [];
    }
  }

  let visibleSuggestions = $derived(
    !suggestionsDismissed &&
      caseTags.length > 0 &&
      value.length === 0 &&
      search === ''
  );

  let filtered = $derived(
    search
      ? tags.filter((t) => t.name.toLowerCase().includes(search.toLowerCase()))
      : tags
  );

  let newTagName = $derived(
    search && !tags.some((t) => t.name.toLowerCase() === search.toLowerCase())
      ? search
      : null
  );

  function isSelected(tag) {
    return value.some((v) => (typeof v === 'string' ? v === tag.id : v === tag.id));
  }

  function toggleTag(tag) {
    const selected = isSelected(tag)
      ? value.filter((v) => (typeof v === 'string' ? v !== tag.id : v !== tag.id))
      : [...value, tag.id];
    // Once the user manually picks any tag, hide the suggestions
    // strip (they have expressed intent).
    if (selected.length > 0) suggestionsDismissed = true;
    onchange?.(selected);
  }

  function removeTag(tagId) {
    onchange?.(value.filter((v) => (typeof v === 'string' ? v !== tagId : v !== tagId)));
  }

  async function handleCreateNew() {
    if (!search.trim() || !$currentTenant) return;
    isCreating = true;
    try {
      const newTag = await createTag($currentTenant.id, { name: search.trim() });
      tags = [...tags, newTag];
      onchange?.([...value, newTag.id]);
      search = '';
      isOpen = false;
      addToast({ type: 'success', message: t('tags.created', { name: newTag.name }) });
    } catch (err) {
      addToast({ type: 'error', message: t('tags.createFailed', { error: err.message }) });
    } finally {
      isCreating = false;
    }
  }

  function handleClickOutside(event) {
    if (!event.target.closest('.tag-picker')) {
      isOpen = false;
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="tag-picker relative">
  <!-- Suggested tags from the active case (Phase 3.5) -->
  {#if visibleSuggestions}
    <div
      class="suggested-tags flex flex-wrap items-center gap-1 px-2 py-1.5 mb-1"
      data-testid="tag-picker-suggestions"
    >
      <span class="text-[0.7rem] uppercase tracking-wider
                   text-gray-500 dark:text-gray-400">
        {t?.caseSpace?.newDebate?.suggestedTags ?? 'Suggested from this case'}:
      </span>
      {#each caseTags as tag (tag.id)}
        <button
          type="button"
          data-testid="tag-picker-suggested-tag"
          class="text-xs font-medium px-2 py-0.5 rounded
                 border-0
                 hover:opacity-80 transition-opacity
                 focus:outline-none focus:ring-2 focus:ring-blue-500"
          style="background-color: {tag.color || '#e5e7eb'};
                 color: {tag.color ? '#fff' : '#374151'};"
          onclick={() => toggleTag(tag)}
        >
          + {tag.name}
        </button>
      {/each}
      <button
        type="button"
        class="text-[0.7rem] text-gray-400 dark:text-gray-500
               hover:text-gray-600 dark:hover:text-gray-300 ml-1
               bg-transparent border-0
               focus:outline-none focus:ring-2 focus:ring-blue-500"
        onclick={() => (suggestionsDismissed = true)}
      >
        ✕
      </button>
    </div>
  {/if}

  <!-- Selected tags -->
  <div
    class="flex flex-wrap gap-1 px-2 py-1.5 border rounded cursor-text min-h-[32px]
           bg-white dark:bg-gray-800 dark:border-gray-600
           {isOpen ? 'border-blue-400 dark:border-blue-500' : 'border-gray-300'}"
    onclick={() => isOpen = true}
  >
    {#each value as tagId}
      {@const tag = tags.find((t) => t.id === tagId)}
      {#if tag}
        <span
          class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium"
          style="background-color: {tag.color || '#e5e7eb'}; color: {tag.color ? '#fff' : '#374151'}"
        >
          {tag.name}
          <button
            class="hover:opacity-70 leading-none"
            onclick={(e) => { e.stopPropagation(); removeTag(tagId); }}
          >&times;</button>
        </span>
      {/if}
    {/each}
    {#if !isOpen}
      <span class="text-xs text-gray-400 self-center">{value.length === 0 ? t('tags.title') : ''}</span>
    {/if}
  </div>

  {#if isOpen}
    <div
      class="absolute left-0 right-0 z-50 mt-1 bg-white dark:bg-gray-800 rounded-lg shadow-lg
             border border-gray-200 dark:border-gray-700 max-h-48 overflow-y-auto"
    >
      <!-- Search input -->
      <div class="px-2 py-1.5 border-b border-gray-200 dark:border-gray-700">
        <input
          type="text"
          bind:value={search}
          placeholder={t('tags.searchPlaceholder')}
          class="w-full px-2 py-1 text-sm border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
          onkeydown={(e) => {
            if (e.key === 'Enter' && newTagName) handleCreateNew();
            if (e.key === 'Escape') isOpen = false;
          }}
        />
      </div>

      {#if filtered.length > 0}
        {#each filtered as tag}
          <button
            class="w-full text-left px-3 py-1.5 text-sm flex items-center gap-2
                   hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors
                   {isSelected(tag) ? 'bg-blue-50 dark:bg-blue-900/20' : ''}"
            onclick={() => toggleTag(tag)}
          >
            <span
              class="inline-block w-3 h-3 rounded-full flex-shrink-0"
              style="background-color: {tag.color || '#e5e7eb'}"
            />
            <span class="flex-1">{tag.name}</span>
            {#if isSelected(tag)}
              <span class="text-blue-600 text-xs">✓</span>
            {/if}
          </button>
        {/each}
      {:else if tags.length === 0}
        <div class="px-3 py-2 text-sm text-gray-500">{t('tags.noTags')}</div>
      {/if}

      {#if newTagName}
        <button
          class="w-full text-left px-3 py-1.5 text-sm text-blue-600 dark:text-blue-400 border-t border-gray-200 dark:border-gray-700 hover:bg-blue-50 disabled:hover:bg-blue--50 dark:hover:bg-blue-900 disabled:hover:bg-blue-800/20 transition-colors disabled:opacity-50"
          onclick={handleCreateNew}
          disabled={isCreating}
        >
          + {t('tags.create')} "{newTagName}"
        </button>
      {/if}
    </div>
  {/if}
</div>
