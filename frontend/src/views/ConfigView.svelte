<script>
  import { loading, error } from '../lib/stores.js';
  import { i18n } from '../lib/i18n/index.js';

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  // Placeholder config — will be populated from API in Sprint 3
  let config = {
    default_max_rounds: 3,
    default_consensus_threshold: 0.8,
    llm_profile: 'default',
    agent_profile: 'default',
  };

  let saved = false;

  function handleSave() {
    // Placeholder — will POST to /api/v1/config in Sprint 3
    saved = true;
    setTimeout(() => { saved = false; }, 3000);
  }
</script>

<div class="space-y-6">
  <h2 class="text-2xl font-bold text-gray-800 dark:text-white">{t('config.title')}</h2>

  {#if $error}
    <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300" role="alert">
      {$error}
    </div>
  {/if}

  {#if saved}
    <div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-300" role="status">
      {t('config.saved')}
    </div>
  {/if}

  <!-- Debate defaults -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('config.debateDefaults')}</h3>

    <form on:submit|preventDefault={handleSave} class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="cfg-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.defaultMaxRounds')}
          </label>
          <input
            id="cfg-rounds"
            type="number"
            bind:value={config.default_max_rounds}
            min="1"
            max="10"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label for="cfg-threshold" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.defaultConsensusThreshold')}
          </label>
          <input
            id="cfg-threshold"
            type="number"
            bind:value={config.default_consensus_threshold}
            min="0"
            max="1"
            step="0.05"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="cfg-llm" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.llmProfile')}
          </label>
          <input
            id="cfg-llm"
            type="text"
            bind:value={config.llm_profile}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label for="cfg-agent" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('config.agentProfile')}
          </label>
          <input
            id="cfg-agent"
            type="text"
            bind:value={config.agent_profile}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <button
        type="submit"
        class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        {t('config.saveButton')}
      </button>
    </form>
  </div>

  <!-- Placeholder sections -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('config.llmProfiles')}</h3>
    <div class="flex items-center justify-center h-32 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">{t('config.llmProfilesPlaceholder')}</p>
    </div>
  </div>

  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('config.agentProfiles')}</h3>
    <div class="flex items-center justify-center h-32 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">{t('config.agentProfilesPlaceholder')}</p>
    </div>
  </div>

  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('config.promptVariants')}</h3>
    <div class="flex items-center justify-center h-32 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">{t('config.promptVariantsPlaceholder')}</p>
    </div>
  </div>
</div>
