<script>
  import { onMount, onDestroy } from 'svelte';
  import { formatNumber, tStore } from '../../lib/i18n/index.js';
  import { syncFromDb } from '../../lib/api.js';

  let {
    profiles = [],
    selectedProfileId = '',
    serviceLLMConfig = {},
    serviceEligibleProfiles = [],
    isLoadingServiceLLM = false,
    onCreate = () => {},
    onEdit = () => {},
    onDuplicate = () => {},
    onDelete = () => {},
    onToggleService = () => {},
    onSelectProfile = () => {},
  } = $props();

  let t = $derived($tStore);

  let search = $state('');
  let dropdownOpen = $state(null);
  let syncing = $state(false);
  let syncMessage = $state('');

  async function handleSyncAll() {
    syncing = true;
    syncMessage = '';
    try {
      const result = await syncFromDb('llm-profile');
      syncMessage = `✓ ${result.exported} profile(s) synced to modules`;
    } catch (e) {
      syncMessage = `✗ ${e.message}`;
    } finally {
      syncing = false;
    }
  }

  const PROFILE_TYPE_LABELS = { text: 'Text', tts: 'TTS', stt: 'STT' };
  const PROFILE_TYPE_COLORS = {
    text: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
    tts: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
    stt: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
  };

  let filteredProfiles = $derived(() => {
    const q = search.toLowerCase().trim();
    let list = [...profiles];
    if (q) {
      list = list.filter(p =>
        p.name.toLowerCase().includes(q) ||
        (p.profile_type || 'text').toLowerCase().includes(q) ||
        p.model.toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => a.name.localeCompare(b.name));
    return list;
  });

  function getServiceElig(profileId) {
    return serviceEligibleProfiles.find(p => p.id === profileId) || null;
  }

  function toggleDropdown(profileId) {
    dropdownOpen = dropdownOpen === profileId ? null : profileId;
  }

  function handleDocClick(e) {
    if (!e.target.closest('[data-dropdown-toggle]') && !e.target.closest('[data-dropdown-menu]')) {
      dropdownOpen = null;
    }
  }

  onMount(() => {
    document.addEventListener('click', handleDocClick);
  });

  onDestroy(() => {
    document.removeEventListener('click', handleDocClick);
  });
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between gap-4">
    <div class="relative flex-1 max-w-md">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">🔍</span>
      <input type="text" bind:value={search}
        placeholder="{t('config.search')}… (Name, Typ, Modell)"
        class="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
      {#if search}
        <button class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" onclick={() => { search = ''; }}>✕</button>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      <button class="px-3 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors whitespace-nowrap disabled:opacity-50"
        onclick={handleSyncAll} disabled={syncing}>
        {syncing ? 'Syncing…' : '📦 Sync to Modules'}
      </button>
      <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap" onclick={onCreate}>
        + {t('config.createLLM')}
      </button>
    </div>
  </div>
  {#if syncMessage}
    <div class="text-sm px-3 py-2 rounded-lg {syncMessage.startsWith('✓') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'}">
      {syncMessage}
      <button class="ml-2 text-blue-600 underline" onclick={() => syncMessage = ''}>{t('common.dismiss')}</button>
    </div>
  {/if}
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
    {#if profiles.length === 0}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('config.llmProfilesPlaceholder')}</p>
      </div>
    {:else if filteredProfiles().length === 0}
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('config.noResults') || 'Keine Treffer'}</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
            <tr>
              <th class="px-4 py-3">{t('config.name')}</th>
              <th class="px-4 py-3">{t('config.type') || 'Typ'}</th>
              <th class="px-4 py-3 text-center">🔧 {t('service.utility') || 'Utility'}</th>
              <th class="px-4 py-3">{t('config.provider')}</th>
              <th class="px-4 py-3">{t('config.model')}</th>
              <th class="px-4 py-3">{t('config.temperature')}</th>
              <th class="px-4 py-3">{t('config.maxTokens')}</th>
              <th class="px-4 py-3">{t('config.contextWindow')}</th>
              <th class="px-4 py-3 text-right">{t('config.actions') || 'Aktionen'}</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredProfiles() as profile (profile.id)}
              <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50
                {selectedProfileId === profile.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}">
                <td class="px-4 py-3 font-medium">
                  <button class="text-blue-600 dark:text-blue-400 hover:underline" onclick={() => { onSelectProfile(profile.id); }}>
                    {profile.name}
                  </button>
                  {#if selectedProfileId === profile.id}
                    <span class="ml-2 text-xs text-green-600 dark:text-green-400">✓ {t('config.active')}</span>
                  {/if}
                </td>
                <td class="px-4 py-3">
                  <span class="inline-block text-xs px-2 py-0.5 rounded-full {PROFILE_TYPE_COLORS[profile.profile_type || 'text']}">
                    {PROFILE_TYPE_LABELS[profile.profile_type || 'text']}
                  </span>
                </td>
                <td class="px-4 py-3 text-center">
                  {#if getServiceElig(profile.id)}
                    {#if getServiceElig(profile.id).service_eligible || serviceLLMConfig.service_llm_profile_id === profile.id}
                      <div class="flex flex-col items-center gap-0.5">
                        <input type="checkbox"
                          checked={serviceLLMConfig.service_llm_profile_id === profile.id}
                          onchange={(e) => onToggleService(profile.id, e.target.checked)}
                          disabled={isLoadingServiceLLM}
                          class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500" />
                        {#if !getServiceElig(profile.id).service_eligible}
                          <span class="text-[10px] text-amber-500 dark:text-amber-400" title={getServiceElig(profile.id).eligibility_reason}>⚠️</span>
                        {/if}
                      </div>
                    {:else}
                      <span class="text-[10px] text-gray-400" title={getServiceElig(profile.id).eligibility_reason}>⚠️</span>
                    {/if}
                  {:else}
                    <span class="text-xs text-gray-400">—</span>
                  {/if}
                </td>
                <td class="px-4 py-3">{profile.provider}</td>
                <td class="px-4 py-3 font-mono text-xs">{profile.model}</td>
                <td class="px-4 py-3">{formatNumber(profile.temperature, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td class="px-4 py-3">{formatNumber(profile.max_tokens)}</td>
                <td class="px-4 py-3">{profile.context_window != null ? formatNumber(profile.context_window) : '—'}</td>
                <td class="px-4 py-3 text-right">
                  <div class="relative inline-block">
                    <button
                      data-dropdown-toggle
                      class="px-2 py-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                      onclick={(e) => { e.stopPropagation(); toggleDropdown(profile.id); }}
                      aria-haspopup="true" aria-expanded={dropdownOpen === profile.id}>
                      ⋮
                    </button>
                    {#if dropdownOpen === profile.id}
                       <div data-dropdown-menu class="absolute right-0 top-full mt-1 z-40 w-40 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1">
                         <button class="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { dropdownOpen = null; onEdit(profile); }}>
                           ✏️ {t('common.edit')}
                         </button>
                         <button class="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" onclick={() => { dropdownOpen = null; onDuplicate(profile); }}>
                           📋 {t('config.duplicate') || 'Duplizieren'}
                         </button>
                         <hr class="my-1 border-gray-200 dark:border-gray-700" />
                         <button class="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors" onclick={() => { dropdownOpen = null; onDelete(profile.id, profile.name); }}>
                           🗑️ {t('common.delete')}
                         </button>
                       </div>
                    {/if}
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 border-t border-gray-100 dark:border-gray-700">
        {filteredProfiles().length} / {profiles.length} {t('config.profiles') || 'Profile'}
      </div>
    {/if}
  </div>
</div>
