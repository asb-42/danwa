<!-- BYOKManager.svelte — Per-user API key management -->

<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { addToast } from '../lib/stores.js';
  import { getUserKeys, setUserKey, deleteUserKey, deleteAllUserKeys, getLLMProfiles } from '../lib/api.js';

  let t = $derived($tStore);

  let keys = $state([]);
  let profiles = $state([]);
  let loading = $state(true);

  // Add form
  let selectedProfile = $state('');
  let apiKey = $state('');
  let label = $state('');
  let saving = $state(false);

  // Delete confirm
  let deleteTarget = $state(null);
  let deleteAllConfirm = $state(false);

  async function loadData() {
    loading = true;
    try {
      const [k, p] = await Promise.all([getUserKeys(), getLLMProfiles()]);
      keys = k;
      profiles = p;
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    } finally {
      loading = false;
    }
  }

  onMount(loadData);

  async function handleAdd(e) {
    e.preventDefault();
    if (!selectedProfile || !apiKey) return;
    saving = true;
    try {
      await setUserKey(selectedProfile, apiKey, label);
      addToast({ type: 'success', message: t('byok.keySaved') });
      selectedProfile = '';
      apiKey = '';
      label = '';
      await loadData();
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    } finally {
      saving = false;
    }
  }

  async function handleDelete(profileId) {
    try {
      await deleteUserKey(profileId);
      addToast({ type: 'success', message: t('byok.keyDeleted') });
      deleteTarget = null;
      await loadData();
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    }
  }

  async function handleDeleteAll() {
    try {
      await deleteAllUserKeys();
      addToast({ type: 'success', message: t('byok.allDeleted') });
      deleteAllConfirm = false;
      await loadData();
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    }
  }
</script>

<div class="max-w-3xl mx-auto p-6 space-y-6">
  <div>
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{t('byok.title')}</h1>
    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('byok.description')}</p>
  </div>

  {#if loading}
    <p class="text-gray-500 dark:text-gray-400">Loading…</p>
  {:else}
    <!-- Existing keys -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      {#if keys.length === 0}
        <p class="text-gray-500 dark:text-gray-400 text-sm">{t('byok.noKeys')}</p>
      {:else}
        <div class="divide-y divide-gray-200 dark:divide-gray-700">
          {#each keys as key}
            <div class="flex items-center justify-between py-3">
              <div>
                <p class="text-gray-900 dark:text-white font-medium font-mono text-sm">{key.profile_id}</p>
                {#if key.label}
                  <p class="text-xs text-gray-500 dark:text-gray-400">{key.label}</p>
                {/if}
              </div>
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                  ●●●●●●●●
                </span>
                {#if deleteTarget === key.profile_id}
                  <button
                    onclick={() => handleDelete(key.profile_id)}
                    class="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                  >
                    {t('byok.deleteKey')}?
                  </button>
                  <button
                    onclick={() => deleteTarget = null}
                    class="px-2 py-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                  >
                    Cancel
                  </button>
                {:else}
                  <button
                    onclick={() => deleteTarget = key.profile_id}
                    class="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                  >
                    {t('byok.deleteKey')}
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>

        <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          {#if deleteAllConfirm}
            <div class="flex items-center gap-3">
              <span class="text-sm text-red-600 dark:text-red-400">{t('byok.deleteAllConfirm')}</span>
              <button
                onclick={handleDeleteAll}
                class="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
              >
                {t('byok.deleteAll')}
              </button>
              <button
                onclick={() => deleteAllConfirm = false}
                class="px-3 py-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                Cancel
              </button>
            </div>
          {:else}
            <button
              onclick={() => deleteAllConfirm = true}
              class="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
            >
              {t('byok.deleteAll')}
            </button>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Add key form -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('byok.addKey')}</h2>

      <form onsubmit={handleAdd} class="space-y-4">
        <div>
          <label for="byok-profile" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('byok.profile')}
          </label>
          <select
            id="byok-profile"
            bind:value={selectedProfile}
            required
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">{t('byok.selectProfile')}</option>
            {#each profiles as profile}
              <option value={profile.id}>{profile.name} ({profile.provider}/{profile.model})</option>
            {/each}
          </select>
        </div>

        <div>
          <label for="byok-key" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('byok.apiKey')}
          </label>
          <input
            id="byok-key"
            type="password"
            bind:value={apiKey}
            placeholder={t('byok.apiKeyPlaceholder')}
            required
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label for="byok-label" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('byok.label')}
          </label>
          <input
            id="byok-label"
            type="text"
            bind:value={label}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <button
          type="submit"
          disabled={saving || !selectedProfile || !apiKey}
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600
                 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? '…' : t('byok.addKey')}
        </button>
      </form>
    </div>
  {/if}
</div>
