<script>
  import { onMount } from 'svelte';
  import { i18n } from '../lib/i18n/index.js';
  import {
    getModules,
    getModule,
    getAvailableModules,
    installModule,
    uninstallModule,
    updateModule,
    validateModule,
    enableModule,
    disableModule,
    exportModule,
  } from '../lib/api.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  // --- State ---
  let activeTab = $state('installed');
  let modules = $state([]);
  let isLoading = $state(false);
  let statusMessage = $state('');
  let error = $state(null);

  // Install state
  let availableModules = $state([]);
  let installUrl = $state('');

  // Detail state
  let selectedModule = $state(null);
  let validationResult = $state(null);

  onMount(async () => {
    await loadModules();
  });

  async function loadModules() {
    isLoading = true;
    error = null;
    try {
      const [installed, available] = await Promise.allSettled([
        getModules(),
        getAvailableModules(),
      ]);
      if (installed.status === 'fulfilled') modules = installed.value || [];
      if (available.status === 'fulfilled') availableModules = available.value || [];
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function handleEnable(moduleId) {
    try {
      await enableModule(moduleId);
      statusMessage = t('modules.enabled', { id: moduleId });
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleDisable(moduleId) {
    try {
      await disableModule(moduleId);
      statusMessage = t('modules.disabled', { id: moduleId });
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleExport(moduleId) {
    try {
      const url = await exportModule(moduleId);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${moduleId}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      statusMessage = t('modules.exported', { id: moduleId });
    } catch (e) {
      error = e.message;
    }
  }

  async function handleInstall(moduleId) {
    try {
      await installModule(moduleId);
      statusMessage = t('modules.installed', { id: moduleId });
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleUninstall(moduleId) {
    if (!confirm(t('modules.confirmUninstall', { id: moduleId }))) return;
    try {
      await uninstallModule(moduleId);
      statusMessage = t('modules.uninstalled', { id: moduleId });
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleUpdate(moduleId) {
    try {
      await updateModule(moduleId);
      statusMessage = t('modules.updated', { id: moduleId });
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleValidate(moduleId) {
    validationResult = null;
    try {
      const result = await validateModule(moduleId);
      validationResult = result;
    } catch (e) {
      error = e.message;
    }
  }

  async function handleInstallFromUrl() {
    if (!installUrl.trim()) return;
    try {
      // Try to install as a module ID or URL
      await installModule(installUrl.trim());
      statusMessage = t('modules.installed', { id: installUrl.trim() });
      installUrl = '';
      await loadModules();
    } catch (e) {
      error = e.message;
    }
  }

  function selectModule(moduleId) {
    selectedModule = modules.find(m => m.module_id === moduleId) || null;
    validationResult = null;
  }

  function formatDate(isoString) {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toLocaleString();
    } catch {
      return isoString;
    }
  }

  const installedModules = $derived.by(() => modules.filter(m => m.enabled !== false));
  const disabledModulesList = $derived.by(() => modules.filter(m => m.enabled === false));
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="space-y-6" onclick={() => {}} onkeydown={() => {}}>
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
      {t('modules.title')}
    </h2>
    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-50"
      onclick={loadModules}
      disabled={isLoading}
    >
      {isLoading ? t('common.loading') : '🔄 ' + t('modules.refresh')}
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
    </div>
  {/if}

  <!-- Tab Navigation -->
  <div class="border-b border-gray-200 dark:border-gray-700">
    <nav class="flex space-x-4" aria-label="Module tabs">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
          {activeTab === 'installed'
            ? 'border-blue-500 text-blue-600 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
        onclick={() => { activeTab = 'installed'; }}
      >
        {t('modules.tabInstalled')} ({installedModules.length})
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
          {activeTab === 'available'
            ? 'border-blue-500 text-blue-600 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
        onclick={() => { activeTab = 'available'; }}
      >
        {t('modules.tabAvailable')} ({availableModules.length})
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
          {activeTab === 'install'
            ? 'border-blue-500 text-blue-600 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
        onclick={() => { activeTab = 'install'; }}
      >
        {t('modules.tabInstall')}
      </button>
    </nav>
  </div>

  <!-- Installed Modules Tab -->
  {#if activeTab === 'installed'}
    {#if isLoading}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
      </div>
    {:else if installedModules.length === 0}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 text-center">
        <p class="text-gray-500 dark:text-gray-400">{t('modules.noInstalled')}</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each installedModules as module (module.module_id)}
          <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div
              class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              onclick={() => selectModule(module.module_id)}
              onkeydown={(e) => { if (e.key === 'Enter') selectModule(module.module_id); }}
              role="button"
              tabindex="0"
            >
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold text-sm"
                >
                  {(module.name?.en || module.module_id).charAt(0).toUpperCase()}
                </div>
                <div>
                  <h3 class="text-sm font-semibold text-gray-800 dark:text-white">
                    {module.name?.en || module.module_id}
                  </h3>
                  <p class="text-xs text-gray-500 dark:text-gray-400">
                    v{module.version || '0.0.0'} · {module.type || '—'}
                  </p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <span
                  class="text-xs px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                >
                  ✅ {t('modules.installed')}
                </span>
              </div>
            </div>

            <!-- Expanded detail -->
            {#if selectedModule?.module_id === module.module_id}
              <div class="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  <div>
                    <p class="text-xs text-gray-500">{t('modules.category')}</p>
                    <p class="text-sm font-medium">{module.category || '—'}</p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">{t('modules.type')}</p>
                    <p class="text-sm font-medium">{module.type || '—'}</p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">{t('modules.author')}</p>
                    <p class="text-sm font-medium">{module.author?.name || '—'}</p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">{t('modules.license')}</p>
                    <p class="text-sm font-medium">{module.license || '—'}</p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">{t('modules.installedAt')}</p>
                    <p class="text-sm font-medium">{formatDate(module.installed_at)}</p>
                  </div>
                  <div>
                    <p class="text-xs text-gray-500">{t('modules.checksum')}</p>
                    <code class="text-xs font-mono text-gray-600 dark:text-gray-400 break-all">
                      {module.checksum?.slice(0, 32) || '—'}
                    </code>
                  </div>
                </div>

                <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 flex gap-2 flex-wrap">
                  <button
                    class="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    onclick={() => handleValidate(module.module_id)}
                  >
                    {t('modules.validate')}
                  </button>
                  <button
                    class="px-3 py-1.5 text-xs bg-yellow-600 text-white rounded hover:bg-yellow-700 transition-colors"
                    onclick={() => handleUpdate(module.module_id)}
                  >
                    {t('modules.update')}
                  </button>
                  <button
                    class="px-3 py-1.5 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
                    onclick={() => handleExport(module.module_id)}
                  >
                    📦 {t('modules.export') || 'Export'}
                  </button>
                  <button
                    class="px-3 py-1.5 text-xs bg-amber-600 text-white rounded hover:bg-amber-700 transition-colors"
                    onclick={() => handleDisable(module.module_id)}
                  >
                    ⏸️ {t('modules.disable') || 'Disable'}
                  </button>
                  <button
                    class="px-3 py-1.5 text-xs bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
                    onclick={() => handleUninstall(module.module_id)}
                  >
                    {t('modules.uninstall')}
                  </button>
                </div>

                <!-- Validation result -->
                {#if validationResult}
                  <div class="mt-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <p class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                      {t('modules.validationResult')}
                    </p>
                    <p class="text-sm" class:text-green-600={validationResult.valid} class:text-red-600={!validationResult.valid}>
                      {validationResult.message || t('modules.valid')}
                    </p>
                    {#if validationResult.errors?.length > 0}
                      <ul class="mt-2 text-xs text-red-600">
                        {#each validationResult.errors as err}
                          <li>• {err}</li>
                        {/each}
                      </ul>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

  <!-- Available Modules Tab -->
  {:else if activeTab === 'available'}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
        {t('modules.available')}
      </h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {t('modules.availableHint')}
      </p>
      {#if availableModules.length === 0}
        <p class="text-gray-500 dark:text-gray-400">{t('modules.noAvailable')}</p>
      {:else}
        <div class="space-y-3">
          {#each availableModules as module}
            <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
              <div>
                <p class="text-sm font-medium text-gray-800 dark:text-white">{module.name?.en || module.module_id}</p>
                <p class="text-xs text-gray-500 dark:text-gray-400">v{module.version || '0.0.0'} · {module.type || '—'}</p>
              </div>
              <button
                class="px-3 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                onclick={() => handleInstall(module.module_id)}
              >
                {t('modules.install')}
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>

  <!-- Install by URL/ID Tab -->
  {:else if activeTab === 'install'}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
        {t('modules.installFromSource')}
      </h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {t('modules.installFromSourceHint')}
      </p>
      <div class="flex gap-3">
        <input
          type="text"
          bind:value={installUrl}
          placeholder={t('modules.enterModuleId')}
          class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
        />
        <button
          class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-50"
          onclick={handleInstallFromUrl}
          disabled={!installUrl.trim()}
        >
          {t('modules.install')}
        </button>
      </div>
    </div>
  {/if}
</div>
