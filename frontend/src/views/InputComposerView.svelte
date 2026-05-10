<script>
  /**
   * InputComposerView — "Neue Debatte" page.
   *
   * Integrates the Input Composer (plugin selector, STT, A2A approval,
   * workflow templates) with the DebateCreatePanel (full debate creation form).
   * After creating a debate, auto-navigates to "Laufende Debatte" and starts it.
   */
  import { i18n } from '../lib/i18n/index.js';
  import { currentDebate, debates, autoStartDebate } from '../lib/stores.js';
  import { listInputPlugins, submitInput, approveA2A, rejectA2A } from '../lib/input/inputApi.js';
  import { createInputJobTracker } from '../lib/input/inputJobStore.js';
  import PluginSelector from '../components/input/PluginSelector.svelte';
  import STTMicrophoneButton from '../components/input/STTMicrophoneButton.svelte';
  import A2AApprovalCard from '../components/input/A2AApprovalCard.svelte';
  import WorkflowTemplatePicker from '../components/input/WorkflowTemplatePicker.svelte';
  import DebateCreatePanel from '../components/debate/DebateCreatePanel.svelte';

  /** @type {function} Navigation helper from App.svelte */
  let { navigate = () => {} } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

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

  // Which mode is active: 'compose' (Input Composer) or 'form' (DebateCreatePanel)
  let inputMode = $state('form');

  // Load plugins on mount
  $effect(() => {
    listInputPlugins()
      .then((p) => { plugins = p; })
      .catch((e) => { error = e.message; });
  });

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
    try {
      const result = await submitInput(selectedPlugin, {}, topic.trim());
      activeJob = result;
      if (result.status === 'processing' || result.status === 'pending_approval') {
        tracker = createInputJobTracker(result.job_id);
      }
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleApproveA2A(taskId) {
    try {
      await approveA2A(taskId);
      pendingA2A = pendingA2A.filter(p => p.task_id !== taskId);
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

  function handleCreated(response) {
    // Set the current debate and trigger auto-start on the debate page
    $currentDebate = response;
    $debates = [...$debates, response];
    $autoStartDebate = true;
    // Navigate to the active debate page
    navigate('debate');
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
          class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm resize-y"
        ></textarea>
        {#if partialText}
          <p class="mt-1 text-xs text-gray-400 italic">🎙️ {partialText}</p>
        {/if}
        <!-- STT Microphone button (bottom-right of textarea) -->
        <div class="absolute bottom-3 right-3">
          <STTMicrophoneButton onPartial={onPartial} onFinal={onFinal} />
        </div>
      </div>

      <!-- Workflow Template Picker -->
      <div class="mb-4">
        <WorkflowTemplatePicker selectedId={selectedTemplateId} onchange={onTemplateChange} />
      </div>

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
            hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
          🤖 Pending A2A Requests
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
  {/if}
</div>
