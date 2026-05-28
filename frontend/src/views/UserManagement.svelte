<script>
  import { onMount } from 'svelte';
  import { currentUser } from '../lib/stores/auth.svelte.js';
  import { i18n } from '../lib/i18n/index.js';
  import { listUsers, inviteUser, deleteUser } from '../lib/auth.js';
  import { addToast } from '../lib/stores.js';

  let t = $derived((key, params) => {
    const val = $i18n[key];
    if (!val) return key;
    if (params) {
      return Object.entries(params).reduce(
        (s, [k, v]) => s.replace(new RegExp(`\\{${k}\\}`, 'g'), v),
        val
      );
    }
    return val;
  });

  let users = $state([]);
  let loading = $state(true);
  let loadError = $state('');

  // Invite form
  let showInviteForm = $state(false);
  let inviteEmail = $state('');
  let inviteDisplayName = $state('');
  let invitePassword = $state('');
  let inviteRole = $state('viewer');
  let inviting = $state(false);
  let inviteError = $state('');

  // Delete confirm
  let deleteTarget = $state(null);

  async function loadUsers() {
    loading = true;
    loadError = '';
    try {
      users = await listUsers();
    } catch (e) {
      loadError = e.message || t('users.loadError');
    } finally {
      loading = false;
    }
  }

  onMount(loadUsers);

  async function handleInvite(e) {
    e.preventDefault();
    inviteError = '';
    if (!inviteEmail || !invitePassword) {
      inviteError = 'Email and password are required';
      return;
    }
    if (invitePassword.length < 8) {
      inviteError = 'Password must be at least 8 characters';
      return;
    }
    inviting = true;
    try {
      const displayName = inviteDisplayName || inviteEmail.split('@')[0];
      await inviteUser(inviteEmail, displayName, invitePassword, inviteRole);
      addToast(t('users.inviteSuccess', { email: inviteEmail }), 'success');
      showInviteForm = false;
      inviteEmail = '';
      inviteDisplayName = '';
      invitePassword = '';
      inviteRole = 'viewer';
      await loadUsers();
    } catch (e) {
      inviteError = e.message;
    } finally {
      inviting = false;
    }
  }

  function confirmDelete(user) {
    deleteTarget = user;
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteUser(deleteTarget.id);
      addToast(t('users.removeSuccess'), 'success');
      deleteTarget = null;
      await loadUsers();
    } catch (e) {
      addToast(e.message, 'error');
      deleteTarget = null;
    }
  }

  let isAdmin = $derived($currentUser?.role === 'admin');
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('users.title')}</h2>
    {#if isAdmin}
      <button
        class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
        onclick={() => { showInviteForm = !showInviteForm; inviteError = ''; }}>
        + {t('users.invite')}
      </button>
    {/if}
  </div>

  {#if !isAdmin}
    <div class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 text-yellow-700 dark:text-yellow-300">
      Admin access required.
    </div>
  {/if}

  {#if showInviteForm}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-6">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('users.invite')}</h3>
      <form onsubmit={handleInvite} class="space-y-4">
        {#if inviteError}
          <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-red-700 dark:text-red-300 text-sm">{inviteError}</div>
        {/if}
        <div>
          <label for="invite-email" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('auth.email')}</label>
          <input id="invite-email" type="email" bind:value={inviteEmail} placeholder={t('users.inviteEmail')} required
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
        </div>
        <div>
          <label for="invite-display" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('auth.displayName')}</label>
          <input id="invite-display" type="text" bind:value={inviteDisplayName} placeholder={t('auth.displayNamePlaceholder')}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
        </div>
        <div>
          <label for="invite-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('auth.password')}</label>
          <input id="invite-password" type="password" bind:value={invitePassword} placeholder={t('auth.passwordPlaceholderRegister')} required minlength="8"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
        </div>
        <div>
          <label for="invite-role" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('users.inviteRole')}</label>
          <select id="invite-role" bind:value={inviteRole}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
            <option value="admin">{t('auth.role_admin')}</option>
            <option value="editor">{t('auth.role_editor')}</option>
            <option value="viewer" selected>{t('auth.role_viewer')}</option>
          </select>
        </div>
        <div class="flex items-center justify-end gap-3 pt-2">
          <button type="button" class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={() => { showInviteForm = false; inviteError = ''; }}>
            {t('common.cancel')}
          </button>
          <button type="submit" class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50" disabled={inviting}>
            {inviting ? '...' : t('users.inviteSubmit')}
          </button>
        </div>
      </form>
    </div>
  {/if}

  {#if loading}
    <div class="flex items-center justify-center h-32">
      <p class="text-gray-500 dark:text-gray-400">{t('common.loading')}</p>
    </div>
  {:else if loadError}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300">{loadError}</div>
  {:else if users.length === 0}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-center h-32">
        <p class="text-gray-500 dark:text-gray-400">{t('users.noUsers')}</p>
      </div>
    </div>
  {:else}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
      <table class="w-full text-sm text-left">
        <thead class="text-xs text-gray-700 dark:text-gray-300 uppercase bg-gray-50 dark:bg-gray-700">
          <tr>
            <th class="px-4 py-3">{t('auth.email')}</th>
            <th class="px-4 py-3">{t('auth.displayName')}</th>
            <th class="px-4 py-3">{t('auth.role').replace('{role}', '')}</th>
            <th class="px-4 py-3">Status</th>
            <th class="px-4 py-3 text-right">{t('common.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {#each users as user (user.id)}
            <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
              <td class="px-4 py-3 font-medium text-gray-800 dark:text-white">{user.email}</td>
              <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{user.display_name}</td>
              <td class="px-4 py-3">
                {#if user.role === 'admin'}
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">{t('auth.role_admin')}</span>
                {:else if user.role === 'editor'}
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">{t('auth.role_editor')}</span>
                {:else}
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{t('auth.role_viewer')}</span>
                {/if}
              </td>
              <td class="px-4 py-3">
                {#if user.is_active}
                  <span class="text-green-600 dark:text-green-400">Active</span>
                {:else}
                  <span class="text-red-600 dark:text-red-400">Inactive</span>
                {/if}
              </td>
              <td class="px-4 py-3 text-right">
                {#if isAdmin && user.id !== $currentUser?.id}
                  <button class="text-xs px-2 py-1 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors" onclick={() => confirmDelete(user)}>
                    {t('users.remove')}
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Delete Confirm Dialog -->
{#if deleteTarget}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={() => deleteTarget = null} role="dialog" aria-modal="true">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6" role="presentation" onclick={(e) => e.stopPropagation()}>
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">{t('users.remove')}</h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">{t('users.removeConfirm', { name: deleteTarget.display_name || deleteTarget.email })}</p>
      <div class="flex items-center justify-end gap-3">
        <button class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onclick={() => deleteTarget = null}>{t('common.cancel')}</button>
        <button class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors" onclick={handleDelete}>{t('users.remove')}</button>
      </div>
    </div>
  </div>
{/if}
