<script>
  /**
   * ExtensionRequestPanel — Modal shown when a debate extension is requested.
   * Allows the moderator to grant or deny additional rounds.
   */
  import { decideExtension, getHITLStatus } from '../../lib/hitl.js';
  import { hitlStatus } from '../../lib/stores/hitl.svelte.js';
  import { locale, tStore } from '../../lib/i18n/index.js';

  let { debateId, extensionRequest } = $props();

  let t = $derived($tStore);

  let isProcessing = $state(false);
  let error = $state(null);
  let decision = $state(null);

  let consensusPercent = $derived(Math.round((extensionRequest?.current_consensus || 0) * 100));
  let thresholdPercent = $derived(Math.round((extensionRequest?.threshold || 0) * 100));

  async function handleDecision(grant) {
    decision = grant ? 'granted' : 'denied';
    isProcessing = true;
    error = null;

    try {
      await decideExtension(debateId, grant ? 'granted' : 'denied');
      // Refresh HITL status
      try {
        const status = await getHITLStatus(debateId);
        hitlStatus.set(status);
      } catch (e) { console.warn('[ExtensionRequestPanel] HITL status refresh failed:', e); }
    } catch (err) {
      error = err.message || t('error.unknown');
      decision = null;
    } finally {
      isProcessing = false;
    }
  }
</script>

{#if extensionRequest}
  <div class="mt-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
    <div class="flex items-start gap-3">
      <span class="text-xl mt-0.5">⏱️</span>
      <div class="flex-1">
        <h4 class="text-sm font-semibold text-amber-800 dark:text-amber-200 mb-2">
          {t('debate.extensionRequested')}
        </h4>
        <p class="text-sm text-amber-700 dark:text-amber-300 mb-3">
          {t('debate.extensionRequest')}
        </p>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
          <div class="bg-amber-100 dark:bg-amber-900/30 rounded p-2 text-center">
            <div class="text-amber-600 dark:text-amber-400 font-bold text-lg">{consensusPercent}%</div>
            <div class="text-amber-700 dark:text-amber-500">{t('debate.extensionCurrentConsensus')}</div>
          </div>
          <div class="bg-amber-100 dark:bg-amber-900/30 rounded p-2 text-center">
            <div class="text-amber-600 dark:text-amber-400 font-bold text-lg">{thresholdPercent}%</div>
            <div class="text-amber-700 dark:text-amber-500">{t('debate.extensionThreshold')}</div>
          </div>
          <div class="bg-amber-100 dark:bg-amber-900/30 rounded p-2 text-center">
            <div class="text-amber-600 dark:text-amber-400 font-bold text-lg">{extensionRequest.current_round}</div>
            <div class="text-amber-700 dark:text-amber-500">{t('debate.round')}</div>
          </div>
          <div class="bg-amber-100 dark:bg-amber-900/30 rounded p-2 text-center">
            <div class="text-amber-600 dark:text-amber-400 font-bold text-lg">{extensionRequest.max_rounds}</div>
            <div class="text-amber-700 dark:text-amber-500">{t('debate.maxRounds')}</div>
          </div>
        </div>
        {#if error}
          <p class="text-sm text-red-600 dark:text-red-400 mb-2">{error}</p>
        {/if}
        {#if !decision}
          <div class="flex gap-2 mt-2">
            <button
              class="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:hover:bg-green-600 transition-colors disabled:opacity-50 text-sm font-medium"
              onclick={() => handleDecision(true)}
              disabled={isProcessing}
            >
              {isProcessing ? '⏳' : '✅'} {t('debate.extensionGrant')}
            </button>
            <button
              class="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:hover:bg-red-600 transition-colors disabled:opacity-50 text-sm font-medium"
              onclick={() => handleDecision(false)}
              disabled={isProcessing}
            >
              {isProcessing ? '⏳' : '❌'} {t('debate.extensionDeny')}
            </button>
          </div>
        {:else}
          <p class="text-sm text-green-600 dark:text-green-400 mt-2 font-medium">
            {decision === 'granted' ? '✅ ' + t('debate.extensionGrant') : '❌ ' + t('debate.extensionDeny')}
          </p>
        {/if}
      </div>
    </div>
  </div>
{/if}
