<!-- ProfileView.svelte — User profile and password change -->

<script>
  import { currentUser } from '../lib/stores/auth.svelte.js';
  import { tStore } from '../lib/i18n/index.js';
  import { changePassword } from '../lib/auth.js';
  import { addToast } from '../lib/stores.js';

  let t = $derived($tStore);

  let currentPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let saving = $state(false);
  let error = $state('');

  async function handleChangePassword(e) {
    e.preventDefault();
    error = '';

    if (newPassword !== confirmPassword) {
      error = t('profile.passwordMismatch');
      return;
    }

    saving = true;
    try {
      await changePassword(currentPassword, newPassword);
      addToast({ type: 'success', message: t('profile.passwordChanged') });
      currentPassword = '';
      newPassword = '';
      confirmPassword = '';
    } catch (err) {
      error = err.message || 'Error';
    } finally {
      saving = false;
    }
  }
</script>

<div class="max-w-2xl mx-auto p-6 space-y-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{t('profile.title')}</h1>

  <!-- Profile info -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 space-y-4">
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <span class="text-sm text-gray-500 dark:text-gray-400">{t('profile.name')}</span>
        <p class="text-gray-900 dark:text-white font-medium">{$currentUser?.display_name || '—'}</p>
      </div>
      <div>
        <span class="text-sm text-gray-500 dark:text-gray-400">{t('profile.email')}</span>
        <p class="text-gray-900 dark:text-white font-medium">{$currentUser?.email || '—'}</p>
      </div>
      <div>
        <span class="text-sm text-gray-500 dark:text-gray-400">{t('profile.role')}</span>
        <p class="text-gray-900 dark:text-white font-medium">
          {t(`auth.role_${$currentUser?.role}`) || $currentUser?.role || '—'}
        </p>
      </div>
      <div>
        <span class="text-sm text-gray-500 dark:text-gray-400">{t('profile.tenant')}</span>
        <p class="text-gray-900 dark:text-white font-medium">{$currentUser?.tenant_id || '—'}</p>
      </div>
    </div>
  </div>

  <!-- Change password -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
    <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('profile.changePassword')}</h2>

    {#if error}
      <div class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 text-sm" role="alert">
        {error}
      </div>
    {/if}

    <form onsubmit={handleChangePassword} class="space-y-4">
      <div>
        <label for="currentPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('profile.currentPassword')}
        </label>
        <input
          id="currentPassword"
          type="password"
          bind:value={currentPassword}
          required
          autocomplete="current-password"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      <div>
        <label for="newPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('profile.newPassword')}
        </label>
        <input
          id="newPassword"
          type="password"
          bind:value={newPassword}
          required
          minlength="8"
          autocomplete="new-password"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      <div>
        <label for="confirmPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('profile.confirmPassword')}
        </label>
        <input
          id="confirmPassword"
          type="password"
          bind:value={confirmPassword}
          required
          minlength="8"
          autocomplete="new-password"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                 bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      <button
        type="submit"
        disabled={saving}
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600
               disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {saving ? t('profile.saving') : t('profile.save')}
      </button>
    </form>
  </div>
</div>
