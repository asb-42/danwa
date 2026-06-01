<script>
  import { onMount } from 'svelte';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { activeCase } from '../lib/stores.js';
  import { getMyTenants, selectTenant } from '../lib/auth.js';
  import { i18n } from '../lib/i18n/index.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let tenants = $state([]);
  let isOpen = $state(false);
  let isLoading = $state(false);

  onMount(() => {
    loadTenants();
  });

  async function loadTenants() {
    isLoading = true;
    try {
      tenants = await getMyTenants();
      if (!$currentTenant && tenants.length > 0) {
        currentTenant.set({ id: tenants[0].tenant_id, name: tenants[0].tenant_name || tenants[0].tenant_id });
      }
    } catch (err) {
      console.warn('Could not load tenants:', err);
    } finally {
      isLoading = false;
    }
  }

  async function switchTenant(tenant) {
    try {
      const data = await selectTenant(tenant.tenant_id);
      currentTenant.set({ id: tenant.tenant_id, name: tenant.tenant_name || tenant.tenant_id });
      activeCase.set(null);
      isOpen = false;
    } catch (err) {
      console.error('Failed to switch tenant:', err);
    }
  }

  function handleClickOutside(event) {
    if (!event.target.closest('.tenant-selector')) {
      isOpen = false;
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="tenant-selector relative">
  <button
    class="flex items-center gap-1.5 px-2 py-1 text-xs rounded-md
           border border-gray-200 dark:border-gray-600
           bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300
           hover:border-blue-400 dark:hover:border-blue-500
           transition-colors"
    onclick={(e) => { e.stopPropagation(); isOpen = !isOpen; if (isOpen) loadTenants(); }}
    aria-haspopup="listbox"
    aria-expanded={isOpen}
  >
    <span class="text-sm" aria-hidden="true">🏢</span>
    {#if $currentTenant}
      <span class="truncate max-w-[100px]">{$currentTenant.name}</span>
    {:else}
      <span class="text-gray-400">{t('tenants.noTenant')}</span>
    {/if}
    <svg class="w-3 h-3 text-gray-400 flex-shrink-0 transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  {#if isOpen}
    <div
      class="absolute right-0 z-50 mt-1 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg
             border border-gray-200 dark:border-gray-700 max-h-48 overflow-y-auto"
      role="listbox"
    >
      {#if isLoading}
        <div class="px-3 py-2 text-sm text-gray-500">{t('common.loading')}</div>
      {:else if tenants.length === 0}
        <div class="px-3 py-2 text-sm text-gray-500">{t('tenants.noTenants')}</div>
      {:else}
        {#each tenants as tenant}
          <button
            class="w-full text-left px-3 py-2 text-sm flex items-center justify-between
                   hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors
                   {$currentTenant?.id === tenant.tenant_id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700' : 'text-gray-700 dark:text-gray-300'}"
            onclick={() => switchTenant(tenant)}
            role="option"
            aria-selected={$currentTenant?.id === tenant.tenant_id}
          >
            <span class="truncate">{tenant.tenant_name || tenant.tenant_id}</span>
            {#if $currentTenant?.id === tenant.tenant_id}
              <span class="text-blue-600 flex-shrink-0">✓</span>
            {/if}
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</div>
