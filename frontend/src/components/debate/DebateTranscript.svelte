<script>
  import { tStore } from '../../lib/i18n/index.js';
  
  import MarkdownRenderer from '../MarkdownRenderer.svelte';

  let {
    agentOutputs = [],
    agents = [],
    currentRound = 0,
    currentActivity = null,
    expandedOutputs = $bindable(new Set()),
    llmProfiles = [],
  } = $props();

  let t = $derived($tStore);

  let liveOutputsByRound = $derived(agentOutputs.reduce((acc, output) => {
    if (!acc[output.round]) acc[output.round] = [];
    acc[output.round].push(output);
    return acc;
  }, {}));

  function roleEmoji(role) {
    const agent = agents.find(a => a.role === role);
    return agent ? agent.icon : '🤖';
  }

  function roleColor(role) {
    switch (role) {
      case 'strategist': return 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-600';
      case 'critic': return 'border-red-400 bg-red-50 dark:bg-red-900/20 dark:border-red-600';
      case 'optimizer': return 'border-amber-400 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-600';
      case 'moderator': return 'border-purple-400 bg-purple-50 dark:bg-purple-900/20 dark:border-purple-600';
      default: return 'border-gray-400 bg-gray-50 dark:bg-gray-800 dark:border-gray-600';
    }
  }

  function roleHeaderColor(role) {
    switch (role) {
      case 'strategist': return 'text-blue-700 dark:text-blue-300';
      case 'critic': return 'text-red-700 dark:text-red-300';
      case 'optimizer': return 'text-amber-700 dark:text-amber-300';
      case 'moderator': return 'text-purple-700 dark:text-purple-300';
      default: return 'text-gray-700 dark:text-gray-300';
    }
  }

  function formatElapsed(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function getProfileName(profileId) {
    const profile = llmProfiles.find(p => p.id === profileId);
    return profile ? profile.name : profileId;
  }
</script>

<div class="outputs-section">
  <h4 class="outputs-title">Agent Outputs ({agentOutputs.length})</h4>
  <div class="outputs-list">
    {#each Object.entries(liveOutputsByRound) as [round, outputs]}
      <div class="round-group">
        <div class="round-label">Round {round}</div>
        <div class="round-outputs">
          {#each outputs as output, i}
            {@const key = `out-r${output.round}-${output.role}-${i}`}
            {@const isExpanded = expandedOutputs.has(key)}
            {@const isLong = output.content?.length > 400}
            <div class="output-card border-l-4 {roleColor(output.role)} p-4">
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-sm {roleHeaderColor(output.role)}">
                    {roleEmoji(output.role)} {output.role}
                  </span>
                  {#if output.model}
                    <span class="output-model">{output.model}</span>
                  {:else if output.profile}
                    <span class="output-model">{getProfileName(output.profile)}</span>
                  {/if}
                </div>
                <div class="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
                  {#if output.durationMs}
                    <span class="font-mono">⏱ {formatElapsed(output.durationMs)}</span>
                  {/if}
                  <span>{output.tokensUsed || 0} tokens</span>
                </div>
              </div>
              <div class="text-sm text-gray-700 dark:text-gray-300">
                {#if isLong && !isExpanded}
                  <MarkdownRenderer content={output.content.substring(0, 400) + '…'} />
                  <button class="expand-btn" onclick={() => expandedOutputs = new Set([...expandedOutputs, key])}>
                    ▼ Show full response ({output.content.length} chars)
                  </button>
                {:else}
                  <MarkdownRenderer content={output.content} />
                  {#if isLong}
                    <button class="expand-btn" onclick={() => { const next = new Set(expandedOutputs); next.delete(key); expandedOutputs = next; }}>
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

    <!-- Thinking indicator (bouncing dots) -->
    {#if currentActivity}
      <div class="thinking-card border-l-4 border-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
        <div class="flex items-center gap-2">
          <span class="animate-pulse w-3 h-3 bg-blue-500 rounded-full"></span>
          <span class="font-semibold text-sm text-blue-700 dark:text-blue-300">
            {roleEmoji(currentActivity.role)} {currentActivity.role}
          </span>
          <span class="text-xs text-blue-500 dark:text-blue-400">— Round {currentActivity.round} — thinking</span>
        </div>
        <div class="mt-2 flex gap-1">
          <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </div>
      </div>
    {/if}

    {#if agentOutputs.length === 0 && !currentActivity}
      <p class="text-gray-500 dark:text-gray-400 text-sm text-center py-8">Waiting for agent outputs...</p>
    {/if}
  </div>
</div>

<style>
  .outputs-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .outputs-title {
    font-size: 13px;
    font-weight: 600;
    color: #6b7280;
    margin: 0;
  }
  .outputs-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 70vh;
    overflow-y: auto;
  }

  .round-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .round-label {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #6b7280;
    background: #f3f4f6;
    padding: 4px 10px;
    border-radius: 4px;
    align-self: flex-start;
  }
  :global(.dark) .round-label {
    background: #374151;
    color: #9ca3af;
  }
  .round-outputs {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .output-card {
    border-radius: 8px;
    background: white;
  }
  :global(.dark) .output-card {
    background: #1f2937;
  }
  .output-model {
    font-size: 11px;
    font-family: monospace;
    color: #9ca3af;
  }

  .thinking-card {
    border-radius: 8px;
  }

  .expand-btn {
    display: block;
    margin-top: 6px;
    background: none;
    border: none;
    color: #3b82f6;
    font-size: 12px;
    cursor: pointer;
    padding: 2px 0;
    text-decoration: underline dotted;
  }
  :global(.dark) .expand-btn { color: #60a5fa; }
  .expand-btn:hover { color: #1d4ed8; }
  :global(.dark) .expand-btn:hover { color: #93c5fd; }
</style>
