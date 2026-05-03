<script>
  import AgentCard from './AgentCard.svelte';
  import { i18n } from '../lib/i18n/index.js';

  /** @type {Array<{ round: number, consensus: number, agent_outputs: Array<{ role: string, content: string, tokens_used?: number }> }>} */
  export let rounds = [];
  /** @type {Array<{ round: number, role: string, content: string, tokens?: number, timestamp?: Date }>} Live outputs during running debate */
  export let liveOutputs = [];
  /** @type {{ round: number, role: string, profile?: string }|null} Currently thinking agent */
  export let currentActivity = null;
  /** @type {number} Max rounds configured for this debate */
  export let maxRounds = 0;
  /** @type {number} Current consensus score (0-1) */
  export let consensus = 0;
  /** @type {string} Debate status */
  export let status = 'pending';
  /** @type {Array<string>} Anomalies from the debate */
  export let anomalies = [];

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  // Group live outputs by round
  $: liveByRound = liveOutputs.reduce((acc, output) => {
    if (!acc[output.round]) acc[output.round] = [];
    acc[output.round].push(output);
    return acc;
  }, {});

  // Determine which data to display: live during running, stored rounds after completion
  $: isRunning = status === 'running';
  $: displayData = isRunning ? liveByRound : buildDisplayData(rounds);

  function buildDisplayData(rounds) {
    if (!rounds || rounds.length === 0) return {};
    const result = {};
    for (const round of rounds) {
      result[round.round] = round.agent_outputs || [];
    }
    return result;
  }

  // Consensus color
  $: consensusColor = consensus >= 0.9 ? 'text-emerald-400' : consensus >= 0.7 ? 'text-yellow-400' : 'text-red-400';
  $: consensusBarColor = consensus >= 0.9 ? 'bg-emerald-500' : consensus >= 0.7 ? 'bg-yellow-500' : 'bg-red-500';

  // Round numbers sorted
  $: roundNumbers = Object.keys(displayData).map(Number).sort((a, b) => a - b);
  $: latestRound = roundNumbers.length > 0 ? Math.max(...roundNumbers) : 0;

  // Final verdict
  $: hasAnomalies = anomalies && anomalies.length > 0;
  $: isCompleted = status === 'completed';
  $: roundPlural = roundNumbers.length !== 1 ? 's' : '';
</script>

