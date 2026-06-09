<script>
  /**
   * InputComposerView — "Neue Debatte" page.
   *
   * Integrates the Input Composer (plugin selector, STT, A2A approval,
   * workflow templates) with the DebateCreatePanel (full debate creation form).
   * After creating a debate, auto-navigates to "Laufende Debatte" and starts it.
   */
  import { get } from 'svelte/store';
  import { onDestroy } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { currentDebate, debates, autoStartDebate, activeCase } from '../lib/stores.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import {
    listInputPlugins,
    submitInput,
    launchWorkflow,
    getInputJobStatus,
    listInputJobs,
    approveA2A,
    rejectA2A,
  } from '../lib/input/inputApi.js';
  import { createInputJobTracker } from '../lib/input/inputJobStore.js';
  import { listWorkflowTemplates } from '../lib/blueprint/api.js';
  import { getCaseDocuments } from '../lib/api/case.js';
  import { setActiveWorkflowSession } from '../lib/workflowSession.js';
  import PluginSelector from '../components/input/PluginSelector.svelte';
  import STTMicrophoneButton from '../components/input/STTMicrophoneButton.svelte';
  import A2AApprovalCard from '../components/input/A2AApprovalCard.svelte';
  import WorkflowTemplatePicker from '../components/input/WorkflowTemplatePicker.svelte';
  import DebateCreatePanel from '../components/debate/DebateCreatePanel.svelte';
  import DebateExecutionDisplay from '../components/blueprint/DebateExecutionDisplay.svelte';

  /** @type {function} Navigation helper from App.svelte */
  let { navigate = () => {} } = $props();

  let t = $derived($tStore);

  // Input Composer state
  let plugins = $state([]);
  let selectedPlugin = $state('standard_text');
  let topic = $state('');
  let loading = $state(false);
  let error = $state(null);
  let activeJob = $state(null);
  let tracker = $state(null);
  let partialText = $state('');

  // A2A approval state
  let pendingA2A = $state([]);

  // Workflow template state
  let selectedTemplateId = $state('');
  let workflowTemplates = $state([]);

  // Workflow execution state (Input Composer → ExecutionPanel)
  let showExecutionPanel = $state(false);
  let executionSessionId = $state(null);
  let currentDebateTitle = $state('');
  let currentDebateId = $state(null);
  let launchError = $state(null);

  // Which mode is active: 'compose' (Input Composer) or 'form' (DebateCreatePanel)
  let inputMode = $state('form');

  // DMS / RAG state
  let documents = $state([]);
  let selectedDocumentIds = $state([]);
  let ragAutoRetrieve = $state(false);
  let includeDebateResults = $state(false);
  let includeDocumentAnalysis = $state(false);
  let completedDebates = $state([]);
  let loadingCompletedDebates = $state(false);

  // A2A polling interval reference
  let a2aPollInterval = $state(null);

  // Load plugins and workflow templates on mount
  $effect(() => {
    listInputPlugins()
      .then((p) => { plugins = p; })
      .catch((e) => { error = e.message; });
    listWorkflowTemplates()
      .then((templates) => {
        workflowTemplates = templates || [];
        // Phase 4: Pre-select first workflow template if none selected
        if (!selectedTemplateId && workflowTemplates.length > 0) {
          selectedTemplateId = workflowTemplates[0].id;
        }
      })
      .catch((e) => { if (import.meta.env.DEV) console.warn('Failed to load workflow templates:', e.message); });

    // Phase 3: Load case documents for RAG
    const tenant = $currentTenant;
    const caseObj = $activeCase;
    if (tenant?.id && caseObj?.id) {
      getCaseDocuments(tenant.id, caseObj.id)
        .then((docs) => { documents = docs || []; })
        .catch((e) => { if (import.meta.env.DEV) console.warn('Failed to load documents:', e.message) } );
    }

    // Phase 4: Start polling for pending A2A jobs
    startA2APolling();

    return () => {
      stopA2APolling();
    };
  });

  // --- Phase 3: A2A Pending Job Polling ---

  function startA2APolling() {
    if (a2aPollInterval) return;
    pollPendingA2A();
    a2aPollInterval = setInterval(pollPendingA2A, 5000);
  }

  function stopA2APolling() {
    if (a2aPollInterval) {
      clearInterval(a2aPollInterval);
      a2aPollInterval = null;
    }
  }

  onDestroy(() => {
    if (a2aPollInterval) {
      clearInterval(a2aPollInterval);
      a2aPollInterval = null;
    }
  });

  async function pollPendingA2A() {
    try {
      const jobs = await listInputJobs({ status: 'pending_approval', pluginKey: 'a2a_inbound' });
      pendingA2A = (jobs || []).map((j) => ({
        job_id: j.job_id,
        agent_id: j.processed_input?.source_metadata?.agent_id || 'unknown',
        topic: j.processed_input?.topic || '',
        task_id: j.job_id, // task_id == job_id for A2A inbound
      }));
    } catch (e) {
      // Silently ignore polling errors (server may not be ready)
      if (import.meta.env.DEV) console.warn('A2A poll failed:', e.message);
    }
  }

  function onPluginChange(key) {
    selectedPlugin = key;
    error = null;
  }

  function onPartial(text) {
    partialText = text;
  }

  function onFinal(text) {
    if (text) topic += (topic ? ' ' : '') + text;
    partialText = '';
  }

  function onTemplateChange(id) {
    selectedTemplateId = id;
  }

  async function handleSubmit() {
    if (!topic.trim()) {
      error = t('debate.enterCase') || 'Please enter a debate topic.';
      return;
    }
    loading = true;
    error = null;
    launchError = null;
    try {
      const result = await submitInput(selectedPlugin, {}, topic.trim());
      activeJob = result;

      if (result.status === 'completed') {
        // Standard text completes immediately — launch workflow right away
        await handleLaunch(result.job_id);
      } else if (result.status === 'processing' || result.status === 'pending_approval') {
        // STT or A2A — poll for completion, then launch
        tracker = createInputJobTracker(result.job_id);
        // Watch for completion via polling
        pollAndLaunch(result.job_id);
      }
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  /** Poll an input job until completed, then launch the workflow. */
  async function pollAndLaunch(jobId) {
    const maxAttempts = 30; // 60 seconds max (2s interval)
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const job = await getInputJobStatus(jobId);
        if (job.status === 'completed') {
          await handleLaunch(jobId);
          return;
        } else if (job.status === 'failed') {
          error = job.error_message || 'Input processing failed';
          return;
        }
        // pending_approval or processing — keep polling
      } catch (e) {
        error = e.message;
        return;
      }
    }
    error = 'Input processing timed out';
  }

  /** Launch workflow execution from a completed input job. */
  async function handleLaunch(jobId) {
    launchError = null;
    try {
      const options = {
        language: 'de',
        document_ids: selectedDocumentIds,
        rag_auto_retrieve: ragAutoRetrieve,
        include_debate_results: includeDebateResults,
        include_document_analysis: includeDocumentAnalysis,
      };
      if (includeDebateResults) {
        options.debate_result_ids = completedDebates.map(d => d.debate_id);
      }
      if (selectedTemplateId) {
        options.workflow_template_id = selectedTemplateId;
      }
      const result = await launchWorkflow(jobId, options);
      executionSessionId = result.session_id;
      currentDebateTitle = result.title || '';
      currentDebateId = result.debate_id || null;
      showExecutionPanel = true;
    } catch (e) {
      launchError = e.message || 'Failed to launch workflow';
      error = launchError;
    }
  }

  // --- Phase 3: A2A Approval Handlers ---

  async function handleApproveA2A(taskId) {
    try {
      await approveA2A(taskId);
      // Remove from pending list immediately
      pendingA2A = pendingA2A.filter(p => p.task_id !== taskId);
      // The approved job transitions to PROCESSING → COMPLETED.
      // Poll for completion and then launch.
      tracker = createInputJobTracker(taskId);
      pollAndLaunch(taskId);
    } catch (e) {
      error = e.message;
    }
  }

  async function handleRejectA2A(taskId) {
    try {
      await rejectA2A(taskId);
      pendingA2A = pendingA2A.filter(p => p.task_id !== taskId);
    } catch (e) {
      error = e.message;
    }
  }

  // --- DMS / RAG Helpers ---

  function toggleDocumentSelection(docId) {
    const idx = selectedDocumentIds.indexOf(docId);
    if (idx >= 0) {
      selectedDocumentIds = selectedDocumentIds.filter(id => id !== docId);
    } else {
      selectedDocumentIds = [...selectedDocumentIds, docId];
    }
  }

  function toggleSelectAllDocs() {
    if (selectedDocumentIds.length === documents.length) {
      selectedDocumentIds = [];
    } else {
      selectedDocumentIds = documents.map(d => d.id);
    }
  }

  function loadCompletedDebates() {
    if (loadingCompletedDebates) return;
    const tid = get(currentTenant)?.id;
    if (!tid) return;
    loadingCompletedDebates = true;
    (async () => {
      try {
        const { getTenantDebates } = await import('../lib/api.js');
        const res = await getTenantDebates(tid, { limit: 100, status: 'completed' });
        completedDebates = res || [];
      } catch (e) {
        if (import.meta.env.DEV) console.warn('Failed to load completed debates:', e);
        completedDebates = [];
      } finally {
        loadingCompletedDebates = false;
      }
    })();
  }

  function handleCreated(response) {
    if (response.debate_id) {
      // Workflow with debate record — navigate to rich debate view
      navigate('mvp-debate/' + response.debate_id);
    } else if (response.session_id) {
      // Workflow-exec path without debate — navigate to execution view
      setActiveWorkflowSession({
        sessionId: response.session_id,
        workflowId: response.workflow_id || '',
        workflowName: response.workflow_name || 'Workflow',
        context: response.context || '',
        startedAt: new Date().toISOString(),
        status: response.status || 'running',
      });
      navigate('execution/' + response.session_id);
    } else {
      // Legacy debate path — navigate to debate view
      currentDebate.set(response);
      debates.set([...$debates, response]);
      autoStartDebate.set(true);
      navigate('debate');
    }
  }
