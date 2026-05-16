<script>
  import { i18n } from '../lib/i18n/index.js';

  let { events = [] } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  const AGENT_COLORS = {
    strategist: { bg: '#8b5cf6', light: 'rgba(139,92,246,0.15)', border: '#8b5cf6' },
    critic: { bg: '#ef4444', light: 'rgba(239,68,68,0.15)', border: '#ef4444' },
    optimizer: { bg: '#f59e0b', light: 'rgba(245,158,11,0.15)', border: '#f59e0b' },
    moderator: { bg: '#6366f1', light: 'rgba(99,102,241,0.15)', border: '#6366f1' },
    'fact-checker': { bg: '#10b981', light: 'rgba(16,185,129,0.15)', border: '#10b981' },
    analyst: { bg: '#06b6d4', light: 'rgba(6,182,212,0.15)', border: '#06b6d4' },
    creative: { bg: '#ec4899', light: 'rgba(236,72,153,0.15)', border: '#ec4899' },
  };

  const ACTION_ICONS = {
    'generate': '✏️',
    'critique': '🔍',
    'synthesize': '⚡',
    'evaluate': '🎯',
    'fact_check': '✅',
    'analyze': '📊',
    'create': '💡',
  };

  let rounds = $derived(() => {
    const map = new Map();
    for (const ev of events) {
      const r = ev.round ?? 0;
      if (!map.has(r)) map.set(r, []);
      map.get(r).push(ev);
    }
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  });

  let totalTokens = $derived(events.reduce((sum, e) => sum + (e.tokens_used || 0), 0));
  let uniqueAgents = $derived(new Set(events.map(e => e.agent).filter(Boolean)).size);
  let uniqueModels = $derived(new Set(events.map(e => e.llm_model).filter(Boolean)).size);

  function getAgentColor(agent) {
    return AGENT_COLORS[agent] || { bg: '#6b7280', light: 'rgba(107,114,128,0.15)', border: '#6b7280' };
  }

  function getActionIcon(action) {
    return ACTION_ICONS[action] || '📝';
  }

  function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  let expandedEvent = $state(null);
</script>

{#if events.length === 0}
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 border border-gray-200 dark:border-gray-700">
    <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-4">{t('audit.visualizationTitle')}</h3>
    <div class="flex items-center justify-center h-32 text-gray-400 dark:text-gray-500 text-sm">
      {t('audit.noEventsForVisualization')}
    </div>
  </div>
{:else}
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
    <div class="p-6 pb-3">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white">{t('audit.visualizationTitle')}</h3>

      <!-- Summary stats -->
      <div class="mt-3 flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400">
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-blue-500"></span>
          {events.length} {t('audit.events') || 'Events'}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-purple-500"></span>
          {rounds().length} {t('audit.rounds') || 'Rounds'}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-green-500"></span>
          {uniqueAgents} {t('audit.agents') || 'Agents'}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-amber-500"></span>
          {totalTokens.toLocaleString()} {t('audit.tokens') || 'Tokens'}
        </span>
      </div>
    </div>

    <div class="px-6 pb-6">
      <!-- Timeline by round -->
      <div class="space-y-4">
        {#each rounds() as [roundNum, roundEvents]}
          <div class="relative">
            <!-- Round header -->
            <div class="flex items-center gap-3 mb-2">
              <span class="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-700 text-sm font-bold text-gray-700 dark:text-gray-200">
                {roundNum}
              </span>
              <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
              <span class="text-xs text-gray-400 dark:text-gray-500">{roundEvents.length} {t('audit.steps') || 'steps'}</span>
            </div>

            <!-- Events in this round -->
            <div class="ml-4 pl-4 border-l-2 border-gray-200 dark:border-gray-700 space-y-2">
              {#each roundEvents as event}
                {@const color = getAgentColor(event.agent)}
                <div
                  class="rounded-lg border transition-all cursor-pointer hover:shadow-md"
                  style="background: {color.light}; border-color: {color.border}30;"
                  class:ring-2={expandedEvent === event.id}
                  on:click={() => expandedEvent = expandedEvent === event.id ? null : event.id}
                >
                  <div class="flex items-center gap-3 px-3 py-2">
                    <!-- Agent dot -->
                    <span class="w-3 h-3 rounded-full flex-shrink-0" style="background: {color.bg}"></span>

                    <!-- Agent name -->
                    <span class="text-xs font-semibold text-gray-700 dark:text-gray-200 min-w-[80px]">
                      {event.agent || '—'}
                    </span>

                    <!-- Action icon + label -->
                    <span class="text-xs text-gray-600 dark:text-gray-300 flex items-center gap-1">
                      {getActionIcon(event.action)}
                      {event.action || '—'}
                    </span>

                    <!-- Tokens -->
                    {#if event.tokens_used}
                      <span class="ml-auto text-xs text-gray-400 dark:text-gray-500 font-mono">
                        {event.tokens_used.toLocaleString()} tok
                      </span>
                    {/if}

                    <!-- Time -->
                    <span class="text-xs text-gray-400 dark:text-gray-500 font-mono min-w-[60px] text-right">
                      {formatTime(event.timestamp)}
                    </span>
                  </div>

                  <!-- Expanded content -->
                  {#if expandedEvent === event.id}
                    <div class="px-3 pb-3 pt-1 border-t" style="border-color: {color.border}20;">
                      {#if event.llm_model}
                        <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
                          <span class="font-medium">{t('audit.model') || 'Model'}:</span> {event.llm_model}
                        </p>
                      {/if}
                      {#if event.output_content}
                        <div class="mt-2 p-2 bg-white/60 dark:bg-gray-900/60 rounded text-xs whitespace-pre-wrap max-h-48 overflow-y-auto text-gray-700 dark:text-gray-300">
                          {event.output_content.substring(0, 500)}{event.output_content.length > 500 ? '…' : ''}
                        </div>
                      {/if}
                      {#if event.input_content}
                        <div class="mt-2 p-2 bg-white/40 dark:bg-gray-900/40 rounded text-xs whitespace-pre-wrap max-h-32 overflow-y-auto text-gray-500 dark:text-gray-400">
                          <span class="font-medium">{t('audit.input') || 'Input'}:</span> {event.input_content.substring(0, 300)}{event.input_content.length > 300 ? '…' : ''}
                        </div>
                      {/if}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>
{/if}