<div class="max-w-4xl mx-auto space-y-8">

  <!-- Header -->
  <div class="flex items-center justify-between border-b border-zinc-700 pb-5">
    <div>
      <h2 class="text-xl font-semibold text-white">{t('timeline.title')}</h2>
      <p class="text-zinc-400 text-sm mt-1">
        {#if isRunning}
          {t('timeline.roundOf', { current: latestRound, max: maxRounds })} · <span class="text-blue-400">{t('timeline.live')}</span>
        {:else if isCompleted}
          {t('timeline.roundsCompleted', { count: roundNumbers.length })} · {t('status.completed')}
        {:else if status === 'failed'}
          {t('timeline.failedAfterRound', { round: latestRound })}
        {:else}
          {t('timeline.waiting')}
        {/if}
      </p>
    </div>

    <!-- Consensus meter -->
    <div class="text-right">
      <div class="text-xs text-zinc-400 mb-1">{t('timeline.consensus')}</div>
      <div class="text-3xl font-mono font-bold {consensusColor}">
        {(consensus * 100).toFixed(1)}%
      </div>
      <div class="w-28 bg-zinc-800 rounded-full h-1.5 mt-2">
        <div
          class="h-1.5 rounded-full transition-all duration-700 {consensusBarColor}"
          style="width: {Math.max(2, consensus * 100)}%"
        ></div>
      </div>
    </div>
  </div>

  <!-- Timeline -->
  {#if roundNumbers.length === 0 && !currentActivity}
    <div class="flex items-center justify-center h-32 border-2 border-dashed border-zinc-700 rounded-xl">
      <p class="text-zinc-500 text-sm">{t('timeline.noOutputs')}</p>
    </div>
  {:else}
    <div class="relative pl-8 border-l-2 border-zinc-700 space-y-10">
      {#each roundNumbers as roundNum}
        <div>
          <!-- Round separator -->
          <div class="flex items-center gap-3 -ml-[2.1rem] mb-5">
            <div class="w-6 h-6 rounded-full bg-zinc-800 border-2 border-zinc-600 flex items-center justify-center text-xs font-mono text-zinc-300">
              {roundNum}
            </div>
            <div class="flex items-center gap-3">
              <span class="uppercase text-xs tracking-widest text-zinc-500 font-medium">{t('timeline.round', { num: roundNum })}</span>
              {#if rounds[roundNum - 1]?.consensus !== undefined}
                <span class="text-xs text-zinc-500">
                  · {t('timeline.roundConsensus', { percent: (rounds[roundNum - 1].consensus * 100).toFixed(1) })}
                </span>
              {/if}
            </div>
          </div>

          <!-- Agent cards for this round -->
          <div class="space-y-4">
            {#each displayData[roundNum] as entry, i}
              <AgentCard
                {entry}
                thinking={false}
              />
            {/each}
          </div>
        </div>
      {/each}

      <!-- Currently thinking agent (live) -->
      {#if currentActivity}
        <div class="relative">
          <div class="flex items-center gap-3 -ml-[2.1rem] mb-4">
            <div class="absolute -left-[0.45rem] w-5 h-5 rounded-full bg-amber-500/20 flex items-center justify-center">
              <div class="w-2.5 h-2.5 bg-amber-500 rounded-full animate-ping"></div>
            </div>
            <span class="text-xs text-amber-400 font-medium ml-4">
              {t('timeline.round', { num: currentActivity.round })} · {currentActivity.role}
            </span>
          </div>
          <AgentCard
            entry={{ role: currentActivity.role, content: '', model: currentActivity.profile }}
            thinking={true}
          />
        </div>
      {/if}
    </div>
  {/if}

  <!-- Final verdict (completed debates) -->
  {#if isCompleted && roundNumbers.length > 0}
    <div class="border-t-2 border-zinc-700 pt-6">
      <div class="border rounded-2xl p-6 {hasAnomalies
        ? 'bg-gradient-to-r from-amber-900/20 to-red-900/20 border-amber-700/50'
        : 'bg-gradient-to-r from-emerald-900/20 to-blue-900/20 border-emerald-700/50'}">
        <h4 class="text-lg font-bold text-white mb-3 flex items-center gap-2">
          {hasAnomalies ? '⚠️' : '🏁'} {t('timeline.finalConsensus')}
          {#if hasAnomalies}
            <span class="text-sm font-normal text-amber-400">{t('timeline.degraded')}</span>
          {/if}
        </h4>
        <div class="flex items-center gap-4 mb-3">
          <div class="flex-1 bg-zinc-800 rounded-full h-4">
            <div
              class="h-4 rounded-full transition-all duration-1000 {hasAnomalies
                ? 'bg-gradient-to-r from-amber-500 to-red-500'
                : 'bg-gradient-to-r from-blue-500 to-emerald-500'}"
              style="width: {Math.max(2, consensus * 100)}%"
            ></div>
          </div>
          <span class="text-2xl font-bold text-white">
            {(consensus * 100).toFixed(1)}%
          </span>
        </div>
        <p class="text-sm text-zinc-400">
          {#if hasAnomalies}
            {t('debate.degradedConsensus')}
          {:else}
            {t('timeline.concludedAfter', { rounds: roundNumbers.length, plural: roundPlural, percent: (consensus * 100).toFixed(1) })}
            {#if consensus >= 0.9}
              <span class="text-emerald-400 font-medium">{t('timeline.strongConsensus')}</span>
            {:else if consensus >= 0.7}
              <span class="text-yellow-400 font-medium">{t('timeline.moderateConsensus')}</span>
            {:else}
              <span class="text-red-400 font-medium">{t('timeline.lowConsensus')}</span>
            {/if}
          {/if}
        </p>
      </div>
    </div>
  {/if}
</div>
