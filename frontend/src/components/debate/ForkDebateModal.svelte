<script>
  /**
   * ForkDebateModal — Modal zum Forken einer abgeschlossenen Debatte.
   * Ermöglicht das Erstellen einer Kopie mit optionalen Änderungen.
   */
  import { forkDebate, getAgentPersonas, getLLMProfiles, getPromptVariants } from '../../lib/api.js';
  import { loading, error } from '../../lib/stores.js';
  import { i18n, locale } from '../../lib/i18n/index.js';

  let { debateId = null, debateTitle = '', onClose = () => {}, onCreated = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let newTitle = $state('');
  let forkFromRound = $state(null);
  let forkReason = $state('new_perspective');
  let modifiedPersonas = $state({});
  let modifiedPromptVariant = $state(null);

  let llmProfiles = $state([]);
  let promptVariants = $state([]);
  let personaOptions = $state([]);
  let roles = ['strategist', 'critic', 'optimizer', 'moderator'];

  $effect(() => {
    loadProfiles();
  });

  async function loadProfiles() {
    try {
      llmProfiles = await getLLMProfiles();
    } catch { /* ignore */ }
    try {
      promptVariants = await getPromptVariants();
    } catch { /* ignore */ }
    try {
      const personas = await getAgentPersonas();
      personaOptions = personas;
    } catch { /* ignore */ }
  }

  let isSubmitting = $state(false);

  const forkReasons = [
    { value: 'new_perspective', labelKey: 'fork.reason.new_perspective' },
    { value: 'consensus_breakdown', labelKey: 'fork.reason.consensus_breakdown' },
    { value: 'branching', labelKey: 'fork.reason.branching' },
  ];

  async function handleSubmit() {
    if (!debateId) return;

    isSubmitting = true;
    $error = null;

    try {
      const body = {
        new_title: newTitle.trim(),
        fork_from_round: forkFromRound,
        fork_reason: forkReason,
      };

      // Only include modified_personas if there are actual changes
      const personaEntries = Object.entries(modifiedPersonas).filter(([, v]) => v !== null && v !== '');
      if (personaEntries.length > 0) {
        body.modified_personas = Object.fromEntries(personaEntries);
      }

      if (modifiedPromptVariant) {
        body.modified_prompt_variant = modifiedPromptVariant;
      }

      const result = await forkDebate(debateId, body);
      $autoStartDebate = true;
      onCreated(result);
      onClose();
    } catch (err) {
      $error = err.message;
    } finally {
      isSubmitting = false;
    }
  }
</script>

{#if $i18n['fork.title']}
<div class="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center z-50 p-4">
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
    <div class="p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          🍴 {t('fork.title')}
        </h3>
        <button
          onclick={onClose}
          class="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >
          ✕
        </button>
      </div>

      <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {t('fork.description')}
      </p>

      {#if $error}
        <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 mb-4 text-red-700 dark:text-red-300 text-sm">
          {$error}
        </div>
      {/if}

      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.newTitle')} <span class="text-red-500">*</span>
          </label>
          <input
            type="text"
            bind:value={newTitle}
            required
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.forkFromRound')}
          </label>
          <input
            type="number"
            bind:value={forkFromRound}
            min="0"
            placeholder="Aktuelle Runde (alle behalten)"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Runden &gt; diesem Wert werden entfernt
          </p>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.forkReason')}
          </label>
          <select
            bind:value={forkReason}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {#each forkReasons as reason}
              <option value={reason.value}>{t(reason.labelKey)}</option>
            {/each}
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.modifiedPersonas')}
          </label>
          <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
            {t('fork.modifiedPersonasHint')}
          </p>
          {#each roles as role}
            <div class="flex items-center gap-2 mb-2">
              <span class="text-sm text-gray-600 dark:text-gray-400 w-24 capitalize">
                {role}
              </span>
              <select
                class="flex-1 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                onchange={(e) => {
                  if (e.target.value) {
                    modifiedPersonas[role] = e.target.value;
                  } else {
                    delete modifiedPersonas[role];
                  }
                }}
              >
                <option value="">Standard</option>
                {#each personaOptions.filter(p => p.role === role || p.role === role.replace('critic', 'critic').replace('optimizer', 'optimizer')), persona in personaOptions}
                  <option value={persona.id}>{persona.name}</option>
                {/each}
              </select>
            </div>
          {/each}
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.modifiedPromptVariant')}
          </label>
          <select
            bind:value={modifiedPromptVariant}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value={null}>Standard</option>
            {#each promptVariants as variant}
              <option value={variant.id}>{variant.name || variant.id}</option>
            {/each}
          </select>
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
          disabled={isSubmitting || !newTitle.trim()}
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700
                 transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                 flex items-center gap-2"
        >
          {#if isSubmitting}
            <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          {/if}
          {isSubmitting ? t('fork.submitting') : t('fork.submit')}
        </button>
      </div>
    </div>
  </div>
</div>
{/if}
