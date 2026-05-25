<script>
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import {
    getModules,
    getModuleProfile,
    updateModuleProfile,
    duplicateModule,
    uninstallModule,
    exportModule,
    translateModule,
    enableModule,
    disableModule,
  } from '../lib/api.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let { filterCategory } = $props();

  let modules = $state([]);
  let isLoading = $state(false);
  let statusMessage = $state('');
  let error = $state(null);

  let editModalOpen = $state(false);
  let editingModule = $state(null);
  let editForm = $state({});
  let editProfileType = $state('');
  let editSaving = $state(false);
  let editError = $state(null);

  const TRANSLATABLE_TYPES = ['role-type', 'agent-persona', 'tone-profile', 'prompt-variant'];
  const CATEGORY_ORDER = ['llm-profiles', 'role-types', 'agents', 'prompts', 'tone-profiles', 'workflows', 'translations'];
  const CATEGORY_LABELS = {
    'agents': 'Agent Cores',
    'llm-profiles': 'LLM Profiles',
    'role-types': 'Role Types',
    'tone-profiles': 'Tone Profiles',
    'prompts': 'Argumentation Patterns',
    'workflows': 'Workflows',
    'translations': '🌐 Translations',
  };

  const filteredModules = $derived(
    filterCategory
      ? modules.filter(m => (m.category || 'other') === filterCategory)
      : modules
  );

  const groupedModules = $derived.by(() => {
    const groups = {};
    const source = filterCategory ? filteredModules : modules;
    for (const m of source) {
      const cat = m.category || 'other';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(m);
    }
    if (filterCategory) {
      return Object.entries(groups);
    }
    const ordered = [];
    for (const cat of CATEGORY_ORDER) {
      if (groups[cat]) ordered.push([cat, groups[cat]]);
    }
    const remaining = Object.keys(groups)
      .filter(k => !CATEGORY_ORDER.includes(k))
      .sort();
    for (const cat of remaining) {
      ordered.push([cat, groups[cat]]);
    }
    return ordered;
  });

  onMount(async () => {
    await loadModules();
  });

  async function loadModules() {
    isLoading = true;
    error = null;
    try {
      modules = await getModules();
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function openEdit(mod) {
    try {
      const profile = await getModuleProfile(mod.module_id);
      if (!profile) return;
      editingModule = mod;
      editProfileType = mod.type || '';
      if (mod.type === 'language-pack') {
        editForm = {
          locale: mod.language || '',
          source_locale: 'en',
          key_count: profile ? Object.keys(profile).length : 0,
          coverage: profile ? `${Object.keys(profile).length} keys` : '0 keys',
        };
      } else {
        editForm = { ...profile };
      }
      editError = null;
      editModalOpen = true;
    } catch (e) {
      error = e.message;
    }
  }

  function closeEdit() {
    editModalOpen = false;
    editingModule = null;
    editForm = {};
    editProfileType = '';
    editError = null;
  }

  async function saveEdit() {
    if (!editingModule) return;
    if (editingModule.type === 'language-pack') {
      closeEdit();
      return;
    }
    editSaving = true;
    editError = null;
    try {
      await updateModuleProfile(editingModule.module_id, editForm);
      statusMessage = 'Profile saved';
      closeEdit();
      await loadModules();
    } catch (e) {
      editError = e.message;
    } finally {
      editSaving = false;
    }
  }

  async function handleDuplicate(mod) {
    const newId = prompt(`New module ID (based on "${mod.module_id}"):`, mod.module_id + '-copy');
    if (!newId || !newId.trim()) return;
    try {
      await duplicateModule(mod.module_id, newId.trim());
      statusMessage = `Duplicated to ${newId.trim()}`;
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleDelete(mod) {
    if (!confirm(`Delete "${mod.name?.en || mod.module_id}"? This cannot be undone.`)) return;
    try {
      await uninstallModule(mod.module_id);
      statusMessage = `Deleted ${mod.module_id}`;
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleExport(mod) {
    try {
      const url = await exportModule(mod.module_id);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${mod.module_id}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      statusMessage = `Exported ${mod.module_id}`;
    } catch (e) {
      error = e.message;
    }
  }

  async function handleTranslate(mod) {
    const targetLang = prompt('Target language code (e.g. de, fr, es):', 'de');
    if (!targetLang || !targetLang.trim()) return;
    try {
      await translateModule(mod.module_id, { target_language: targetLang.trim(), force: false, auto_approve: true });
      statusMessage = `Translation queued for ${mod.module_id} → ${targetLang.trim()}`;
    } catch (e) {
      error = e.message;
    }
  }

  async function handleEnable(mod) {
    try {
      await enableModule(mod.module_id);
      statusMessage = `Enabled ${mod.module_id}`;
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleDisable(mod) {
    try {
      await disableModule(mod.module_id);
      statusMessage = `Disabled ${mod.module_id}`;
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  function updateField(field, value) {
    editForm = { ...editForm, [field]: value };
  }

  function formFields() {
    const type = editProfileType;
    if (type === 'llm-profile') {
      return [
        { key: 'name', label: 'Name', type: 'text' },
        { key: 'provider', label: 'Provider', type: 'text' },
        { key: 'model', label: 'Model', type: 'text' },
        { key: 'protocol', label: 'Protocol', type: 'text' },
        { key: 'api_base', label: 'API Base', type: 'text' },
        { key: 'api_key_env', label: 'API Key Env Var', type: 'text' },
        { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
        { key: 'context_window', label: 'Context Window', type: 'number' },
        { key: 'temperature', label: 'Temperature', type: 'number', step: 0.1 },
        { key: 'timeout', label: 'Timeout (s)', type: 'number' },
        { key: 'cost_per_1k_input', label: 'Cost / 1K Input ($)', type: 'number', step: 0.001 },
        { key: 'cost_per_1k_output', label: 'Cost / 1K Output ($)', type: 'number', step: 0.001 },
        { key: 'fallback_llm_profile_id', label: 'Fallback LLM', type: 'text' },
        { key: 'a2a_endpoint', label: 'A2A Endpoint', type: 'text' },
        { key: 'a2a_timeout', label: 'A2A Timeout (s)', type: 'number' },
      ];
    }
    if (type === 'agent-persona') {
      return [
        { key: 'name', label: 'Name', type: 'text' },
        { key: 'role', label: 'Role', type: 'text' },
        { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
        { key: 'llm_profile_id', label: 'LLM Profile', type: 'text' },
        { key: 'max_rounds', label: 'Max Rounds', type: 'number' },
        { key: 'consensus_threshold', label: 'Consensus Threshold', type: 'number', step: 0.1 },
        { key: 'description', label: 'Description', type: 'text' },
      ];
    }
    if (type === 'role-type') {
      return [
        { key: 'name', label: 'Name', type: 'text' },
        { key: 'description', label: 'Description', type: 'text' },
        { key: 'icon', label: 'Icon', type: 'text' },
        { key: 'color', label: 'Color', type: 'color' },
        { key: 'default_max_rounds', label: 'Default Max Rounds', type: 'number' },
        { key: 'default_consensus_threshold', label: 'Default Consensus', type: 'number', step: 0.1 },
        { key: 'category', label: 'Category', type: 'text' },
        { key: 'is_active', label: 'Active', type: 'checkbox' },
      ];
    }
    if (type === 'tone-profile') {
      return [
        { key: 'name', label: 'Name', type: 'text' },
        { key: 'description', label: 'Description', type: 'text' },
        { key: 'style', label: 'Style', type: 'text' },
        { key: 'formality', label: 'Formality (0-1)', type: 'number', step: 0.1, min: 0, max: 1 },
        { key: 'verbosity', label: 'Verbosity', type: 'text' },
        { key: 'emotional_valence', label: 'Emotional Valence (-1 to 1)', type: 'number', step: 0.1, min: -1, max: 1 },
        { key: 'rhetorical_mode', label: 'Rhetorical Mode', type: 'text' },
        { key: 'custom_instructions', label: 'Custom Instructions', type: 'textarea' },
      ];
    }
    if (type === 'workflow-template') {
      return [
        { key: 'name', label: 'Name', type: 'text' },
        { key: 'description', label: 'Description', type: 'textarea' },
        { key: 'category', label: 'Category', type: 'text' },
        { key: 'is_system', label: 'System Template', type: 'checkbox' },
      ];
    }
    if (type === 'prompt-variant') {
      return [
        { key: 'content', label: 'Prompt Content (Markdown)', type: 'markdown' },
      ];
    }
    if (type === 'language-pack') {
      return [
        { key: 'locale', label: 'Locale', type: 'text', readonly: true },
        { key: 'source_locale', label: 'Source Locale', type: 'text', readonly: true },
        { key: 'key_count', label: 'Translation Keys', type: 'number', readonly: true },
        { key: 'coverage', label: 'Coverage', type: 'text', readonly: true },
      ];
    }
    return [];
  }

  function inputClass() {
    return 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent';
  }

  function labelClass() {
    return 'block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1';
  }
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
      {t('modules.title') || 'Modules'}
    </h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-50"
      onclick={loadModules}
      disabled={isLoading}
    >
      {isLoading ? t('common.loading') : '🔄 ' + (t('modules.refresh') || 'Refresh')}
    </button>
  </div>

  {#if error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {error}
      <button class="ml-2 text-blue-600 underline" onclick={() => error = null}>{t('common.dismiss')}</button>
    </div>
  {/if}

  {#if statusMessage}
    <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
      {statusMessage}
      <button class="ml-2 text-blue-600 underline" onclick={() => statusMessage = ''}>{t('common.dismiss')}</button>
    </div>
  {/if}

  {#if isLoading && modules.length === 0}
    <div class="flex items-center justify-center h-32">
      <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
    </div>
  {:else if modules.length === 0}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 text-center">
      <p class="text-gray-500 dark:text-gray-400">{t('modules.noInstalled') || 'No modules found'}</p>
    </div>
  {:else}
    {#each groupedModules as [category, mods]}
      <div>
        {#if !filterCategory}
          <h3 class="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2 pb-1 border-b border-gray-200 dark:border-gray-700">
            {CATEGORY_LABELS[category] || category}
            <span class="text-sm font-normal text-gray-400 ml-2">({mods.length})</span>
          </h3>
        {/if}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-gray-50 dark:bg-gray-750 border-b border-gray-200 dark:border-gray-700">
                  <th class="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Name</th>
                  <th class="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Type</th>
                  <th class="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Version</th>
                  <th class="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Tags</th>
                  <th class="text-right px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each mods as mod (mod.module_id)}
                  <tr class="border-b border-gray-100 dark:border-gray-700 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors {mod.enabled === false ? 'opacity-50' : ''}">
                    <td class="px-4 py-2.5">
                      <span class="font-medium text-gray-800 dark:text-white">{mod.name?.en || mod.module_id}</span>
                      {#if mod.enabled === false}
                        <span class="ml-1 text-xs bg-gray-200 dark:bg-gray-600 text-gray-500 dark:text-gray-400 px-1.5 py-0.5 rounded">disabled</span>
                      {/if}
                    </td>
                    <td class="px-4 py-2.5">
                      <span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{mod.type || '—'}</span>
                    </td>
                    <td class="px-4 py-2.5 text-gray-500 dark:text-gray-400">v{mod.version || '0.0.0'}</td>
                    <td class="px-4 py-2.5">
                      <div class="flex flex-wrap gap-1">
                        {#each (mod.tags || []) as tag}
                          <span class="text-xs px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">{tag}</span>
                        {/each}
                        {#if !mod.tags || mod.tags.length === 0}
                          <span class="text-gray-400 dark:text-gray-500">—</span>
                        {/if}
                      </div>
                    </td>
                    <td class="px-4 py-2.5 text-right">
                      <div class="flex items-center justify-end gap-1">
                        {#if mod.enabled !== false}
                          <button
                            class="px-2.5 py-1 text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors"
                            onclick={() => handleDisable(mod)}
                            title="Disable module"
                          >
                            Disable
                          </button>
                        {:else}
                          <button
                            class="px-2.5 py-1 text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors"
                            onclick={() => handleEnable(mod)}
                            title="Enable module"
                          >
                            Enable
                          </button>
                        {/if}
                        <button
                          class="px-2.5 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                          onclick={() => openEdit(mod)}
                        >
                          Edit
                        </button>
                        <button
                          class="px-2.5 py-1 text-xs bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
                          onclick={() => handleDuplicate(mod)}
                        >
                          Duplicate
                        </button>
                        <button
                          class="px-2.5 py-1 text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded hover:bg-purple-200 dark:hover:bg-purple-900/50 transition-colors"
                          onclick={() => handleExport(mod)}
                        >
                          Export
                        </button>
                        {#if TRANSLATABLE_TYPES.includes(mod.type)}
                          <button
                            class="px-2.5 py-1 text-xs bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded hover:bg-indigo-200 dark:hover:bg-indigo-900/50 transition-colors"
                            onclick={() => handleTranslate(mod)}
                          >
                            Translate
                          </button>
                        {/if}
                        <button
                          class="px-2.5 py-1 text-xs bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
                          onclick={() => handleDelete(mod)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    {/each}
  {/if}
</div>

{#if editModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeEdit}>
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col m-4"
      onclick={(e) => e.stopPropagation()}
      role="dialog"
      aria-modal="true"
    >
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          Edit: {editingModule?.name?.en || editingModule?.module_id}
        </h3>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none"
          onclick={closeEdit}
        >
          &times;
        </button>
      </div>

      <div class="px-6 py-4 overflow-y-auto flex-1">
        {#if editError}
          <div class="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
            {editError}
          </div>
        {/if}

        {#if editProfileType === 'workflow-template'}
          <div class="mb-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-sm text-amber-700 dark:text-amber-300">
            Workflow templates are edited visually in the Blueprint Canvas. Below you can only edit basic metadata.
          </div>
        {/if}

        {#if editProfileType === 'language-pack'}
          <div class="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg text-sm text-blue-700 dark:text-blue-300">
            Language packs contain UI translations managed via the Translation Dashboard. Strings are read-only here.
          </div>
        {/if}

        <div class="space-y-4">
          {#each formFields() as field}
            <div>
              <label class={labelClass()}>{field.label}</label>
              {#if field.type === 'textarea' || field.type === 'markdown'}
                <textarea
                  value={editForm[field.key] ?? ''}
                  oninput={(e) => updateField(field.key, e.currentTarget.value)}
                  class={inputClass() + ' min-h-[200px] font-mono text-xs'}
                  rows={12}
                ></textarea>
              {:else if field.type === 'checkbox'}
                <input
                  type="checkbox"
                  checked={!!editForm[field.key]}
                  onchange={(e) => updateField(field.key, e.currentTarget.checked)}
                  class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
              {:else if field.type === 'color'}
                <div class="flex items-center gap-3">
                  <input
                    type="color"
                    value={editForm[field.key] || '#8b5cf6'}
                    oninput={(e) => updateField(field.key, e.currentTarget.value)}
                    class="w-10 h-10 rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
                  />
                  <input
                    type="text"
                    value={editForm[field.key] || ''}
                    oninput={(e) => updateField(field.key, e.currentTarget.value)}
                    class={inputClass() + ' flex-1'}
                  />
                </div>
              {:else}
                <input
                  type={field.type}
                  value={editForm[field.key] ?? ''}
                  oninput={(e) => {
                    const val = field.type === 'number'
                      ? (e.currentTarget.value === '' ? null : Number(e.currentTarget.value))
                      : e.currentTarget.value;
                    updateField(field.key, val);
                  }}
                  class={inputClass()}
                  readonly={field.readonly}
                  step={field.step}
                  min={field.min}
                  max={field.max}
                  disabled={field.readonly}
                />
              {/if}
            </div>
          {/each}
        </div>

        {#if editProfileType === 'workflow-template' && editForm.template_data}
          <div class="mt-4">
            <label class={labelClass()}>Template Structure (read-only)</label>
            <pre class="text-xs bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-3 overflow-x-auto max-h-48 overflow-y-auto text-gray-600 dark:text-gray-400 font-mono">{JSON.stringify(editForm.template_data, null, 2)}</pre>
          </div>
        {/if}
      </div>

      <div class="flex items-center justify-end gap-2 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-750">
        <button
          class="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
          onclick={closeEdit}
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          onclick={saveEdit}
          disabled={editSaving}
        >
          {editSaving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  </div>
{/if}
