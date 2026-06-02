<script>
  import { formatDate, tStore } from '../../lib/i18n/index.js';

  let {
    workflows = [],
    onRefresh = () => {},
    onDelete = () => {},
    onClone = () => {},
    onCompile = () => {},
    onOpenCanvas = () => {},
  } = $props();

  let t = $derived($tStore);

  let search = $state('');
  let dropdownOpen = $state(null);

  let filteredWorkflows = $derived(() => {
    const q = search.toLowerCase().trim();
    let list = [...workflows];
    if (q) {
      list = list.filter(w =>
        w.name?.toLowerCase().includes(q) ||
        w.id?.toLowerCase().includes(q) ||
        (w.description || '').toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    return list;
  });

  function toggleDropdown(wfId) {
    dropdownOpen = dropdownOpen === wfId ? null : wfId;
  }

  function handleDocClick() {
    dropdownOpen = null;
  }

  function formatCreatedAt(dateStr) {
    if (!dateStr) return '—';
    try {
      return formatDate(dateStr, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return dateStr; }
  }

  function getTemplateLabel(wf) {
    return wf.template_id || '—';
  }
</script>

<svelte:window onclick={handleDocClick} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleDocClick(e); }}} />

<div class="space-y-4">
  <div class="flex items-center justify-between gap-4">
    <div class="relative flex-1 max-w-md">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">🔍</span>
      <input type="text" bind:value={search}
        placeholder="{t('config.search') || 'Search'}… (Name, ID)"
        class="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
      {#if search}
        <button class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" onclick={() => { search = ''; }}>✕</button>
      {/if}
    </div>
    <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap" onclick={onRefresh}>
      🔄 {t('common.refresh') || 'Refresh'}
    </button>
  </div>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
    {#if workflows.length === 0}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('manage.workflows.empty') || 'No saved workflows yet. Instantiate a template on the Canvas to create one.'}</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
            <tr>
              <th class="px-4 py-3">{t('config.name') || 'Name'}</th>
              <th class="px-4 py-3">{t('config.description') || 'Description'}</th>
              <th class="px-4 py-3">{t('manage.workflows.version') || 'Version'}</th>
              <th class="px-4 py-3">{t('manage.workflows.template') || 'Template'}</th>
              <th class="px-4 py-3">{t('manage.workflows.created') || 'Created'}</th>
              <th class="px-4 py-3 text-right">{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredWorkflows() as wf (wf.id)}
              <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                <td class="px-4 py-3 font-medium text-gray-900 dark:text-white">
                  <span class="truncate max-w-[200px] block" title={wf.name}>{wf.name}</span>
                </td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
                  <span class="truncate max-w-[250px] block" title={wf.description || ''}>{wf.description || '—'}</span>
                </td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">v{wf.version ?? 1}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{getTemplateLabel(wf)}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400 whitespace-nowrap">{formatCreatedAt(wf.created_at)}</td>
                <td class="px-4 py-3 text-right relative">
                  <button
                    class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                    onclick={(e) => { e.stopPropagation(); toggleDropdown(wf.id); }}
                    title={t('common.actions')}
                  >
                    ⋮
                  </button>
                  {#if dropdownOpen === wf.id}
                    <div class="absolute right-0 top-full mt-1 z-20 w-48 bg-white dark:bg-gray-700 rounded-lg shadow-lg border border-gray-200 dark:border-gray-600 py-1 text-sm" onclick={(e) => e.stopPropagation()}>
                      <button
                        class="w-full text-left px-4 py-2 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                        onclick={() => { onOpenCanvas(wf.id); dropdownOpen = null; }}>
                        🧩 {t('manage.workflows.openCanvas') || 'Open in Canvas'}
                      </button>
                      <button
                        class="w-full text-left px-4 py-2 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                        onclick={() => { onCompile(wf.id); dropdownOpen = null; }}>
                        ✓ {t('blueprint.workflow.compile') || 'Compile'}
                      </button>
                      <button
                        class="w-full text-left px-4 py-2 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                        onclick={() => { onClone(wf.id); dropdownOpen = null; }}>
                        📋 {t('blueprint.workflow.clone') || 'Clone'}
                      </button>
                      <hr class="border-gray-200 dark:border-gray-600 my-1">
                      <button
                        class="w-full text-left px-4 py-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30"
                        onclick={() => { onDelete(wf.id, wf.name); dropdownOpen = null; }}>
                        🗑 {t('common.delete')}
                      </button>
                    </div>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700">
        {filteredWorkflows().length} / {workflows.length} {t('manage.workflows.workflows') || 'Workflows'}
      </div>
    {/if}
  </div>
</div>

<style>
  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
