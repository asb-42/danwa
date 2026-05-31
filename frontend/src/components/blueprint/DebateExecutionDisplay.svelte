<script>
  import { i18n } from '../../lib/i18n/index.js';
  import { pauseWorkflow, resumeWorkflow, cancelWorkflow } from '../../lib/workflowExec.js';
  import { createWorkflowSSE } from '../../lib/workflowSSE.js';
  import { normalizeTranscriptContent } from '../../lib/transcriptNormalizer.js';
  import MarkdownRenderer from '../MarkdownRenderer.svelte';

  let {
    sessionId = null,
    debateTitle = '',
    debateId = null,
    context = '',
    onclose = () => {},
  } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let status = $state('running');
  let nodeOutputs = $state([]);
  let currentRound = $state(0);
  let consensus = $state(0);
  let startTime = $state(null);
  let elapsedMs = $state(0);
  let elapsedTimer = $state(null);
  let error = $state('');
  let expandedOutputs = $state(new Set());
  let isPausing = $state(false);
  let isCancelling = $state(false);
  let cleanupSSE = $state(null);

  let totalDuration = $derived(computeDuration());

  function computeDuration() {
    if (nodeOutputs.length === 0) return '';
    const totalMs = nodeOutputs.reduce((sum, o) => sum + (o.durationMs || 0), 0);
    return formatElapsed(totalMs);
  }

  function connectSSE(sid) {
    startTime = Date.now();
    elapsedTimer = setInterval(() => {
      elapsedMs = Date.now() - startTime;
    }, 200);

    cleanupSSE = createWorkflowSSE(sid, {
      onNodeComplete: (data) => {
        const role = data.role || data.node_type || '';
        const rawContent = data.content || '';
        const normalizedContent = normalizeTranscriptContent(rawContent, role);
        nodeOutputs = [...nodeOutputs, {
          role,
          content: normalizedContent,
          durationMs: data.duration_ms || 0,
          round: data.round || currentRound,
          model: data.model || '',
          tokens: data.tokens || data.tokens_used || 0,
        }];
        if (data.consensus !== undefined) consensus = data.consensus;
        if (data.round !== undefined) currentRound = data.round;
      },
      onWorkflowComplete: (data) => {
        status = 'completed';
        if (data.final_consensus !== undefined) consensus = data.final_consensus;
        if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
      },
      onNodeError: (data) => {
        error = data.error || 'Unknown node error';
        status = 'failed';
        if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
      },
      onWorkflowPaused: () => { status = 'paused'; },
      onWorkflowResumed: () => { status = 'running'; },
      onError: (err) => { console.error('SSE error:', err); },
    });
  }

  $effect(() => {
    if (sessionId) connectSSE(sessionId);
    return () => {
      if (cleanupSSE) cleanupSSE();
      if (elapsedTimer) clearInterval(elapsedTimer);
    };
  });

  async function handlePauseResume() {
    if (!sessionId) return;
    isPausing = true;
    try {
      if (status === 'running') {
        await pauseWorkflow(sessionId);
        status = 'paused';
      } else if (status === 'paused') {
        await resumeWorkflow(sessionId);
        status = 'running';
      }
    } catch (err) {
      error = err.message || 'Failed to toggle pause';
    } finally {
      isPausing = false;
    }
  }

  async function handleCancel() {
    if (!sessionId) return;
    isCancelling = true;
    try {
      await cancelWorkflow(sessionId);
      status = 'cancelled';
      if (cleanupSSE) cleanupSSE();
      if (elapsedTimer) clearInterval(elapsedTimer);
    } catch (err) {
      error = err.message || 'Failed to cancel';
    } finally {
      isCancelling = false;
    }
  }

  function toggleExpand(key) {
    const next = new Set(expandedOutputs);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    expandedOutputs = next;
  }

  function roleEmoji(role) {
    switch (role) {
      case 'strategist': return '🎯';
      case 'critic': return '🔍';
      case 'builder': return '🛠️';
      case 'optimizer': return '⚡';
      case 'pragmatist': return '📊';
      case 'moderator': return '⚖️';
      default: return '🤖';
    }
  }

  function roleColor(role) {
    switch (role) {
      case 'strategist': return 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-600';
      case 'critic': return 'border-red-400 bg-red-50 dark:bg-red-900/20 dark:border-red-600';
      case 'builder': return 'border-teal-400 bg-teal-50 dark:bg-teal-900/20 dark:border-teal-600';
      case 'optimizer': return 'border-amber-400 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-600';
      case 'pragmatist': return 'border-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 dark:border-indigo-600';
      case 'moderator': return 'border-purple-400 bg-purple-50 dark:bg-purple-900/20 dark:border-purple-600';
      default: return 'border-gray-400 bg-gray-50 dark:bg-gray-800 dark:border-gray-600';
    }
  }

  function roleHeaderColor(role) {
    switch (role) {
      case 'strategist': return 'text-blue-700 dark:text-blue-300';
      case 'critic': return 'text-red-700 dark:text-red-300';
      case 'builder': return 'text-teal-700 dark:text-teal-300';
      case 'optimizer': return 'text-amber-700 dark:text-amber-300';
      case 'pragmatist': return 'text-indigo-700 dark:text-indigo-300';
      case 'moderator': return 'text-purple-700 dark:text-purple-300';
      default: return 'text-gray-700 dark:text-gray-300';
    }
  }

  function formatElapsed(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }

  let statusBadgeClass = $derived({
    'running': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    'paused': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    'completed': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    'failed': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    'cancelled': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
  }[status] || 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200');

  let isCompleted = $derived(status === 'completed' || status === 'failed' || status === 'cancelled');

  let outputsByRound = $derived(nodeOutputs.reduce((acc, output) => {
    const round = output.round || 0;
    if (!acc[round]) acc[round] = [];
    acc[round].push(output);
    return acc;
  }, {}));

  function handleClose() {
    if (cleanupSSE) cleanupSSE();
    if (elapsedTimer) clearInterval(elapsedTimer);
    onclose();
  }
</script>

<div class="debate-execution-display space-y-6">
  <!-- Title Banner -->
  {#if debateTitle}
    <div class="px-4 py-3 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/20
                border border-blue-200 dark:border-blue-700 shadow-sm">
      <h3 class="text-xl font-bold text-gray-900 dark:text-white leading-snug tracking-tight">
        {debateTitle}
      </h3>
    </div>
  {/if}

  <!-- Status Card -->
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
        {t('debate.currentDebate') || 'Ausführung'}
      </h3>
      <div class="flex items-center space-x-3">
        <span class="px-2 py-1 text-xs font-medium rounded-full {statusBadgeClass}">
          {status}
        </span>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-lg leading-none" onclick={handleClose}>
          ✕
        </button>
      </div>
    </div>

    <!-- Meta info row -->
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm mb-3">
      {#if debateId}
        <div>
          <span class="text-gray-500 dark:text-gray-400">{t('debate.id') || 'ID'}: </span>
          <code class="font-mono text-gray-800 dark:text-gray-200 text-xs">{debateId}</code>
        </div>
      {/if}
      <div>
        <span class="text-gray-500 dark:text-gray-400">{t('debate.round') || 'Runde'}: </span>
        <span class="text-gray-800 dark:text-gray-200 font-medium">{currentRound}</span>
      </div>
      <div>
        <span class="text-gray-500 dark:text-gray-400">{t('workflow.execution.elapsed') || 'Dauer'}: </span>
        <span class="text-gray-800 dark:text-gray-200 font-mono text-xs">
          {status === 'running' || status === 'paused' ? formatDuration(elapsedMs) : totalDuration || formatDuration(elapsedMs)}
        </span>
      </div>
    </div>

    <!-- Consensus bar -->
    {#if consensus > 0}
      <div class="flex items-center gap-2 mb-3">
        <span class="text-sm text-gray-500 dark:text-gray-400">{t('debate.consensus') || 'Konsens'}:</span>
        <div class="w-32 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <div
            class="h-2 rounded-full transition-all duration-500 {consensus < 0.5 ? 'bg-red-500' : consensus < 0.8 ? 'bg-yellow-500' : 'bg-green-500'}"
            style="width: {Math.max(2, consensus * 100)}%"
          ></div>
        </div>
        <span class="text-gray-800 dark:text-gray-200 font-medium text-sm">
          {(consensus * 100).toFixed(1)}%
        </span>
      </div>
    {/if}

    <!-- Controls -->
    <div class="flex space-x-3 mt-4">
      {#if status === 'running' || status === 'paused'}
        <button
          class="px-4 py-2 text-sm rounded-lg {status === 'running'
            ? 'bg-yellow-500 hover:bg-yellow-600 text-white'
            : 'bg-green-600 hover:bg-green-700 text-white'} disabled:opacity-50 transition-colors"
          onclick={handlePauseResume}
          disabled={isPausing}
        >
          {isPausing ? '...' : status === 'running' ? '⏸ ' + (t('workflow.execution.pause') || 'Pause') : '▶ ' + (t('workflow.execution.resume') || 'Weiter')}
        </button>
        <button
          class="px-4 py-2 text-sm rounded-lg bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 transition-colors"
          onclick={handleCancel}
          disabled={isCancelling}
        >
          {isCancelling ? '...' : '⏹ ' + (t('workflow.execution.cancel') || 'Abbrechen')}
        </button>
      {/if}
    </div>

    <!-- Error -->
    {#if error}
      <div class="mt-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
        {error}
      </div>
    {/if}
  </div>

  <!-- Loading indicator while running with no outputs yet -->
  {#if status === 'running' && nodeOutputs.length === 0}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 border border-gray-200 dark:border-gray-700 text-center">
      <div class="flex justify-center gap-1 mb-3">
        <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
        <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
        <span class="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
      </div>
      <p class="text-gray-500 dark:text-gray-400">Agenten bereiten sich vor...</p>
    </div>
  {/if}

  <!-- Agent Outputs -->
  {#if nodeOutputs.length > 0}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
      <div class="p-4 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white">
          {t('debate.timelineTitle') || 'Beiträge'}
        </h3>
      </div>
      <div class="p-4 space-y-6 max-h-[70vh] overflow-y-auto">
        {#each Object.entries(outputsByRound) as [round, outputs]}
          <div>
            <div class="flex items-center gap-2 mb-3">
              <span class="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                {t('timeline.round', { num: round }) || `Runde ${round}`}
              </span>
            </div>
            <div class="space-y-3">
              {#each outputs as output, i}
                {@const key = `r${output.round}-${output.role}-${i}`}
                {@const isExpanded = expandedOutputs.has(key)}
                {@const isLong = output.content?.length > 400}
                <div class="border-l-4 rounded-lg {roleColor(output.role)} p-4">
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <span class="font-semibold text-sm {roleHeaderColor(output.role)}">
                        {roleEmoji(output.role)} {output.role}
                      </span>
                      {#if output.model}
                        <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">{output.model}</span>
                      {/if}
                    </div>
                    <div class="flex items-center gap-2">
                      {#if output.durationMs}
                        <span class="text-xs text-gray-400 dark:text-gray-500 font-mono">⏱ {formatElapsed(output.durationMs)}</span>
                      {/if}
                      <span class="text-xs text-gray-400 dark:text-gray-500">{output.tokens || 0} tokens</span>
                    </div>
                  </div>
                  <div class="text-sm text-gray-700 dark:text-gray-300">
                    {#if isLong && !isExpanded}
                      <MarkdownRenderer content={output.content.substring(0, 400) + '…'} />
                      <button class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block" onclick={() => toggleExpand(key)}>
                        ▼ Show full response ({output.content.length} chars)
                      </button>
                    {:else}
                      <MarkdownRenderer content={output.content} />
                      {#if isLong}
                        <button class="text-blue-600 dark:text-blue-400 hover:underline text-xs mt-1 inline-block" onclick={() => toggleExpand(key)}>
                          ▲ Collapse
                        </button>
                      {/if}
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Title -->
  {#if debateTitle}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 mb-4">
      <div class="text-xl font-bold text-gray-900 dark:text-white">&lt;Title&gt;{debateTitle}&lt;/Title&gt;</div>
    </div>
  {/if}

  <!-- Metadata -->
  {#if nodeOutputs.length}
    {@const rounds = Math.max(...nodeOutputs.map(n => n.round || 0), 0)}
    {@const roles = [...new Set(nodeOutputs.map(n => n.role).filter(Boolean))]}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700 mb-4">
      <div class="grid grid-cols-1 gap-2 text-sm text-gray-700 dark:text-gray-300">
        {#if rounds}
          <div><span class="font-semibold">Anzahl Runden:</span> {rounds}</div>
        {/if}
        {#if roles.length}
          <div><span class="font-semibold">Agenten-Rollen:</span> {roles.join(' · ')}</div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Case text -->
  {#if context}
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-3">{t('debate.caseLabel') || 'Fall'}</h3>
      <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{context}</p>
    </div>
  {/if}

  <!-- Final consensus -->
  {#if isCompleted && consensus > 0}
    <div class="border rounded-lg p-6 bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 border-green-200 dark:border-green-800">
      <h4 class="text-lg font-bold text-gray-800 dark:text-white mb-3 flex items-center gap-2">
        🏁 {t('timeline.finalConsensus') || 'Abschließender Konsens'}
      </h4>
      <div class="flex items-center gap-4 mb-3">
        <div class="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-4">
          <div
            class="h-4 rounded-full transition-all duration-1000 bg-gradient-to-r from-blue-500 to-green-500"
            style="width: {Math.max(2, consensus * 100)}%"
          ></div>
        </div>
        <span class="text-2xl font-bold text-gray-800 dark:text-white">
          {(consensus * 100).toFixed(1)}%
        </span>
      </div>
      <p class="text-sm text-gray-600 dark:text-gray-400">
        {t('timeline.concludedAfter', { rounds: Object.keys(outputsByRound).length, plural: Object.keys(outputsByRound).length !== 1 ? 's' : '', percent: (consensus * 100).toFixed(1) }) || `Debatte nach ${Object.keys(outputsByRound).length} Runden mit ${(consensus * 100).toFixed(1)}% Konsens abgeschlossen.`}
        {#if consensus >= 0.9}
          <span class="text-green-600 dark:text-green-400 font-medium"> — Starkes Einvernehmen</span>
        {:else if consensus >= 0.7}
          <span class="text-yellow-600 dark:text-yellow-400 font-medium"> — Mäßiges Einvernehmen</span>
        {:else}
          <span class="text-red-600 dark:text-red-400 font-medium"> — Geringes Einvernehmen</span>
        {/if}
      </p>
    </div>
  {/if}
</div>