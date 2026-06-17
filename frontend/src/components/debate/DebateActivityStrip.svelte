<script>
  /**
   * DebateActivityStrip — Compact progress feedback during a running debate.
   *
   * Shows progress dots, agent status, model name, timer, and token counter.
   */
  import { tStore } from '../../lib/i18n/index.js';

  /** @type {{ currentDebate: object, currentActivity: object|null, workflowPhase: object|null, liveOutputs: array, isProcessing: boolean, isBetweenAgents: boolean, processingElapsed: number, workflowElapsed: number, cumulativeTokens: number, agentCount: number, activeAgentIndex: number, completedInRound: number }} */
  let {
    currentDebate = {},
    currentActivity = null,
    workflowPhase = null,
    liveOutputs = [],
    isProcessing = false,
    isBetweenAgents = false,
    processingElapsed = 0,
    workflowElapsed = 0,
    cumulativeTokens = 0,
    agentCount = 0,
    activeAgentIndex = -1,
    completedInRound = 0,
  } = $props();

  let t = $derived($tStore);

  function roleDotColor(role) {
    switch (role) {
      case 'strategist': return 'bg-blue-500';
      case 'critic': return 'bg-red-500';
      case 'optimizer': return 'bg-amber-500';
      case 'moderator': return 'bg-violet-500';
      default: return 'bg-zinc-500';
    }
  }

  function roleTextColor(role) {
    switch (role) {
      case 'strategist': return 'text-blue-400';
      case 'critic': return 'text-red-400';
      case 'optimizer': return 'text-amber-400';
      case 'moderator': return 'text-violet-400';
      default: return 'text-zinc-400';
    }
  }

  function roleVerbKey(role) {
    switch (role) {
      case 'strategist': return 'feedback.analysing';
      case 'critic': return 'feedback.checking';
      case 'optimizer': return 'feedback.optimizing';
      case 'moderator': return 'feedback.evaluating';
      default: return 'feedback.analysing';
    }
  }

  function formatElapsed(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function formatTokens(n) {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
  }
</script>

{#if currentDebate?.status === 'running'}
  <div class="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
    <!-- DEBUG 2026-06-17: visual marker to identify this component on screen -->
    <div data-debug-component="DebateActivityStrip" class="px-2 py-0.5 mb-2 inline-block rounded bg-pink-600 text-white text-[10px] font-mono font-bold tracking-wider">DBG: DebateActivityStrip.svelte</div>
    <!-- Row 1: Progress dots + role verb -->
    <div class="flex items-center gap-3 mb-2">
      <!-- Progress dots -->
      <div class="flex items-center gap-1.5">
        {#if workflowPhase && !currentActivity && liveOutputs.length === 0}
          <span class="relative flex h-2.5 w-2.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
          </span>
        {:else}
          {#each Array(agentCount) as _, i}
            {#if i < completedInRound}
              <span class="w-2.5 h-2.5 rounded-full {roleDotColor(liveOutputs.filter(o => o.round === (currentDebate?.current_round || 0))[i]?.role || 'default')}"></span>
            {:else if i === activeAgentIndex && isProcessing}
              <span class="relative flex h-2.5 w-2.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full {roleDotColor(currentActivity?.role || 'default')} opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 {roleDotColor(currentActivity?.role || 'default')}"></span>
              </span>
            {:else}
              <span class="w-2.5 h-2.5 rounded-full bg-zinc-700"></span>
            {/if}
          {/each}
        {/if}
      </div>

      <!-- Status text -->
      {#if isProcessing && currentActivity}
        <span class="text-sm font-medium {roleTextColor(currentActivity.role)}">
          {t(roleVerbKey(currentActivity.role), { role: t(`agent.${currentActivity.role}`) })}
        </span>
      {:else if workflowPhase}
        {#if workflowPhase.type === 'workflow_started'}
          <span class="text-sm font-medium text-cyan-400">
            {t('feedback.workflowStarted')}
          </span>
        {:else if workflowPhase.type === 'agent_preparing' && workflowPhase.phase === 'resolving_profile'}
          <span class="text-sm font-medium text-cyan-400">
            {t('feedback.resolvingProfile', { role: t(`agent.${workflowPhase.role}`) })}
          </span>
        {:else if workflowPhase.type === 'agent_preparing' && workflowPhase.phase === 'resolving_prompts'}
          <span class="text-sm font-medium text-cyan-400">
            {t('feedback.resolvingPrompts', { role: t(`agent.${workflowPhase.role}`) })}
          </span>
        {:else if workflowPhase.type === 'llm_call_started'}
          <span class="text-sm font-medium text-amber-400">
            {t('feedback.llmCalling', { model: workflowPhase.model || '...' })}
          </span>
        {:else}
          <span class="text-sm font-medium text-zinc-500">
            {t('feedback.waiting')}
          </span>
        {/if}
      {:else if isBetweenAgents}
        <span class="text-sm font-medium text-zinc-400">
          {t('feedback.completed', { role: t(`agent.${liveOutputs[liveOutputs.length - 1]?.role || 'strategist'}`) })}
        </span>
      {:else}
        <span class="text-sm font-medium text-zinc-500">
          {t('feedback.waiting')}
        </span>
      {/if}
    </div>

    <!-- Row 2: Model name + timer + token counter -->
    {#if isProcessing || isBetweenAgents || workflowPhase}
      <div class="flex items-center gap-3">
        <!-- Model name -->
        {#if workflowPhase?.model}
          <span class="text-xs text-zinc-500 font-mono truncate max-w-[200px]">
            {workflowPhase.model}
          </span>
        {:else if currentActivity?.model || liveOutputs[liveOutputs.length - 1]?.model}
          <span class="text-xs text-zinc-500 font-mono truncate max-w-[200px]">
            {currentActivity?.model || liveOutputs[liveOutputs.length - 1]?.model}
          </span>
        {/if}

        <!-- Provider badge -->
        {#if workflowPhase?.provider}
          <span class="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-zinc-500 font-mono uppercase">
            {workflowPhase.provider}
          </span>
        {:else if currentActivity?.provider}
          <span class="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-zinc-500 font-mono uppercase">
            {currentActivity.provider}
          </span>
        {/if}

        <div class="flex-1"></div>

        <!-- Timer pill -->
        {#if isProcessing}
          <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
            ⏱ {formatElapsed(processingElapsed)}
          </span>
        {:else if workflowPhase && workflowElapsed > 0}
          <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
            ⏱ {formatElapsed(workflowElapsed)}
          </span>
        {:else if liveOutputs.length > 0}
          {@const lastOutput = liveOutputs[liveOutputs.length - 1]}
          {#if lastOutput.duration_ms}
            <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
              ⏱ {formatElapsed(lastOutput.duration_ms)}
            </span>
          {/if}
        {/if}

        <!-- Stuck warning — if workflow phase takes > 30s -->
        {#if workflowPhase && workflowElapsed > 30000}
          <span class="px-2 py-0.5 rounded-full bg-amber-900/50 text-xs text-amber-400 font-mono">
            ⚠ {t('feedback.slowResponse')}
          </span>
        {/if}

        <!-- Token counter pill -->
        {#if cumulativeTokens > 0}
          <span class="px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono">
            📊 {formatTokens(cumulativeTokens)} {t('feedback.tokens')}
          </span>
        {/if}
      </div>
    {/if}
  </div>
{/if}
