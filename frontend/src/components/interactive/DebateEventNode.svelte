<script>
  /**
   * DebateEventNode — a single node in the interactive debate tree.
   * Renders as a SvelteFlow node with actor info, content preview,
   * and a [+] button for forking.
   */
  import { Handle, Position } from '@xyflow/svelte';

  let { id, data, selected = false, onFork = null } = $props();

  let isUser = $derived(data.actor_type === 'user');
  let isAgent = $derived(data.actor_type === 'agent');
  let isSystem = $derived(data.actor_type === 'system');
  let isA2A = $derived(data.actor_type === 'a2a');

  let actorIcon = $derived(
    isUser ? '👤' : isAgent ? '🤖' : isA2A ? '🔗' : '⚙️'
  );

  let borderColor = $derived(
    selected
      ? 'border-blue-500 ring-2 ring-blue-200'
      : isUser
        ? 'border-green-300'
        : isAgent
          ? 'border-purple-300'
          : isA2A
            ? 'border-orange-300'
            : 'border-gray-300'
  );

  let contentPreview = $derived(
    typeof data.content === 'string'
      ? data.content.slice(0, 150) + (data.content.length > 150 ? '...' : '')
      : JSON.stringify(data.content).slice(0, 150)
  );

  function handleFork(e) {
    e.stopPropagation();
    if (onFork) onFork(data);
  }
</script>

<div
  class="debate-node border-2 rounded-lg p-3 bg-white shadow-sm min-w-[200px] max-w-[350px] {borderColor} {selected ? 'selected' : ''}"
>
  <!-- Incoming handle (top) -->
  {#if data.parent_id}
    <Handle type="target" position={Position.Top} class="!w-3 !h-3 !bg-gray-400" />
  {/if}

  <!-- Actor header -->
  <div class="flex items-center gap-2 mb-2">
    <span class="text-lg">{actorIcon}</span>
    <div class="flex-1 min-w-0">
      <div class="text-sm font-semibold text-gray-800 truncate">
        {data.actor_id}
      </div>
      {#if data.role}
        <div class="text-xs text-gray-500">{data.role}</div>
      {/if}
    </div>
    <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
      {data.event_type}
    </span>
  </div>

  <!-- Content preview -->
  <div class="text-sm text-gray-700 mb-2 line-clamp-3">
    {contentPreview}
  </div>

  <!-- Footer -->
  <div class="flex items-center justify-between text-[10px] text-gray-400">
    <span>{new Date(data.created_at).toLocaleTimeString()}</span>
    {#if data.tokens_output}
      <span>{data.tokens_output} tokens</span>
    {/if}
  </div>

  <!-- [+] Fork button -->
  <button
    class="fork-btn absolute -bottom-3 left-1/2 -translate-x-1/2 w-6 h-6 rounded-full bg-blue-500 text-white text-sm font-bold shadow hover:bg-blue-600 transition-colors flex items-center justify-center"
    onclick={handleFork}
    title="Fork: Neue Aktion starten"
    aria-label="Fork this event"
  >
    +
  </button>

  <!-- Outgoing handle (bottom) -->
  <Handle type="source" position={Position.Bottom} class="!w-3 !h-3 !bg-gray-400" />
</div>

<style>
  .debate-node {
    position: relative;
    transition: box-shadow 0.15s, border-color 0.15s;
  }
  .debate-node:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
  .debate-node.selected {
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3);
  }
  .fork-btn {
    opacity: 0;
    transition: opacity 0.15s;
  }
  .debate-node:hover .fork-btn {
    opacity: 1;
  }
  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
