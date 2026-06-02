<script>
  import { onMount } from 'svelte';
  import { loading, error, backups, backupDetails, isLoadingBackups, backupConfig } from '../lib/stores.js';
  import { tStore } from '../lib/i18n/index.js';
  import {
    reloadProfiles,
    getBackendLogs,
    getSettings,
    updateSettings,
    getBackupSettings,
    updateBackupSettings,
    deleteBackup,
    getBackupFiles,
    verifyBackup as apiVerifyBackup,
    createBackup as apiCreateBackup,
    getBackups,
    restoreBackup,
    getOcrSettings,
    updateOcrSettings,
    getOcrStatus,
  } from '../lib/api.js';
  import ConfirmDialog from '../components/ConfirmDialog.svelte';

  let t = $derived($tStore);

  // --- State ---
  let activeTab = $state('backup');
  let statusMessage = $state('');

  // --- Confirmation dialogs (replace window.confirm for accessibility) ---
  let pendingDeleteBackup = $state(null);
  let pendingRestoreBackup = $state(null);

  // System tab state
  let isReloading = $state(false);
  let reloadResult = $state(null);
  let logLines = $state([]);
  let logSearch = $state('');
  let isLoadingLogs = $state(false);

  // Settings tab state
  let settingsData = $state({});
  let settingsLoaded = $state(false);
  let isLoadingSettings = $state(false);
  let isSavingSettings = $state(false);
  let settingsMessage = $state('');

  // OCR tab state
  let ocrSettings = $state({});
  let ocrStatus = $state(null);
  let isLoadingOcr = $state(false);
  let isSavingOcr = $state(false);
  let ocrMessage = $state('');

  // Backup tab state
  let backupSettings = $state({});
  let isLoadingBackupSettings = $state(false);
  let isSavingBackupSettings = $state(false);
  let backupMessage = $state('');
  let isCreatingBackup = $state(false);
  let backupCreateMessage = $state('');
  let showBackupFileList = $state(false);

  // --- Lifecycle ---
  onMount(async () => {
    error.set(null);
    await loadBackupSettings();
    await loadBackups();
  });

  // --- Backup Handlers ---
  async function loadBackupSettings() {
    isLoadingBackupSettings = true;
    try {
      backupSettings = await getBackupSettings();
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingBackupSettings = false;
    }
  }

  async function handleSaveBackupSettings() {
    isSavingBackupSettings = true;
    backupMessage = '';
    try {
      await updateBackupSettings(backupSettings);
      backupMessage = t('backup.settingsSaved') || 'Backup settings saved';
      await loadBackupSettings();
    } catch (e) {
      error.set(e.message);
    } finally {
      isSavingBackupSettings = false;
    }
  }

  async function handleCreateBackup() {
    isCreatingBackup = true;
    backupCreateMessage = '';
    try {
      const result = await apiCreateBackup();
      backupCreateMessage = t('backup.created', { id: result.backup_id });
      await loadBackups();
    } catch (e) {
      error.set(e.message);
    } finally {
      isCreatingBackup = false;
    }
  }

  async function loadBackups() {
    isLoadingBackups.set(true);
    try {
      const result = await getBackups();
      backups.set(result.backups || []);
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingBackups.set(false);
    }
  }

  async function handleDeleteBackup(backupId) {
    pendingDeleteBackup = backupId;
  }

  async function confirmDeleteBackup() {
    const id = pendingDeleteBackup;
    pendingDeleteBackup = null;
    if (!id) return;
    try {
      await deleteBackup(id);
      await loadBackups();
    } catch (e) {
      error.set(e.message);
    }
  }

  async function showBackupFiles(backupId) {
    showBackupFileList = true;
    isLoadingBackups.set(true);
    try {
      const result = await getBackupFiles(backupId);
      backupDetails.set(result.files);
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingBackups.set(false);
    }
  }

  function closeFileList() {
    showBackupFileList = false;
    backupDetails.set(null);
  }

  async function verifyBackupById(backupId) {
    try {
      const result = await apiVerifyBackup(backupId);
      if (result.valid) {
        backupCreateMessage = t('backup.verifySuccess') || 'Backup verified successfully';
      } else {
        backupCreateMessage = t('backup.verifyFailed') || 'Verification failed: ' + (result.errors?.join(', ') || 'Unknown error');
      }
    } catch (e) {
      error.set(e.message);
    }
  }

  async function handleRestoreBackup(backupId) {
    pendingRestoreBackup = backupId;
  }

  async function confirmRestoreBackup() {
    const id = pendingRestoreBackup;
    pendingRestoreBackup = null;
    if (!id) return;
    try {
      const result = await restoreBackup(id);
      backupCreateMessage = result.message || t('backup.restoreSuccess') || 'Restore completed';
      await loadBackups();
    } catch (e) {
      error.set(e.message);
    }
  }

  // --- System/Settings ---
  async function handleReloadProfiles() {
    isReloading = true;
    statusMessage = '';
    try {
      reloadResult = await reloadProfiles();
      statusMessage = `✓ ${reloadResult.message} — ${reloadResult.llm_profiles} LLM, ${reloadResult.agent_personas} Agenten, ${reloadResult.prompt_variants} Prompts`;
    } catch (e) { error.set(e.message); }
    finally { isReloading = false; }
  }

  async function handleLoadLogs() {
    isLoadingLogs = true;
    try {
      const result = await getBackendLogs(200, logSearch || null);
      logLines = result.lines || [];
    } catch (e) { error.set(e.message); }
    finally { isLoadingLogs = false; }
  }

  async function loadSettings() {
    isLoadingSettings = true;
    try {
      settingsData = await getSettings() || {};
      settingsLoaded = true;
    } catch (e) { error.set(e.message); }
    finally { isLoadingSettings = false; }
  }

  async function handleSaveSettings() {
    isSavingSettings = true;
    settingsMessage = '';
    try {
      await updateSettings(settingsData);
      settingsMessage = `✓ ${t('settings.saved')}`;
    } catch (e) { error.set(e.message); }
    finally { isSavingSettings = false; }
  }

  // --- OCR Handlers ---
  async function loadOcrTab() {
    isLoadingOcr = true;
    try {
      ocrSettings = await getOcrSettings();
      ocrStatus = await getOcrStatus();
    } catch (e) {
      error.set(e.message);
    } finally {
      isLoadingOcr = false;
    }
  }

  async function handleSaveOcrSettings() {
    isSavingOcr = true;
    ocrMessage = '';
    try {
      await updateOcrSettings({ ocr_preferred_engine: ocrSettings.ocr_preferred_engine });
      ocrMessage = '✓ ' + (t('ocr.saved') || 'OCR settings saved');
      await loadOcrTab();
    } catch (e) {
      error.set(e.message);
    } finally {
      isSavingOcr = false;
    }
  }

  function ocrEngineMeta(engine) {
    const meta = {
      auto: {
        label: t('ocr.engineAuto') || 'Auto (Fallback chain)',
        hint: t('ocr.engineAutoHint') || 'PaddleOCR → EasyOCR → Tesseract — tries each engine in order',
        requirements: t('ocr.reqAuto') || 'No specific requirements; uses whatever is available.',
        icon: '⚡',
      },
      paddleocr: {
        label: t('ocr.enginePaddle') || 'PaddleOCR',
        hint: t('ocr.enginePaddleHint') || 'Best accuracy, CUDA acceleration supported',
        requirements: t('ocr.reqPaddle') || 'Install: pip install paddlepaddle paddleocr. See scripts/setup_dms.sh. GPU: CUDA-compatible NVIDIA GPU + nvidia-docker.',
        icon: '📖',
      },
      easyocr: {
        label: t('ocr.engineEasy') || 'EasyOCR',
        hint: t('ocr.engineEasyHint') || 'Good accuracy, GPU recommended',
        requirements: t('ocr.reqEasy') || 'Install: pip install easyocr. GPU strongly recommended (PyTorch with CUDA); CPU works but is slow for large documents.',
        icon: '📖',
      },
      tesseract: {
        label: t('ocr.engineTesseract') || 'Tesseract',
        hint: t('ocr.engineTesseractHint') || 'Lightweight, always available as fallback',
        requirements: t('ocr.reqTesseract') || 'Install Tesseract system package:\n  • Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng\n  • macOS: brew install tesseract\n  • Windows: download from GitHub UB-Mannheim/tesseract',
        icon: '📖',
      },
    };
    return meta[engine] || meta.auto;
  }

  $effect(() => {
    if (activeTab === 'settings' && !settingsLoaded) loadSettings();
    if (activeTab === 'ocr') loadOcrTab();
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="space-y-6" onkeydown={() => {}}>
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('config.title')}</h2>

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

  <!-- Tab Navigation -->
  <div class="border-b border-gray-200 dark:border-gray-700">
    <nav class="flex space-x-4" aria-label="Configuration tabs">
      {#each ['backup', 'settings', 'ocr', 'system'] as tab}
        <button
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors
            {activeTab === tab
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
          onclick={() => { activeTab = tab; }}
        >
          {#if tab === 'backup'}📦 {t('backup.title')}
          {:else if tab === 'settings'}⚙️ {t('settings.title')}
          {:else if tab === 'ocr'}🔍 {t('ocr.title') || 'OCR Engine'}
          {:else if tab === 'system'}🖥️ System
          {/if}
        </button>
      {/each}
    </nav>
  </div>

  <!-- Backup Tab -->
  {#if activeTab === 'backup'}
    <div class="space-y-4">
      <!-- Backup Settings -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('backup.settings') || 'Backup Settings'}</h3>
        {#if isLoadingBackupSettings}
          <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
        {:else}
          <div class="space-y-4">
            <div>
              <label class="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" bind:checked={backupSettings.backup_enabled} class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500" />
                <div>
                  <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{t('backup.enabled') || 'Backups enabled'}</span>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{t('backup.enabledHint') || 'Enable or disable backup functionality'}</p>
                </div>
              </label>
            </div>
            <div>
              <label class="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" bind:checked={backupSettings.backup_auto_on_shutdown} class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500" />
                <div>
                  <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{t('backup.autoOnShutdown')}</span>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{t('backup.autoOnShutdownHint')}</p>
                </div>
              </label>
            </div>
            <div>
              <label for="backup-retention" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('backup.retention')}</label>
              <input id="backup-retention" type="number" bind:value={backupSettings.backup_retention_count} min="0" max="999" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
              <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{t('backup.retentionHint')}</p>
            </div>
            <div>
              <label class="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" bind:checked={backupSettings.backup_encrypt} class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500" disabled />
                <div>
                  <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{t('backup.encrypt')}</span>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{t('backup.encryptHint')}</p>
                </div>
              </label>
            </div>
            {#if backupMessage}
              <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3 text-green-700 dark:text-green-300 text-sm">
                {backupMessage}
              </div>
            {/if}
            <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleSaveBackupSettings} disabled={isSavingBackupSettings}>
              {isSavingBackupSettings ? '...' : (t('common.save') || 'Save')}
            </button>
          </div>
        {/if}
      </div>

      <!-- Create Backup -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">{t('backup.create') || 'Create Backup'}</h3>
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">{t('backup.description') || 'Create a backup of all project data and settings.'}</p>
        <button class="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleCreateBackup} disabled={isCreatingBackup}>
          {isCreatingBackup ? '...' : (t('backup.create') || 'Create Backup')}
        </button>
        {#if backupCreateMessage}
          <p class="mt-2 text-sm text-green-600 dark:text-green-400">{backupCreateMessage}</p>
        {/if}
      </div>

      <!-- Backup List -->
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-x-auto">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white p-6 pb-3">{t('backup.list') || 'Backup Archives'}</h3>
        {#if $backups.length === 0}
          <div class="p-6">
            <p class="text-gray-500 dark:text-gray-400">{t('backup.noBackups') || 'No backups available.'}</p>
          </div>
        {:else}
          <table class="w-full text-sm text-left">
            <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
              <tr>
                <th class="px-4 py-3">{t('backup.date') || 'Date'}</th>
                <th class="px-4 py-3">{t('backup.size') || 'Size'}</th>
                <th class="px-4 py-3">{t('backup.files') || 'Files'}</th>
                <th class="px-4 py-3">{t('backup.trigger') || 'Trigger'}</th>
                <th class="px-4 py-3 text-right">{t('config.actions') || 'Actions'}</th>
              </tr>
            </thead>
            <tbody>
              {#each $backups as backup (backup.backup_id)}
                <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td class="px-4 py-3">{new Date(backup.created_at).toLocaleString()}</td>
                  <td class="px-4 py-3">{(backup.size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
                  <td class="px-4 py-3">{backup.file_count}</td>
                  <td class="px-4 py-3">
                    <span class="text-xs px-2 py-0.5 rounded-full {backup.trigger === 'manual' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'}">
                      {backup.trigger}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-right space-x-1">
                    <button class="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={() => showBackupFiles(backup.backup_id)}>
                      {t('backup.showFiles') || 'Files'}
                    </button>
                    <button class="text-xs px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded hover:bg-green-200 dark:hover:bg-green-800/40 transition-colors" onclick={() => verifyBackupById(backup.backup_id)}>
                      {t('backup.verify') || 'Verify'}
                    </button>
                    <button class="text-xs px-2 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded hover:bg-amber-200 dark:hover:bg-amber-800/40 transition-colors" onclick={() => handleRestoreBackup(backup.backup_id)}>
                      {t('backup.restore') || 'Restore'}
                    </button>
                    <button class="text-xs px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-800/40 transition-colors" onclick={() => handleDeleteBackup(backup.backup_id)}>
                      {t('common.delete') || 'Delete'}
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>

      <!-- File List Overlay -->
      {#if showBackupFileList}
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={closeFileList} role="dialog" aria-modal="true" aria-labelledby="backup-file-list-title" tabindex="-1">
          <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto mx-4" role="presentation" onclick={(e) => e.stopPropagation()}>
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <h3 id="backup-file-list-title" class="text-lg font-semibold text-gray-800 dark:text-white">{t('backup.fileList') || 'Files in Backup'}</h3>
              <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none" onclick={closeFileList}>✕</button>
            </div>
            <div class="px-6 py-4">
              {#if $backupDetails}
                <ul class="space-y-1">
                  {#each $backupDetails as file}
                    <li class="text-sm text-gray-700 dark:text-gray-300 py-1 border-b border-gray-100 dark:border-gray-700">{file}</li>
                  {/each}
                </ul>
              {:else}
                <p class="text-gray-500 dark:text-gray-400">{t('backup.noFiles') || 'No files listed.'}</p>
              {/if}
            </div>
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
              <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={closeFileList}>
                {t('common.close') || 'Close'}
              </button>
            </div>
          </div>
        </div>
      {/if}
    </div>

  <!-- Settings Tab -->
  {:else if activeTab === 'settings'}
    <div class="space-y-4">
      {#if isLoadingSettings}
        <div class="flex items-center justify-center h-32">
          <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
        </div>
      {:else if settingsLoaded}
        {#if settingsMessage}
          <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
            {settingsMessage}
          </div>
        {/if}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 space-y-6">
          <div>
            <label for="settings-search-mode" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('settings.searchMode')}</label>
            <select id="settings-search-mode" value={settingsData.search_mode || 'off'} onchange={(e) => settingsData = { ...settingsData, search_mode: e.target.value }} class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
              <option value="off">{t('debate.searchOff')}</option>
              <option value="optional">{t('debate.searchOptional')}</option>
              <option value="required">{t('debate.searchRequired')}</option>
            </select>
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{t('settings.searchModeHint')}</p>
          </div>
          <div>
            <label class="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" checked={settingsData.privacy_mode || false} onchange={(e) => settingsData = { ...settingsData, privacy_mode: e.target.checked }} class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500" />
              <div>
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{t('settings.privacy')}</span>
                <p class="text-xs text-gray-500 dark:text-gray-400">{t('settings.privacyHint')}</p>
              </div>
            </label>
          </div>
          <div>
            <label for="settings-retention" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('settings.retention')}</label>
            <input id="settings-retention" type="number" value={settingsData.retention_days ?? 0} oninput={(e) => settingsData = { ...settingsData, retention_days: parseInt(e.target.value) || 0 }} min="0" max="3650" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{t('settings.retentionHint')}</p>
          </div>
          <div class="flex justify-end pt-2">
            <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleSaveSettings} disabled={isSavingSettings}>
              {isSavingSettings ? '...' : t('common.save')}
            </button>
          </div>
        </div>
      {/if}
      {#if !settingsLoaded && !isLoadingSettings}
        <div class="flex items-center justify-center h-32">
          <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
        </div>
      {/if}
    </div>

  <!-- OCR Engine Tab -->
  {:else if activeTab === 'ocr'}
    <div class="space-y-4">
      {#if isLoadingOcr}
        <div class="flex items-center justify-center h-32">
          <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
        </div>
      {:else}
        {#if ocrMessage}
          <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
            {ocrMessage}
          </div>
        {/if}

        <!-- Current OCR status -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('ocr.status') || 'OCR Status'}</h3>
          {#if ocrStatus}
            <div class="flex items-center gap-2 mb-2">
              {#if ocrStatus.available}
                <span class="inline-block w-3 h-3 rounded-full bg-green-500" title="available"></span>
                <span class="text-sm text-gray-700 dark:text-gray-300">
                  {t('ocr.available') || 'OCR engine available'}: <strong>{ocrStatus.engine || '—'}</strong>
                </span>
              {:else}
                <span class="inline-block w-3 h-3 rounded-full bg-red-500" title="unavailable"></span>
                <span class="text-sm text-gray-700 dark:text-gray-300">{t('ocr.unavailable') || 'No OCR engine available'}</span>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Preferred engine selection -->
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('ocr.preferredEngine') || 'Preferred OCR Engine'}</h3>
          <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">{t('ocr.preferredHint') || 'Select which OCR engine to prefer. "Auto" uses the built-in fallback chain. The selected engine will be tried first; if unavailable, the remaining engines are tried in order.'}</p>

          <div class="space-y-3">
            {#each ['auto', 'paddleocr', 'easyocr', 'tesseract'] as engine}
              {@const meta = ocrEngineMeta(engine)}
              <label class="flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors
                {ocrSettings.ocr_preferred_engine === engine
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                  : 'border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700/50'}"
              >
                <input
                  type="radio"
                  name="ocr-engine"
                  value={engine}
                  checked={ocrSettings.ocr_preferred_engine === engine}
                  onchange={() => ocrSettings = { ...ocrSettings, ocr_preferred_engine: engine }}
                  class="mt-1 text-blue-600 focus:ring-blue-500"
                />
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium text-gray-800 dark:text-white">{meta.icon} {meta.label}</div>
                  <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{meta.hint}</p>
                  {#if ocrSettings.ocr_preferred_engine === engine}
                    <div class="mt-2 p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded text-xs text-amber-800 dark:text-amber-200 whitespace-pre-line">
                      <strong>{t('ocr.requirements') || 'System requirements'}:</strong><br>
                      {meta.requirements}
                    </div>
                  {/if}
                </div>
              </label>
            {/each}
          </div>

          <div class="flex justify-end pt-4">
            <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleSaveOcrSettings} disabled={isSavingOcr}>
              {isSavingOcr ? '...' : t('common.save')}
            </button>
          </div>
        </div>
      {/if}
    </div>

  <!-- System Tab -->
  {:else if activeTab === 'system'}
    <div class="space-y-4">
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Profile neu laden</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Liest alle YAML-Profile und Prompt-Templates neu von der Festplatte, ohne das Backend neu starten zu müssen.</p>
        <button class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onclick={handleReloadProfiles} disabled={isReloading}>
          {isReloading ? 'Lade...' : '🔄 Profile neu laden'}
        </button>
        {#if reloadResult}
          <div class="mt-3 text-sm text-gray-600 dark:text-gray-300">
            <p>LLM-Profile: {reloadResult.llm_profiles} | Agenten: {reloadResult.agent_personas} | Prompts: {reloadResult.prompt_variants}</p>
          </div>
        {/if}
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Frontend neu laden</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Lädt die Seite neu (gleich wie Browser-Refresh / F5).</p>
        <button class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors" onclick={() => location.reload()}>
          🔄 Seite neu laden
        </button>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Backend-Logs</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Zeigt die letzten Log-Einträge des Backends (mit Timestamps).</p>
        <div class="flex gap-2 mb-4">
          <input type="text" bind:value={logSearch} placeholder="Filter (z.B. ERROR, agent, LLM)..." class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" onkeydown={(e) => { if (e.key === 'Enter') handleLoadLogs(); }} />
          <button class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm" onclick={handleLoadLogs} disabled={isLoadingLogs}>
            {isLoadingLogs ? 'Lade...' : '📋 Logs laden'}
          </button>
        </div>
        {#if logLines.length > 0}
          <div class="bg-gray-900 rounded-lg p-4 overflow-auto max-h-96">
            <pre class="text-xs text-green-400 font-mono whitespace-pre-wrap">{logLines.join('\n')}</pre>
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">{logLines.length} Zeilen</p>
        {:else if !isLoadingLogs}
          <p class="text-sm text-gray-500 dark:text-gray-400">Noch keine Logs geladen. Klicke auf "Logs laden".</p>
        {/if}
      </div>
    </div>
  {/if}
</div>

<ConfirmDialog
  open={pendingDeleteBackup !== null}
  title={t('backup.deleteTitle') || t('common.delete')}
  message={t('backup.confirmDelete') || 'Are you sure you want to delete this backup?'}
  confirmLabel={t('common.delete')}
  cancelLabel={t('common.cancel')}
  variant="danger"
  onConfirm={confirmDeleteBackup}
  onCancel={() => (pendingDeleteBackup = null)}
/>

<ConfirmDialog
  open={pendingRestoreBackup !== null}
  title={t('backup.restoreTitle') || t('common.confirm')}
  message={t('backup.confirmRestore') || 'This will overwrite existing data. Continue?'}
  confirmLabel={t('common.confirm')}
  cancelLabel={t('common.cancel')}
  variant="warning"
  onConfirm={confirmRestoreBackup}
  onCancel={() => (pendingRestoreBackup = null)}
/>
