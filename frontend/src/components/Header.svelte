<script>
  import { healthStatus } from '../lib/stores.js';
  import { i18n } from '../lib/i18n/index.js';
  import LanguageSwitcher from './LanguageSwitcher.svelte';

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  $: statusColor = $healthStatus.status === 'ok'
    ? 'bg-green-500'
    : $healthStatus.status === 'unknown'
      ? 'bg-yellow-500'
      : 'bg-red-500';
</script>

<header class="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
  <h1 class="text-lg font-semibold text-gray-800 dark:text-white">
    Debate Engine
  </h1>

  <div class="flex items-center space-x-4">
    <!-- Language switcher -->
    <LanguageSwitcher />

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
  </div>
</header>
