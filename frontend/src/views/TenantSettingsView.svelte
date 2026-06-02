<!-- TenantSettingsView.svelte — Tenant admin panel -->

<script>
  import { onMount } from 'svelte';
  import { currentUser } from '../lib/stores/auth.svelte.js';
  import { tStore } from '../lib/i18n/index.js';
  import { addToast } from '../lib/stores.js';
  import { request } from '../lib/api.js';

  let t = $derived($tStore);

  let tenant = $state(null);
  let users = $state([]);
  let loading = $state(true);
  let error = $state('');

  // Invite form
  let inviteEmail = $state('');
  let inviteDisplayName = $state('');
  let invitePassword = $state('');
  let inviteRole = $state('viewer');
  let inviting = $state(false);

  // Delete confirm
  let deleteTarget = $state(null);

  async function loadTenant() {
    loading = true;
    error = '';
    try {
      const [tData, uData] = await Promise.all([
        request('/api/v1/tenants/current'),
        request('/api/v1/tenants/current/users'),
      ]);
      tenant = tData;
      users = uData;
    } catch (e) {
      error = e.message || t('tenant.loadError');
    } finally {
      loading = false;
    }
  }

  onMount(loadTenant);

  async function handleInvite(e) {
    e.preventDefault();
    inviting = true;
    try {
      await request('/api/v1/tenants/current/invite', {
        method: 'POST',
        body: JSON.stringify({
          email: inviteEmail,
          display_name: inviteDisplayName || inviteEmail.split('@')[0],
          password: invitePassword,
          role: inviteRole,
        }),
      });
      addToast({ type: 'success', message: t('tenant.inviteSuccess') });
      inviteEmail = '';
      inviteDisplayName = '';
      invitePassword = '';
      inviteRole = 'viewer';
      await loadTenant();
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    } finally {
      inviting = false;
    }
  }

  async function handleDelete(user) {
    try {
      await request(`/api/v1/tenants/current/users/${user.id}`, { method: 'DELETE' });
      addToast({ type: 'success', message: t('tenant.removeSuccess') });
      deleteTarget = null;
      await loadTenant();
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    }
  }
</script>

<div class="max-w-3xl mx-auto p-6 space-y-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{t('tenant.title')}</h1>

  {#if loading}
    <p class="text-gray-500 dark:text-gray-400">Loading…</p>
  {:else if error}
    <div class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300" role="alert">
      {error}
    </div>
  {:else if tenant}
    <!-- Tenant info -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <span class="text-sm text-gray-500 dark:text-gray-400">{t('tenant.name')}</span>
          <p class="text-gray-900 dark:text-white font-medium">{tenant.name}</p>
        </div>
        <div>
          <span class="text-sm text-gray-500 dark:text-gray-400">{t('tenant.plan')}</span>
          <p class="text-gray-900 dark:text-white font-medium">
            <span class="px-2 py-0.5 text-xs rounded-full
              {tenant.plan === 'enterprise' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' :
               tenant.plan === 'pro' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
               'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}">
              {t(`tenant.plan.${tenant.plan}`) || tenant.plan}
            </span>
          </p>
        </div>
      </div>
    </div>

    <!-- Quotas -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">{t('tenant.quotas')}</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <QuotaBar label={t('tenant.projectsUsed')} used={tenant.used_projects} max={tenant.max_projects} />
        <QuotaBar label={t('tenant.debatesUsed')} used={tenant.used_concurrent_debates} max={tenant.max_concurrent_debates} />
        <QuotaBar label={t('tenant.documentsUsed')} used={tenant.used_documents} max={tenant.max_documents} />
        <QuotaBar label={t('tenant.storageUsed')} used={tenant.used_storage_mb} max={tenant.max_storage_mb} />
      </div>
    </div>

    <!-- Users -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        {t('tenant.users')} ({users.length})
      </h2>

      {#if users.length === 0}
        <p class="text-gray-500 dark:text-gray-400 text-sm">{t('tenant.noUsers')}</p>
      {:else}
        <div class="divide-y divide-gray-200 dark:divide-gray-700">
          {#each users as user}
            <div class="flex items-center justify-between py-3">
              <div>
                <p class="text-gray-900 dark:text-white font-medium">{user.display_name}</p>
                <p class="text-sm text-gray-500 dark:text-gray-400">{user.email}</p>
              </div>
              <div class="flex items-center gap-3">
                <span class="px-2 py-0.5 text-xs rounded-full
                  {user.role === 'admin' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                   user.role === 'editor' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                   'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}">
                  {t(`auth.role_${user.role}`) || user.role}
                </span>
                {#if user.id !== $currentUser?.id}
                  {#if deleteTarget?.id === user.id}
                    <button
                      onclick={() => handleDelete(user)}
                      class="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                    >
                      {t('tenant.remove')}?
                    </button>
                    <button
                      onclick={() => deleteTarget = null}
                      class="px-2 py-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                    >
                      Cancel
                    </button>
                  {:else}
                    <button
                      onclick={() => deleteTarget = user}
                      class="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                    >
                      {t('tenant.remove')}
                    </button>
                  {/if}
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}

      <!-- Invite form -->
      <div class="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{t('tenant.invite')}</h3>
        <form onsubmit={handleInvite} class="flex flex-wrap gap-3 items-end">
          <div class="flex-1 min-w-[200px]">
            <input
              type="email"
              bind:value={inviteEmail}
              placeholder={t('tenant.inviteEmail')}
              required
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <input
              type="password"
              bind:value={invitePassword}
              placeholder="Password"
              required
              minlength="8"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <select
              bind:value={inviteRole}
              class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="viewer">{t('auth.role_viewer')}</option>
              <option value="editor">{t('auth.role_editor')}</option>
              <option value="admin">{t('auth.role_admin')}</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={inviting}
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700
                   disabled:opacity-50 text-sm transition-colors"
          >
            {inviting ? '…' : t('tenant.inviteSubmit')}
          </button>
        </form>
      </div>
    </div>
  {/if}
</div>

{#snippet QuotaBar(label, used, max)}
  {@const usedVal = typeof used === 'number' ? used : 0}
  {@const maxVal = typeof max === 'number' && max > 0 ? max : 0}
  {@const pct = maxVal > 0 ? Math.min(100, Math.round((usedVal / maxVal) * 100)) : 0}
  {@const overLimit = maxVal > 0 && usedVal > maxVal}
  <div class="space-y-1">
    <div class="flex justify-between text-sm">
      <span class="text-gray-700 dark:text-gray-300">{label}</span>
      <span class="text-gray-500 dark:text-gray-400 tabular-nums">{usedVal} / {maxVal || '∞'}</span>
    </div>
    <div
      class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden"
      role="meter"
      aria-label={label}
      aria-valuenow={usedVal}
      aria-valuemin={0}
      aria-valuemax={maxVal || undefined}
    >
      <div
        class="h-full rounded-full transition-all {overLimit ? 'bg-red-500' : 'bg-blue-500'}"
        style="width: {pct}%"
      ></div>
    </div>
  </div>
{/snippet}
