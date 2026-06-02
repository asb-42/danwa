<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import ExecutionPanel from '../components/blueprint/ExecutionPanel.svelte';
  import { getActiveWorkflowSession, clearActiveWorkflowSession, patchActiveWorkflowSession } from '../lib/workflowSession.js';

  /** @type {{ sessionId?: string|null, navigate?: function }} */
  let {
    sessionId = null,
    navigate = () => {},
  } = $props();

  let t = $derived($tStore);

  let activeSession = $state(null);
  let showExecutionPanel = $state(false);
  let executionSessionId = $state(null);
  let executionContext = $state('');

  onMount(() => {
    const s = getActiveWorkflowSession();
    if (s && s.sessionId === sessionId) {
      activeSession = s;
      executionSessionId = s.sessionId;
      executionContext = s.context || '';
      showExecutionPanel = true;
    } else if (sessionId) {
      // Session from URL but not in localStorage — still try to connect
      activeSession = { sessionId, workflowName: 'Execution' };
      executionSessionId = sessionId;
      showExecutionPanel = true;
    }
  });
</script>

<div class="p-6 space-y-6">
  <div class="flex items-center justify-between">
    <div>
      <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
        ⚡ {t('nav.activeExecution') || 'Live Execution'}
      </h2>
      {#if activeSession}
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {activeSession.workflowName || ''}
          {#if activeSession.sessionId}
            <span class="font-mono text-xs ml-2">({activeSession.sessionId})</span>
          {/if}
        </p>
      {/if}
    </div>
    <div class="flex gap-2">
      <button
        class="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        onclick={() => navigate('blueprint')}
      >
        🧩 {t('nav.canvas')}
      </button>
      <button
        class="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        onclick={() => { clearActiveWorkflowSession(); navigate('dashboard'); }}
      >
        ✕ {t('common.close')}
      </button>
    </div>
  </div>

  <ExecutionPanel
    workflowId=""
    sessionId={executionSessionId}
    context={executionContext}
    visible={showExecutionPanel}
    onclose={() => { navigate('dashboard'); }}
  />
</div>
