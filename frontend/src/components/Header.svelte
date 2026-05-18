<script>
  import { createEventDispatcher } from 'svelte';
  import { healthStatus, appVersion } from '../lib/stores.js';
  import { i18n } from '../lib/i18n/index.js';
  import LanguageSwitcher from './LanguageSwitcher.svelte';
  import ProjectSelector from './ProjectSelector.svelte';

  const dispatch = createEventDispatcher();
  let { isAssistantOpen } = $props();

  function handleToggle() {
    dispatch('toggle');
  }

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let statusColor = $derived($healthStatus.status === 'ok'
    ? 'bg-green-500'
    : $healthStatus.status === 'unknown'
      ? 'bg-yellow-500'
      : 'bg-red-500');
</script>

<header class="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
  <h1 class="text-lg font-semibold text-gray-800 dark:text-white">
    Debate Engine
  </h1>

  <div class="flex items-center space-x-4">
    <!-- Project selector -->
    <ProjectSelector compact={true} />

    <!-- Language switcher -->
    <LanguageSwitcher />

    <!-- Version badge -->
    {#if $appVersion}
      <span class="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-full" title={t('app.versionLabel')}>
        v{$appVersion}
      </span>
    {/if}

    <!-- Health indicator -->
    <div class="flex items-center space-x-2" aria-label="Backend status: {$healthStatus.status}">
      <span class="relative flex h-3 w-3">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full {statusColor} opacity-75"></span>
        <span class="relative inline-flex rounded-full h-3 w-3 {statusColor}"></span>
      </span>
      <span class="text-sm text-gray-600 dark:text-gray-300">
        {$healthStatus.status}
        {#if $healthStatus.version}
          <span class="text-xs text-gray-500">({$healthStatus.version})</span>
        {/if}
      </span>
    </div>

    <!-- Kitsune toggle button -->
    <button
      class="kitsune-toggle"
      class:active={isAssistantOpen}
      onclick={handleToggle}
      title="Danwa Kitsune öffnen/schließen"
      aria-label="Danwa Kitsune"
    >
      <span class="kitsune-icon">🦊</span>
      <span class="kitsune-label">Kitsune</span>
    </button>
  </div>
</header>

<style>
  .kitsune-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 13px;
    color: #374151;
  }

  .kitsune-toggle:hover {
    background: #e5e7eb;
  }

  .kitsune-toggle.active {
    background: #667eea;
    color: white;
    border-color: #667eea;
  }

  .kitsune-icon {
    font-size: 16px;
  }

  .kitsune-label {
    font-weight: 500;
  }

  @media (max-width: 768px) {
    .kitsune-label {
      display: none;
    }

    .kitsune-toggle {
      padding: 6px 8px;
    }
  }
</style>
