<script>
  /**
   * DebateEventNode — a single node in the interactive debate tree.
   * Renders as a SvelteFlow node with actor info, content preview,
   * and a [+] button for forking.
   */
  import { Handle, Position } from '@xyflow/svelte';
  import { forkModalStore } from '../../lib/interactive/stores';

  let { id, data, selected = false } = $props();

  let isUser = $derived(data.actor_type === 'user');
  let isAgent = $derived(data.actor_type === 'agent');
  let isSystem = $derived(data.actor_type === 'system');
  let isA2A = $derived(data.actor_type === 'a2a');

  let actorIcon = $derived(
    isUser ? '👤' : isAgent ? '🤖' : isA2A ? '🔗' : '⚙️'
  );

  let borderColor = $derived(
    selected
      ? 'border-blue-500 ring-2 ring-blue-200 dark:ring-blue-800'
      : isUser
        ? 'border-green-300 dark:border-green-700'
        : isAgent
          ? 'border-purple-300 dark:border-purple-700'
          : isA2A
            ? 'border-orange-300 dark:border-orange-700'
            : 'border-gray-300 dark:border-gray-600'
  );

  let contentPreview = $derived(
    typeof data.content === 'string'
      ? data.content.slice(0, 150) + (data.content.length > 150 ? '...' : '')
      : JSON.stringify(data.content).slice(0, 150)
  );

  function handleFork(e) {
    e.stopPropagation();
    forkModalStore.open(data);
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="debate-node border-2 rounded-lg p-3 pt-5 bg-white dark:bg-gray-800 shadow-sm min-w-[200px] max-w-[350px] {borderColor} {selected ? 'selected' : ''}"
>
  <!-- Fork button — top-right corner, always discoverable -->
  <button
    class="fork-btn absolute -top-2 -right-2 w-6 h-6 rounded-full bg-blue-500 text-white text-xs font-bold shadow-md hover:bg-blue-600 hover:scale-110 transition-all flex items-center justify-center"
    onclick={handleFork}
    title="Fork: Start new action"
    aria-label="Fork this event"
  >
    +
  </button>

  <!-- Incoming handle (top) -->
  {#if data.parent_id}
    <Handle type="target" position={Position.Top} class="!w-3 !h-3 !bg-gray-400 dark:!bg-gray-500" />
  {/if}

  <!-- Actor header -->
  <div class="flex items-center gap-2 mb-2">
    <span class="text-lg">{actorIcon}</span>
    <div class="flex-1 min-w-0">
      <div class="text-sm font-semibold text-gray-800 dark:text-gray-100 truncate">
        {data.actor_id}
      </div>
      {#if data.role}
        <div class="text-xs text-gray-500 dark:text-gray-400">{data.role}</div>
      {/if}
    </div>
    <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
      {data.event_type}
    </span>
  </div>

  <!-- Content preview -->
  <div class="text-sm text-gray-700 dark:text-gray-300 mb-2 line-clamp-3">
    {contentPreview}
  </div>

  <!-- Footer -->
  <div class="flex items-center justify-between text-[10px] text-gray-400 dark:text-gray-500">
    <span>{new Date(data.created_at).toLocaleTimeString()}</span>
    {#if data.tokens_output}
      <span>{data.tokens_output} tokens</span>
    {/if}
  </div>

  <!-- Outgoing handle (bottom) -->
  <Handle type="source" position={Position.Bottom} class="!w-3 !h-3 !bg-gray-400 dark:!bg-gray-500" />
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
    opacity: 0.4;
    transition: opacity 0.15s, transform 0.15s;
  }
  .debate-node:hover .fork-btn {
    opacity: 1;
  }
  .fork-btn:hover {
    opacity: 1;
    transform: scale(1.1);
  }
  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
