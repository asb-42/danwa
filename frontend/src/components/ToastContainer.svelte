<script>
  import { toasts, removeToast } from '../lib/stores.js';
  import { i18n } from '../lib/i18n/index.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const iconMap = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️',
  };
</script>

{#if $toasts.length > 0}
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
       aria-live="polite"
       aria-label="Notifications">
    {#each $toasts as toast (toast.id)}
      <div
        class="pointer-events-auto flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg transition-all duration-300
          {toast.type === 'success' ? 'bg-green-50 text-green-800 dark:bg-green-900 dark:text-green-200' :
           toast.type === 'error' ? 'bg-red-50 text-red-800 dark:bg-red-900 dark:text-red-200' :
           toast.type === 'warning' ? 'bg-yellow-50 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
           'bg-blue-50 text-blue-800 dark:bg-blue-900 dark:text-blue-200'}"
        role="alert"
      >
        <span class="text-lg flex-shrink-0">{iconMap[toast.type] || 'ℹ️'}</span>
        <span class="text-sm font-medium flex-1">{toast.message}</span>
        <button
          class="text-current opacity-50 hover:opacity-100 flex-shrink-0"
          onclick={() => removeToast(toast.id)}
          aria-label={t('common.close')}
        >
          ✕
        </button>
      </div>
    {/each}
  </div>
{/if}