</script>

<div class="max-w-4xl mx-auto p-6 space-y-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
    🎤 {t('nav.input')}
  </h1>

  <!-- Mode Toggle -->
  <div class="flex gap-2 border-b border-gray-200 dark:border-gray-700 pb-2">
    <button
      class="px-4 py-2 text-sm font-medium rounded-t-lg transition-colors
        {inputMode === 'form'
          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200 border-b-2 border-blue-600'
          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'}"
      onclick={() => inputMode = 'form'}
    >
      {t('debate.newDebate')}
    </button>
    <button
      class="px-4 py-2 text-sm font-medium rounded-t-lg transition-colors
        {inputMode === 'compose'
          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200 border-b-2 border-blue-600'
          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'}"
      onclick={() => inputMode = 'compose'}
    >
      🎤 Input Composer
    </button>
  </div>

  <!-- DebateCreatePanel mode (default) -->
  {#if inputMode === 'form'}
    <DebateCreatePanel onCreated={handleCreated} />
  {/if}

  <!-- Input Composer mode (advanced — all plugins) -->
  {#if inputMode === 'compose'}
    <!-- Plugin Selector -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">Input Source</h2>
      <div class="mb-4">
        <PluginSelector {plugins} selectedKey={selectedPlugin} onchange={onPluginChange} />
      </div>

      <!-- Textarea with STT button -->
      <div class="mb-4 relative">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="topic-input">
          {t('debate.caseLabel')}
        </label>
        <textarea
          id="topic-input"
          bind:value={topic}
          placeholder={t('debate.casePlaceholder')}
          rows="8"
          maxlength="5000"
          class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm resize-y"
        ></textarea>
        {#if partialText}
          <p class="mt-1 text-xs text-gray-500 italic">🎙️ {partialText}</p>
        {/if}
        <!-- STT Microphone button (bottom-right of textarea) -->
        <div class="absolute bottom-3 right-3">
          <STTMicrophoneButton onPartial={onPartial} onFinal={onFinal} />
        </div>
      </div>

      <!-- Workflow Template Picker -->
      <div class="mb-4">
        <WorkflowTemplatePicker templates={workflowTemplates} selectedId={selectedTemplateId} onchange={onTemplateChange} />
      </div>

      <!-- DMS Document Selection -->
      {#if documents.length > 0}
        <div class="mb-4 p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-900">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-semibold text-gray-800 dark:text-white">Documents</span>
            <div class="flex items-center gap-2">
              <button
                class="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                onclick={toggleSelectAllDocs}
              >{selectedDocumentIds.length === documents.length ? 'Deselect all' : 'Select all'}</button>
              <span class="text-xs text-gray-500 dark:text-gray-400">{selectedDocumentIds.length} selected</span>
            </div>
          </div>
          <div class="max-h-32 overflow-y-auto space-y-1 mb-2">
            {#each documents as doc (doc.id)}
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedDocumentIds.includes(doc.id)}
                  onchange={() => toggleDocumentSelection(doc.id)}
                  class="rounded border-gray-300 dark:border-gray-600"
                />
                <span class="text-sm text-gray-700 dark:text-gray-300 truncate">{doc.filename}</span>
              </label>
            {/each}
          </div>
          <div class="space-y-1">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" bind:checked={ragAutoRetrieve} class="rounded border-gray-300 dark:border-gray-600" />
              <span class="text-sm text-gray-700 dark:text-gray-300">Auto-retrieve relevant chunks</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" bind:checked={includeDebateResults} class="rounded border-gray-300 dark:border-gray-600" />
              <span class="text-sm text-gray-700 dark:text-gray-300">Include previous debates</span>
            </label>
            {#if includeDebateResults}
              <div class="ml-6 mt-1 text-xs text-gray-500 dark:text-gray-400">
                {#if loadingCompletedDebates}
                  Loading debates…
                {:else if completedDebates.length === 0}
                  <button class="text-blue-600 hover:underline" onclick={loadCompletedDebates}>Load completed debates</button>
                {:else}
                  {completedDebates.length} debate(s) selected
                {/if}
              </div>
            {/if}
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" bind:checked={includeDocumentAnalysis} class="rounded border-gray-300 dark:border-gray-600" />
              <span class="text-sm text-gray-700 dark:text-gray-300">Include document analysis</span>
            </label>
          </div>
        </div>
      {/if}

      <!-- Error -->
      {#if error}
        <div class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      {/if}

      <!-- Submit Button -->
      <div class="mb-4">
        <button
          onclick={handleSubmit}
          disabled={loading || !topic.trim()}
          class="px-6 py-2.5 rounded-lg bg-green-600 text-white font-medium text-sm
            hover:bg-green-700 disabled:hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {#if loading}
            🔄 Processing…
          {:else}
            ▶️ {t('debate.startButton') || 'Start Debate'}
          {/if}
        </button>
      </div>

      <!-- Job Status -->
      {#if tracker}
        <div class="p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
            Status: <span class="font-mono">{tracker.status}</span>
          </p>
          {#if tracker.error}
            <p class="text-sm text-red-500 mt-1">{tracker.error}</p>
          {/if}
        </div>
      {/if}
    </div>

    <!-- A2A Approval Section -->
    {#if pendingA2A.length > 0}
      <div class="space-y-3">
        <h2 class="text-lg font-semibold text-gray-800 dark:text-white">
          🤖 Pending A2A Requests ({pendingA2A.length})
        </h2>
        {#each pendingA2A as a2a}
          <A2AApprovalCard
            jobId={a2a.task_id}
            agentId={a2a.agent_id}
            topic={a2a.topic}
            onApprove={() => handleApproveA2A(a2a.task_id)}
            onReject={() => handleRejectA2A(a2a.task_id)}
          />
        {/each}
      </div>
    {/if}

    <!-- A2A Info Section -->
    <div class="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
      <h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        🤖 A2A Inbound
      </h3>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        External agents can submit debate topics via the A2A protocol.
        Pending requests will appear above for approval.
      </p>
    </div>

    <!-- MCP Info Section -->
    <div class="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
      <h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        🔧 MCP Stub
      </h3>
      <p class="text-xs text-gray-500 dark:text-gray-400">
        Model Context Protocol integration is available as a stub plugin.
        Full MCP support will be enabled in a future release.
      </p>
    </div>

    <!-- Execution results (inline below form) in DebateView style -->
    {#if showExecutionPanel}
      <DebateExecutionDisplay
        sessionId={executionSessionId}
        debateTitle={currentDebateTitle}
        debateId={currentDebateId}
        context={topic}
        onclose={() => { showExecutionPanel = false; executionSessionId = null; currentDebateTitle = ''; currentDebateId = null; }}
      />
    {/if}
  {/if}
</div>
