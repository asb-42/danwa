<script>
  /**
   * ConfirmDialog — Reusable accessible confirmation modal.
   *
   * Replaces blocking window.confirm() calls with a styled, theme-aware,
   * keyboard-navigable dialog. Use for destructive actions or any prompt
   * that needs explicit user consent.
   *
   * Usage:
   *   <ConfirmDialog
   *     open={showConfirm}
   *     title={t('backup.deleteTitle')}
   *     message={t('backup.confirmDelete')}
   *     confirmLabel={t('common.delete')}
   *     cancelLabel={t('common.cancel')}
   *     variant="danger"
   *     onConfirm={handleDelete}
   *     onCancel={() => showConfirm = false}
   *   />
   */
  import { tStore } from '../lib/i18n/index.js';

  let {
    open = false,
    title = '',
    message = '',
    detail = '',
    confirmLabel = '',
    cancelLabel = '',
    variant = 'danger', // 'danger' | 'warning' | 'info'
    onConfirm = () => {},
    onCancel = () => {},
  } = $props();

  let t = $derived($tStore);

  let confirmText = $derived(confirmLabel || t('common.confirm'));
  let cancelText = $derived(cancelLabel || t('common.cancel'));
  let dialogEl = $state(null);

  $effect(() => {
    if (open && dialogEl) {
      dialogEl.focus();
    }
  });

  function handleKeydown(e) {
    if (!open) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      onConfirm();
    }
  }

  function variantClasses() {
    switch (variant) {
      case 'danger':
        return {
          icon: '⚠️',
          iconBg: 'bg-red-100 dark:bg-red-900/40',
          confirm: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
        };
      case 'warning':
        return {
          icon: '⚠️',
          iconBg: 'bg-amber-100 dark:bg-amber-900/40',
          confirm: 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500',
        };
      default:
        return {
          icon: '❔',
          iconBg: 'bg-blue-100 dark:bg-blue-900/40',
          confirm: 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500',
        };
    }
  }

  let v = $derived(variantClasses());
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
    onclick={onCancel}
    onkeydown={(e) => { if (e.key === 'Escape') onCancel(); }}
    role="presentation"
  >
    <div
      bind:this={dialogEl}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-message"
      tabindex="-1"
      class="bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 max-w-md w-full focus:outline-none"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div class="flex items-start gap-4 p-6 pb-4">
        <div class="flex-shrink-0 w-10 h-10 rounded-full {v.iconBg} flex items-center justify-center text-xl" aria-hidden="true">
          {v.icon}
        </div>
        <div class="flex-1 min-w-0">
          {#if title}
            <h3 id="confirm-dialog-title" class="text-lg font-semibold text-gray-900 dark:text-white">
              {title}
            </h3>
          {/if}
          {#if message}
            <p id="confirm-dialog-message" class="mt-2 text-sm text-gray-600 dark:text-gray-400 whitespace-pre-line">
              {message}
            </p>
          {/if}
          {#if detail}
            <p class="mt-2 text-xs text-gray-500 dark:text-gray-500 italic">
              {detail}
            </p>
          {/if}
        </div>
      </div>

      <div class="flex justify-end gap-2 px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 rounded-b-lg">
        <button
          type="button"
          onclick={onCancel}
          class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {cancelText}
        </button>
        <button
          type="button"
          onclick={onConfirm}
          class="px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors focus:outline-none focus:ring-2 {v.confirm}"
        >
          {confirmText}
        </button>
      </div>
    </div>
  </div>
{/if}
