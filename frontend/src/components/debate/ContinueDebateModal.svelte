<script>
  /**
   * ContinueDebateModal — Modal zum Fortsetzen einer abgeschlossenen Debatte.
   * Ermöglicht das Erstellen einer neuen Debatte auf Basis der Ergebnisse.
   */
  import { continueDebate, getLLMProfiles } from '../../lib/api.js';
  import { error, addToast } from '../../lib/stores.js';
  import { tStore } from '../../lib/i18n/index.js';

  let { debateId = null, debateTitle = '', onClose = () => {}, onCreated = () => {} } = $props();

  let t = $derived($tStore);

  let newTitle = $state('');
  let focusTopic = $state('');
  let inheritPersonas = $state(true);
  let inheritLLM = $state(true);
  let inheritPromptVariant = $state(true);

  let llmProfiles = $state([]);

  $effect(() => {
    loadProfiles();
  });

  async function loadProfiles() {
    try {
      llmProfiles = await getLLMProfiles();
    } catch (e) {
      if (import.meta.env.DEV) console.warn('[ContinueDebateModal] failed to load LLM profiles:', e);
      addToast({ message: t('error.unknown'), type: 'error', timeout: 4000 });
    }
  }

  let isSubmitting = $state(false);

  async function handleSubmit() {
    if (!debateId) return;

    isSubmitting = true;
    error.set(null);

    try {
      const body = {
        new_title: newTitle.trim() || undefined,
        focus_topic: focusTopic.trim() || undefined,
      };

      const result = await continueDebate(debateId, body);
      autoStartDebate.set(true);
      onCreated(result);
      onClose();
    } catch (err) {
      error.set(err.message);
    } finally {
      isSubmitting = false;
    }
  }
</script>

{#if t('followup.title')}
<div class="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center z-50 p-4">
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
    <div class="p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          🔄 {t('followup.title')}
        </h3>
        <button
          onclick={onClose}
          class="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >
          ✕
        </button>
      </div>

      <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {t('followup.description')}
      </p>

      {#if $error}
        <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 mb-4 text-red-700 dark:text-red-300 text-sm">
          {$error}
        </div>
      {/if}

      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('debate.titleLabel')}
          </label>
          <input
            type="text"
            bind:value={newTitle}
            placeholder={t('followup.newTitlePlaceholder')}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {t('common.optional')}
          </p>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('followup.focusTopic')}
          </label>
          <input
            type="text"
            bind:value={focusTopic}
            placeholder={t('followup.focusTopicPlaceholder')}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {t('common.optional')}
          </p>
        </div>

        {#if debateTitle}
          <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-sm">
            <span class="text-gray-600 dark:text-gray-400">{t('debate.forkedFrom')}:</span>
            <span class="font-medium text-gray-800 dark:text-gray-200">{debateTitle}</span>
          </div>
        {/if}
      </div>

      <div class="mt-6 flex justify-end gap-3">
        <button
          onclick={onClose}
          class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300
                 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
          {t('common.cancel')}
        </button>
        <button
          onclick={handleSubmit}
          disabled={isSubmitting}
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:hover:bg-blue-600
                 transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                 flex items-center gap-2"
        >
          {#if isSubmitting}
            <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          {/if}
          {isSubmitting ? t('followup.submitting') : t('followup.submit')}
        </button>
      </div>
    </div>
  </div>
</div>
{/if}
