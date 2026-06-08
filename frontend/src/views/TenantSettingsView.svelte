<!-- TenantSettingsView.svelte — Tenant admin panel with tenant creation -->

<script>
  import { onMount } from 'svelte';
  import { currentUser } from '../lib/stores/auth.svelte.js';
  import { tStore } from '../lib/i18n/index.js';
  import { addToast } from '../lib/stores.js';
  import { request } from '../lib/api.js';
  import { listAllTenants, createTenant, getMyTenants, selectTenant } from '../lib/auth.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';

  let t = $derived($tStore);

  let tenant = $state(null);
  let users = $state([]);
  let loading = $state(true);
  let error = $state('');

  // All tenants list (admin only)
  let allTenants = $state([]);
  let showCreateForm = $state(false);
  let newTenantName = $state('');
  let newTenantPlan = $state('free');
  let creating = $state(false);

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
      // Also load all tenants for admin
      if ($currentUser?.role === 'admin') {
        try { allTenants = await listAllTenants(); } catch {}
      }
    } catch (e) {
      error = e.message || t('tenant.loadError');
    } finally {
      loading = false;
    }
  }

  onMount(loadTenant);

  async function handleCreateTenant(e) {
    e.preventDefault();
    if (!newTenantName.trim()) return;
    creating = true;
    try {
      const created = await createTenant({ name: newTenantName.trim(), plan: newTenantPlan });
      addToast({ type: 'success', message: t('tenant.createSuccess') });
      newTenantName = '';
      newTenantPlan = 'free';
      showCreateForm = false;
      // Switch to the new tenant
      try {
        const data = await selectTenant(created.id);
        if (data?.access_token && data?.refresh_token && data?.user) {
          // Auth tokens updated by selectTenant
        }
        currentTenant.set({ id: created.id, name: created.name });
      } catch {}
      await loadTenant();
    } catch (e) {
      addToast({ type: 'error', message: e.message || t('tenant.createError') });
    } finally {
      creating = false;
    }
  }

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

  async function switchToTenant(tenantId, tenantName) {
    try {
      const data = await selectTenant(tenantId);
      if (data?.access_token) {
        // Auth tokens updated
      }
      currentTenant.set({ id: tenantId, name: tenantName });
      await loadTenant();
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    }
  }
</script>

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

<div class="max-w-3xl mx-auto p-6 space-y-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{t('tenant.title')}</h1>

  {#if loading}
    <p class="text-gray-500 dark:text-gray-400">Loading…</p>
  {:else if error}
    <div class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300" role="alert">
      {error}
    </div>
  {:else}
    <!-- All Tenants (admin only) -->
    {#if $currentUser?.role === 'admin' && allTenants.length > 0}
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-white">{t('tenant.allTenants')}</h2>
          <button
            onclick={() => showCreateForm = !showCreateForm}
            class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            {showCreateForm ? '✕' : `+ ${t('tenant.create')}`}
          </button>
        </div>

        {#if showCreateForm}
          <form onsubmit={handleCreateTenant} class="mb-4 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-3">
            <div class="flex flex-wrap gap-3 items-end">
              <div class="flex-1 min-w-[200px]">
                <label for="new-tenant-name" class="block text-sm text-gray-600 dark:text-gray-400 mb-1">{t('tenant.createName')}</label>
                <input
                  id="new-tenant-name"
                  type="text"
                  bind:value={newTenantName}
                  placeholder={t('tenant.createName')}
                  required
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm
                         focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label for="new-tenant-plan" class="block text-sm text-gray-600 dark:text-gray-400 mb-1">{t('tenant.createPlan')}</label>
                <select
                  id="new-tenant-plan"
                  bind:value={newTenantPlan}
                  class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm
                         focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="free">{t('tenant.plan.free')}</option>
                  <option value="pro">{t('tenant.plan.pro')}</option>
                  <option value="enterprise">{t('tenant.plan.enterprise')}</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={creating || !newTenantName.trim()}
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600
                       disabled:opacity-50 text-sm transition-colors"
              >
                {creating ? '…' : t('tenant.createSubmit')}
              </button>
            </div>
          </form>
        {/if}

        <div class="divide-y divide-gray-200 dark:divide-gray-700">
          {#each allTenants as t2}
            <button
              class="w-full text-left flex items-center justify-between py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors rounded px-2
                     {$currentTenant?.id === t2.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}"
              onclick={() => switchToTenant(t2.id, t2.name)}
            >
              <div>
                <p class="text-gray-900 dark:text-white font-medium">{t2.name}</p>
                <p class="text-xs text-gray-500 dark:text-gray-400">{t2.id} · {t2.plan}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 text-xs rounded-full
                  {t2.plan === 'enterprise' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' :
                   t2.plan === 'pro' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                   'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}">
                  {t(`tenant.plan.${t2.plan}`) || t2.plan}
                </span>
                {#if $currentTenant?.id === t2.id}
                  <span class="text-blue-600">✓</span>
                {/if}
              </div>
            </button>
          {/each}
        </div>
      </div>
    {/if}

    {#if tenant}
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
          {@render QuotaBar(t('tenant.projectsUsed'), tenant.used_projects, tenant.max_projects)}
          {@render QuotaBar(t('tenant.debatesUsed'), tenant.used_concurrent_debates, tenant.max_concurrent_debates)}
          {@render QuotaBar(t('tenant.documentsUsed'), tenant.used_documents, tenant.max_documents)}
          {@render QuotaBar(t('tenant.storageUsed'), tenant.used_storage_mb, tenant.max_storage_mb)}
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
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600
                     disabled:opacity-50 text-sm transition-colors"
            >
              {inviting ? '…' : t('tenant.inviteSubmit')}
            </button>
          </form>
        </div>
      </div>
    {/if}
  {/if}
</div>
