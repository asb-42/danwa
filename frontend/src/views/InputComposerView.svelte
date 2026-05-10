<script>
  import { i18n } from '../lib/i18n/index.js';
  import { listInputPlugins, submitInput, approveA2A, rejectA2A } from '../lib/input/inputApi.js';
  import { createInputJobTracker } from '../lib/input/inputJobStore.js';
  import PluginSelector from '../components/input/PluginSelector.svelte';
  import STTMicrophoneButton from '../components/input/STTMicrophoneButton.svelte';
  import A2AApprovalCard from '../components/input/A2AApprovalCard.svelte';
  import WorkflowTemplatePicker from '../components/input/WorkflowTemplatePicker.svelte';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  // State
  let plugins = $state([]);
  let selectedPlugin = $state('standard_text');
  let topic = $state('');
  let loading = $state(false);
  let error = $state(null);
  let activeJob = $state(null);
  let tracker = $state(null);
  let partialText = $state('');

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

  async function handleSubmit() {
    if (!topic.trim()) {
      error = 'Please enter a debate topic.';
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
</script>

<div class="max-w-4xl mx-auto p-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">
    🎤 Input Composer
  </h1>

  <!-- Plugin Selector -->
  <div class="mb-6">
    <h2 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Input Source</h2>
    <PluginSelector {plugins} selectedKey={selectedPlugin} onchange={onPluginChange} />
  </div>

  <!-- Textarea with STT button -->
  <div class="mb-6 relative">
    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="topic-input">
      Debate Topic / Case Description
    </label>
    <textarea
      id="topic-input"
      bind:value={topic}
      placeholder="Enter the debate topic or case description…"
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

  <!-- Error -->
  {#if error}
    <div class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
      {error}
    </div>
  {/if}

  <!-- Submit Button -->
  <div class="mb-6">
    <button
      onclick={handleSubmit}
      disabled={loading || !topic.trim()}
      class="px-6 py-2.5 rounded-lg bg-green-600 text-white font-medium text-sm
        hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      {#if loading}
        🔄 Processing…
      {:else}
        ▶️ Start Debate
      {/if}
    </button>
  </div>

  <!-- Job Status -->
  {#if tracker}
    <div class="mb-6 p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
        Status: <span class="font-mono">{tracker.status}</span>
      </p>
      {#if tracker.error}
        <p class="text-sm text-red-500 mt-1">{tracker.error}</p>
      {/if}
    </div>
  {/if}
</div>
