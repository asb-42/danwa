<script>
  import { onMount, onDestroy } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { LOCALE_NAMES } from '../lib/i18n/config.js';
  import { addToast } from '../lib/stores.js';
  import {
    getSupportedLocales,
    getTranslationStats,
    getTranslationCoverage,
    getLocaleDetails,
    bulkTranslate,
    getTranslationJobStatus,
    setTranslation,
    registerLocale,
    getCustomLocales,
    wipeLocale,
  } from '../lib/api.js';
  import ConfirmDialog from '../components/ConfirmDialog.svelte';

  let { navigate } = $props();
  let t = $derived($tStore);

  let locales = $state([]);
  let stats = $state({});
  let coverage = $state({});
  let customLocales = $state([]);
  let loading = $state(false);
  let translatingLocale = $state(null);
  let wipingLocale = $state(null);

  // Async job state
  let activeJobId = $state(null);
  let jobProgress = $state(0);
  let jobTotal = $state(0);
  let jobCompleted = $state(0);
  let jobCurrentKey = $state('');
  let jobCurrentLocale = $state('');
  let jobStatus = $state('');
  let pollInterval = $state(null);

  // Detail view state
  let expandedLocale = $state(null);
  let detailStrings = $state([]);
  let detailLoading = $state(false);
  let editingKey = $state(null);
  let editingValue = $state('');

  // Add language dialog
  let addLocaleOpen = $state(false);
  let newLocaleCode = $state('');
  let newLocaleName = $state('');
  let newLocaleRtl = $state(false);
  let addingLocale = $state(false);
  let addLocaleError = $state('');

  let pendingWipeLocale = $state(null);

  onMount(async () => {
    await loadOverview();
  });

  onDestroy(() => {
    cancelPolling();
  });

  async function loadOverview() {
    loading = true;
    try {
      const [localesRes, statsRes, coverageRes, customRes] = await Promise.all([
        getSupportedLocales().catch(() => ({ locales: [] })),
        getTranslationStats().catch(() => ({})),
        getTranslationCoverage().catch(() => ({})),
        getCustomLocales().catch(() => ({ custom_locales: [] })),
      ]);

      const builtIn = (localesRes.locales || []).map(l => ({
        code: l.code,
        name: LOCALE_NAMES[l.code] || l.name || l.code,
        isRtl: l.is_rtl || false,
        isCustom: false,
      }));

      const custom = (customRes.custom_locales || []).map(l => ({
        code: l.locale,
        name: l.name || l.locale,
        isRtl: l.is_rtl || false,
        isCustom: true,
      }));

      locales = [...builtIn, ...custom];
      stats = statsRes;
      coverage = coverageRes;
    } finally {
      loading = false;
    }
  }

  async function loadDetail(localeCode) {
    if (expandedLocale === localeCode) {
      expandedLocale = null;
      detailStrings = [];
      return;
    }
    expandedLocale = localeCode;
    detailLoading = true;
    editingKey = null;
    try {
      const data = await getLocaleDetails(localeCode);
      detailStrings = data.strings || [];
    } catch (e) {
      console.error('Failed to load locale details:', e);
      detailStrings = [];
    } finally {
      detailLoading = false;
    }
  }

  function startEdit(key, currentValue) {
    editingKey = key;
    editingValue = currentValue || '';
  }

  async function saveEdit(localeCode, key) {
    try {
      await setTranslation(localeCode, key, editingValue);
      const idx = detailStrings.findIndex(s => s.key === key);
      if (idx >= 0) {
        detailStrings[idx] = {
          ...detailStrings[idx],
          translated_value: editingValue,
          status: 'translated',
          source: 'manual',
          updated_at: new Date().toISOString(),
        };
      }
      editingKey = null;
    } catch (e) {
      console.error('Failed to save translation:', e);
    }
  }

  async function translateLocale(localeCode, wipeFirst = false) {
    translatingLocale = localeCode;
    try {
      const { job_id } = await bulkTranslate([localeCode], 'global', false, wipeFirst);
      activeJobId = job_id;
      jobStatus = 'running';
      jobProgress = 0;

      pollInterval = setInterval(async () => {
        try {
          const status = await getTranslationJobStatus(job_id);
          jobProgress = status.progress_pct || 0;
          jobTotal = status.total_strings || 0;
          jobCompleted = status.completed_strings || 0;
          jobCurrentKey = status.current_key || '';
          jobCurrentLocale = status.current_locale || '';
          jobStatus = status.status;

          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(pollInterval);
            pollInterval = null;
            activeJobId = null;

            if (status.status === 'completed') {
              const localeResult = status.results?.[localeCode] || {};
              const count = localeResult.translated || 0;
              addToast({
                message: `${count} UI strings translated to ${LOCALE_NAMES[localeCode] || localeCode}`,
                type: 'success',
                timeout: 5000,
              });
              await loadOverview();
              if (expandedLocale === localeCode) {
                await loadDetail(localeCode);
              }
            } else {
              addToast({ message: `Translation failed: ${status.error}`, type: 'error', timeout: 8000 });
            }
          }
        } catch (e) {
          console.error('Poll error:', e);
        }
      }, 800);
    } catch (e) {
      addToast({ message: `Translation failed: ${e.message}`, type: 'error', timeout: 8000 });
      console.error('LLM translation failed:', e);
    } finally {
      translatingLocale = null;
    }
  }

  async function wipeLocaleHandler(localeCode) {
    pendingWipeLocale = localeCode;
  }

  async function confirmWipeLocale() {
    const localeCode = pendingWipeLocale;
    pendingWipeLocale = null;
    if (!localeCode) return;
    const localeName = LOCALE_NAMES[localeCode] || localeCode;

    wipingLocale = localeCode;
    try {
      const result = await wipeLocale(localeCode);
      const deleted = result.deleted || 0;
      addToast({
        message: `${deleted} translations deleted for ${localeName}`,
        type: 'success',
        timeout: 5000,
      });
      await loadOverview();
      if (expandedLocale === localeCode) {
        await loadDetail(localeCode);
      }
    } catch (e) {
      addToast({ message: `Wipe failed: ${e.message}`, type: 'error', timeout: 8000 });
      console.error('Wipe failed:', e);
    } finally {
      wipingLocale = null;
    }
  }

  function cancelPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  async function addLocale() {
    if (!newLocaleCode) return;
    addingLocale = true;
    addLocaleError = '';
    try {
      await registerLocale(newLocaleCode, newLocaleName || null, newLocaleRtl);
      addLocaleOpen = false;
      newLocaleCode = '';
      newLocaleName = '';
      newLocaleRtl = false;
      await loadOverview();
    } catch (e) {
      addLocaleError = e.message || 'Failed to add language';
      console.error('Failed to register locale:', e);
    } finally {
      addingLocale = false;
    }
  }

  async function exportAsPack(localeCode) {
    const name = prompt('Language pack name:', LOCALE_NAMES[localeCode] || localeCode);
    if (!name) return;
    const suffix = prompt('Pack ID suffix (e.g. custom, v2):', 'custom');
    if (!suffix) return;

    try {
      const res = await fetch(`/api/v1/i18n/${localeCode}/export-as-pack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description: `Custom ${LOCALE_NAMES[localeCode] || localeCode} translation pack`,
          pack_id_suffix: suffix,
          author: 'Danwa User',
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Export failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `lang-${localeCode}-${suffix}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      addToast({ message: `Exported ${localeCode} as language pack`, type: 'success', timeout: 4000 });
    } catch (e) {
      addToast({ message: `Export failed: ${e.message}`, type: 'error', timeout: 6000 });
    }
  }

  function coverageColor(pct) {
    if (pct >= 90) return 'bg-green-500';
    if (pct >= 60) return 'bg-yellow-500';
    if (pct >= 30) return 'bg-orange-500';
    return 'bg-red-500';
  }

  function coverageTextColor(pct) {
    if (pct >= 90) return 'text-green-700 dark:text-green-300';
    if (pct >= 60) return 'text-yellow-700 dark:text-yellow-300';
    return 'text-red-700 dark:text-red-300';
  }

  function formatDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  }

  function sourceLabel(src) {
    if (!src) return '';
    if (src === 'llm_generated') return 'LLM';
    if (src === 'manual') return 'Manual';
    if (src === 'bulk_imported') return 'Import';
    return src;
  }

  function getLocaleRow(localeCode) {
    const cov = coverage[localeCode] || {};
    const st = stats[localeCode] || {};
    const pct = cov.coverage_pct || 0;
    return { cov, st, pct };
  }
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
      {t('translation.title')}
    </h2>
    <div class="flex gap-2">
      <button
        class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
        onclick={() => addLocaleOpen = true}
      >
        + {t('translation.addLanguage')}
      </button>
      <button
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600 transition-colors text-sm disabled:opacity-50"
        onclick={loadOverview}
        disabled={loading}
      >
        {loading ? t('common.loading') : '🔄 ' + t('translation.refreshModules')}
      </button>
    </div>
  </div>

  <!-- Active Translation Job Progress -->
  {#if activeJobId}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-blue-200 dark:border-blue-800 p-4">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-medium text-blue-700 dark:text-blue-300">
          Translating to {jobCurrentLocale}… ({jobCompleted}/{jobTotal})
        </span>
        <span class="text-sm font-bold text-blue-700 dark:text-blue-300">{jobProgress}%</span>
      </div>
      <div
        class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3"
        role="progressbar"
        aria-valuenow={jobProgress}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-label="Translation progress: {jobCompleted} of {jobTotal} keys ({jobProgress}%)"
      >
        <div
          class="h-3 rounded-full bg-blue-600 transition-all duration-500"
          style="width: {jobProgress}%"
        ></div>
      </div>
      {#if jobCurrentKey}
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400 truncate">{jobCurrentKey}</p>
      {/if}
    </div>
  {/if}

  <!-- Overview Table -->
  {#if loading && locales.length === 0}
    <div class="flex items-center justify-center h-32">
      <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
    </div>
  {:else if locales.length === 0}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 text-center">
      <p class="text-gray-500 dark:text-gray-400 mb-4">
        {t('translation.noLocales')}
      </p>
      <button
        class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
        onclick={() => addLocaleOpen = true}
      >
        + {t('translation.addLanguage')}
      </button>
    </div>
  {:else}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700">
          <tr>
            <th class="text-left px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('translation.language')}</th>
            <th class="text-center px-3 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('translation.totalStrings')}</th>
            <th class="text-center px-3 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('translation.translated')}</th>
            <th class="text-center px-3 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('translation.missing')}</th>
            <th class="text-left px-4 py-3 font-semibold text-gray-700 dark:text-gray-300 w-48">{t('translation.coverage')}</th>
            <th class="text-center px-3 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('translation.llm')}</th>
            <th class="text-center px-3 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('translation.manual')}</th>
            <th class="text-left px-3 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('translation.lastUpdated')}</th>
            <th class="text-right px-4 py-3 font-semibold text-gray-700 dark:text-gray-300">{t('common.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {#each locales as locale (locale.code)}
            {#each [getLocaleRow(locale.code)] as row}
            <tr class="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-gray-800 dark:text-white">{locale.name}</span>
                  <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">{locale.code}</span>
                  {#if locale.isRtl}<span class="text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 px-1.5 py-0.5 rounded">RTL</span>{/if}
                  {#if locale.isCustom}<span class="text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded">Custom</span>{/if}
                </div>
              </td>
              <td class="text-center px-3 py-3 text-gray-600 dark:text-gray-400">{row.cov.total_keys || row.st.total || '—'}</td>
              <td class="text-center px-3 py-3 text-green-600 dark:text-green-400 font-medium">{row.cov.translated || row.st.translated || 0}</td>
              <td class="text-center px-3 py-3 text-red-600 dark:text-red-400">{row.cov.total_keys && row.cov.translated ? row.cov.total_keys - row.cov.translated : '—'}</td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <div class="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                    <div class="h-2 rounded-full transition-all duration-500 {coverageColor(row.pct)}" style="width: {row.pct}%"></div>
                  </div>
                  <span class="text-xs font-medium w-10 text-right {coverageTextColor(row.pct)}">{row.pct.toFixed(0)}%</span>
                </div>
              </td>
              <td class="text-center px-3 py-3 text-gray-500 dark:text-gray-400">{row.st.llm || 0}</td>
              <td class="text-center px-3 py-3 text-gray-500 dark:text-gray-400">{row.st.manual || 0}</td>
              <td class="text-left px-3 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">{formatDate(row.st.last_updated)}</td>
              <td class="text-right px-4 py-3">
                <div class="flex items-center justify-end gap-1">
                  <button
                    class="px-2.5 py-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    onclick={() => loadDetail(locale.code)}
                  >
                    {expandedLocale === locale.code ? t('translation.close') : t('translation.details')}
                  </button>
                  <button
                    class="px-2.5 py-1 text-xs bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-200 dark:hover:bg-emerald-800/50 transition-colors"
                    onclick={() => exportAsPack(locale.code)}
                    title="Export as Language Pack ZIP"
                  >
                    📦 Export
                  </button>
                  <button
                    class="px-2.5 py-1 text-xs rounded transition-colors disabled:opacity-50 {locale.code === 'en'
                      ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                      : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-200 disabled:hover:bg-red-100 dark:hover:bg-red-800 disabled:hover:bg-red-700/50'}"
                    disabled={wipingLocale === locale.code || activeJobId !== null || locale.code === 'en'}
                    onclick={() => locale.code !== 'en' && wipeLocaleHandler(locale.code)}
                    title={locale.code === 'en' ? 'Cannot wipe source language' : 'Delete all translations for this locale'}
                  >
                    {wipingLocale === locale.code ? '⏳ Wiping…' : '🗑️ Wipe'}
                  </button>
                  <button
                    class="px-2.5 py-1 text-xs rounded transition-colors disabled:opacity-50 {locale.code === 'en'
                      ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                      : 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-200 disabled:hover:bg-indigo-100 dark:hover:bg-indigo-800 disabled:hover:bg-indigo-700/50'}"
                    disabled={translatingLocale === locale.code || activeJobId !== null || locale.code === 'en'}
                    onclick={() => locale.code !== 'en' && translateLocale(locale.code, false)}
                    title={locale.code === 'en' ? 'English is the source language (SSOT)' : 'Translate with LLM'}
                  >
                    {translatingLocale === locale.code ? '⏳ ' + t('translation.translating') : '🤖 ' + t('translation.llm')}
                  </button>
                  <button
                    class="px-2.5 py-1 text-xs rounded transition-colors disabled:opacity-50 {locale.code === 'en'
                      ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                      : 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 hover:bg-violet-200 disabled:hover:bg-violet-100 dark:hover:bg-violet-800 disabled:hover:bg-violet-700/50'}"
                    disabled={translatingLocale === locale.code || activeJobId !== null || locale.code === 'en'}
                    onclick={() => locale.code !== 'en' && translateLocale(locale.code, true)}
                    title={locale.code === 'en' ? 'English is the source language (SSOT)' : 'Wipe existing translations, then translate all strings fresh'}
                  >
                    {translatingLocale === locale.code ? '⏳ ' + t('translation.translating') : '🔄 ' + t('translation.llm') + ' + Wipe'}
                  </button>
                </div>
              </td>
            </tr>

            <!-- Expanded detail row -->
            {#if expandedLocale === locale.code}
              <tr>
                <td colspan="9" class="p-0">
                  <div class="bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700 p-4">
                    {#if detailLoading}
                      <div class="flex items-center justify-center py-8">
                        <p class="text-gray-400">{t('common.loading')}</p>
                      </div>
                    {:else if detailStrings.length === 0}
                      <p class="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">        {t('translation.noStrings')}</p>
                    {:else}
                      <div class="overflow-x-auto">
                        <table class="w-full text-xs">
                          <thead class="border-b border-gray-200 dark:border-gray-700">
                            <tr>
                              <th class="text-left py-2 px-2 font-medium text-gray-600 dark:text-gray-400">{t('translation.key')}</th>
                              <th class="text-left py-2 px-2 font-medium text-gray-600 dark:text-gray-400 w-1/4">{t('translation.english')}</th>
                              <th class="text-left py-2 px-2 font-medium text-gray-600 dark:text-gray-400 w-1/4">{locale.name}</th>
                              <th class="text-center py-2 px-2 font-medium text-gray-600 dark:text-gray-400">{t('translation.source')}</th>
                              <th class="text-left py-2 px-2 font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">{t('translation.updated')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {#each detailStrings as str (str.key)}
                              <tr class="border-b border-gray-100 dark:border-gray-700/30 hover:bg-white dark:hover:bg-gray-700/30 transition-colors">
                                <td class="py-1.5 px-2 font-mono text-gray-500 dark:text-gray-400 truncate max-w-[200px]" title={str.key}>{str.key}</td>
                                <td class="py-1.5 px-2 text-gray-700 dark:text-gray-300 truncate max-w-[250px]" title={str.source_value}>{str.source_value}</td>
                                <td class="py-1.5 px-2">
                                  {#if editingKey === str.key}
                                    <div class="flex gap-1">
                                      <input
                                        type="text"
                                        bind:value={editingValue}
                                        class="flex-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs"
                                        onkeydown={(e) => {
                                          if (e.key === 'Enter') saveEdit(locale.code, str.key);
                                          if (e.key === 'Escape') editingKey = null;
                                        }}
                                      />
                                      <button class="px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700" onclick={() => saveEdit(locale.code, str.key)}>✓</button>
                                      <button class="px-2 py-1 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded text-xs hover:bg-gray-400" onclick={() => editingKey = null}>✕</button>
                                    </div>
                                  {:else if str.status === 'translated'}
                                    <div class="flex items-center gap-1">
                                      <span class="text-gray-800 dark:text-gray-200 truncate max-w-[200px]" title={str.translated_value}>{str.translated_value}</span>
                                      <button class="text-gray-400 hover:text-blue-500 transition-colors flex-shrink-0" onclick={() => startEdit(str.key, str.translated_value)}>✎</button>
                                    </div>
                                  {:else}
                                    <span class="text-gray-400 dark:text-gray-500 italic">{t('translation.missingTranslation')}</span>
                                    <button class="ml-1 text-gray-400 hover:text-blue-500 transition-colors" onclick={() => startEdit(str.key, '')}>+ {t('translation.add')}</button>
                                  {/if}
                                </td>
                                <td class="text-center py-1.5 px-2">
                                  {#if str.source}
                                    <span class="px-1.5 py-0.5 rounded text-xs {str.source === 'llm_generated' ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}">
                                      {sourceLabel(str.source)}
                                    </span>
                                  {:else}
                                    <span class="text-gray-400">—</span>
                                  {/if}
                                </td>
                                <td class="py-1.5 px-2 text-gray-400 dark:text-gray-500 whitespace-nowrap">{formatDate(str.updated_at)}</td>
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      </div>
                    {/if}
                  </div>
                </td>
              </tr>
            {/if}
            {/each}
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Add Language Dialog -->
{#if addLocaleOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    onclick={() => { addLocaleOpen = false; }}
    onkeydown={(e) => { if (e.key === 'Escape') addLocaleOpen = false; }}
    role="dialog"
    aria-modal="true"
    aria-labelledby="translation-add-locale-title"
    tabindex="-1"
  >
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6"
      onclick={(e) => e.stopPropagation()}
    >
      <h3 id="translation-add-locale-title" class="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        {t('translation.addLanguage')}
      </h3>
      <div class="space-y-4">
        {#if addLocaleError}
          <div class="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
            {addLocaleError}
          </div>
        {/if}
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('translation.localeCode')} <span class="text-red-500">*</span>
          </label>
          <input
            type="text"
            bind:value={newLocaleCode}
            placeholder="e.g. nl, pl, tr"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
            onkeydown={(e) => { if (e.key === 'Enter') addLocale(); }}
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('translation.localeName')}
          </label>
          <input
            type="text"
            bind:value={newLocaleName}
            placeholder="e.g. Nederlands"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <label class="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            bind:checked={newLocaleRtl}
            class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span class="text-sm text-gray-700 dark:text-gray-300">
            {t('translation.isRtl')}
          </span>
        </label>
      </div>
      <div class="flex items-center justify-end gap-3 mt-6">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={() => { addLocaleOpen = false; }}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:hover:bg-green-600 transition-colors disabled:opacity-50"
          disabled={!newLocaleCode || addingLocale}
          onclick={addLocale}
        >
          {addingLocale ? '⏳ ' + t('common.loading') : t('translation.addLanguage')}
        </button>
      </div>
    </div>
  </div>
{/if}

<ConfirmDialog
  open={pendingWipeLocale !== null}
  title={t('common.confirm')}
  message={pendingWipeLocale
    ? `Delete ALL translations for ${LOCALE_NAMES[pendingWipeLocale] || pendingWipeLocale}?\n\nThis cannot be undone. You will need to re-translate all strings.`
    : ''}
  confirmLabel={t('common.delete')}
  cancelLabel={t('common.cancel')}
  variant="danger"
  onConfirm={confirmWipeLocale}
  onCancel={() => (pendingWipeLocale = null)}
/>
