<script>
  import { fly } from 'svelte/transition';
  import MarkdownRenderer from './MarkdownRenderer.svelte';
  import { i18n } from '../lib/i18n/index.js';

  /** @type {{ role: string, content: string, tokens_used?: number, model?: string, status?: string, round?: number }} */
  export let entry = {};
  /** @type {boolean} Whether this card is currently "thinking" (live) */
  export let thinking = false;

  let expanded = false;

  $: t = (key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  };

  $: role = entry.role || 'unknown';
  $: content = entry.content || '';
  $: tokens = entry.tokens_used || entry.tokens || 0;
  $: model = entry.model || entry.profile || '';
  $: isLong = content.length > 400;
  $: preview = isLong && !expanded ? content.substring(0, 400) + '…' : content;

  const ROLE_META = {
    strategist: { icon: '🎯', nameKey: 'agent.strategist', color: '#3b82f6', css: 'blue' },
    critic:     { icon: '🔍', nameKey: 'agent.critic',     color: '#ef4444', css: 'red' },
    optimizer:  { icon: '⚡', nameKey: 'agent.optimizer',  color: '#f59e0b', css: 'amber' },
    moderator:  { icon: '⚖️', nameKey: 'agent.moderator',  color: '#8b5cf6', css: 'violet' },
  };

  $: meta = ROLE_META[role] || { icon: '🤖', nameKey: role, color: '#6b7280', css: 'gray' };
  $: roleName = t(meta.nameKey);
</script>

<div
  class="agent-card relative bg-zinc-900/70 border border-zinc-700 hover:border-zinc-500 rounded-2xl overflow-hidden transition-all duration-300"
  class:thinking
  style="--agent-color: {meta.color}"
  in:fly={{ y: 12, duration: 300 }}
>
  <!-- Top accent bar -->
  <div class="h-1.5 bg-gradient-to-r from-[var(--agent-color)] to-transparent"></div>

  <!-- Left accent bar -->
  <div class="absolute left-0 top-6 bottom-4 w-1 rounded-r bg-[var(--agent-color)]"></div>

  <div class="p-5 pl-5">
    <!-- Header: icon + name + model + tokens -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-zinc-800 flex items-center justify-center text-xl border border-zinc-700">
          {meta.icon}
        </div>
        <div>
          <div class="font-semibold text-white text-[15px]">{roleName}</div>
          {#if model}
            <div class="text-xs text-zinc-400 font-mono">{model}</div>
          {/if}
        </div>
      </div>

      <div class="text-right">
        {#if tokens > 0}
          <div class="text-xs text-zinc-500">{tokens} tokens</div>
        {/if}
        {#if thinking}
          <div class="mt-1 flex items-center gap-1.5 text-amber-400 text-xs">
            <span class="relative flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
            </span>
            {t('timeline.thinking')}
          </div>
        {/if}
      </div>
    </div>

    <!-- Content -->
    {#if content}
      <div class="text-sm text-zinc-300 leading-relaxed border-l-2 border-[var(--agent-color)] pl-3 mb-3">
        {#if isLong && !expanded}
          <MarkdownRenderer content={preview} />
        {:else}
          <MarkdownRenderer content={content} />
        {/if}
      </div>

      {#if isLong}
        <button
          class="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-colors"
          on:click={() => expanded = !expanded}
        >
          {expanded ? t('timeline.collapse') : t('timeline.expand', { count: content.length })}
        </button>
      {/if}
    {:else if thinking}
      <!-- Thinking placeholder -->
      <div class="flex gap-1.5 pl-3">
        <span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
        <span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
        <span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
      </div>
    {/if}
  </div>
</div>

<style>
  .agent-card.thinking {
    ring: 2px;
    ring-offset: 2px;
    ring-color: var(--agent-color);
    box-shadow: 0 0 0 2px var(--agent-color), 0 0 12px color-mix(in srgb, var(--agent-color) 30%, transparent);
  }
</style>
