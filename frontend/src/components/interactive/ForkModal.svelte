<script>
  /**
   * ForkModal — modal for choosing what action to take when forking.
   *
   * Shows options: Agent (LLM), A2A (external agent), HITL (human input).
   * Supports drag-by-header and resize via bottom-right handle.
   */
  import { eventStore, spaceStore } from '../../lib/interactive/stores';
  import { getLLMProfiles } from '../../lib/api/profile.js';
  import { tStore } from '../../lib/i18n/index.js';

  let t = $derived($tStore);
  let { targetEvent = null, spaceId = null, onclose = null } = $props();

  let selectedType = $state('agent');
  let agentRole = $state('strategist');
  let agentMessage = $state('');
  let a2aUrl = $state('');
  let hitlQuery = $state('');
  let loading = $state(false);
  let error = $state(null);
  let llmProfiles = $state([]);
  let selectedLlmProfile = $state('');

  // Drag state
  let dragging = $state(false);
  let dragOffsetX = $state(0);
  let dragOffsetY = $state(0);
  let modalX = $state(0);
  let modalY = $state(0);
  let modalWidth = $state(500);
  let modalHeight = $state(0);
  let modalEl = $state(null);
  let initialized = $state(false);

  // Resize state
  let resizing = $state(false);
  let resizeStartX = $state(0);
  let resizeStartY = $state(0);
  let resizeStartW = $state(0);
  let resizeStartH = $state(0);

  // Computed value for textarea binding
  let messageValue = $derived(selectedType === 'hitl' ? hitlQuery : agentMessage);

  function setMessageValue(val) {
    if (selectedType === 'hitl') {
      hitlQuery = val;
    } else {
      agentMessage = val;
    }
  }

  // Center modal on first render
  $effect(() => {
    if (modalEl && !initialized) {
      const rect = modalEl.getBoundingClientRect();
      modalX = Math.max(0, (window.innerWidth - rect.width) / 2);
      modalY = Math.max(0, (window.innerHeight - rect.height) / 3);
      modalWidth = rect.width;
      modalHeight = rect.height;
      initialized = true;
    }
  });

  // Pre-fill message based on context
  $effect(() => {
    if (targetEvent) {
      const content =
        typeof targetEvent.content === 'string'
          ? targetEvent.content
          : JSON.stringify(targetEvent.content);
      agentMessage = `Regarding: "${content.slice(0, 100)}..."`;
    }
  });

  // Fetch available LLM profiles
  $effect(() => {
    getLLMProfiles()
      .then((profiles) => {
        llmProfiles = profiles || [];
        if (llmProfiles.length > 0 && !selectedLlmProfile) {
          selectedLlmProfile = llmProfiles[0].id;
        }
      })
      .catch(() => {
        llmProfiles = [];
      });
  });

  // --- Drag ---
  function handleDragStart(e) {
    // Don't drag if clicking on a button or input
    if (e.target.closest('button, input, select, textarea')) return;
    dragging = true;
    dragOffsetX = e.clientX - modalX;
    dragOffsetY = e.clientY - modalY;
    e.preventDefault();
  }

  function handleDragMove(e) {
    if (!dragging) return;
    const maxX = window.innerWidth - 100;
    const maxY = window.innerHeight - 40;
    modalX = Math.max(0, Math.min(maxX, e.clientX - dragOffsetX));
    modalY = Math.max(0, Math.min(maxY, e.clientY - dragOffsetY));
  }

  function handleDragEnd() {
    dragging = false;
  }

  // --- Resize ---
  function handleResizeStart(e) {
    resizing = true;
    resizeStartX = e.clientX;
    resizeStartY = e.clientY;
    resizeStartW = modalWidth;
    resizeStartH = modalHeight || modalEl?.getBoundingClientRect().height || 400;
    e.preventDefault();
    e.stopPropagation();
  }

  function handleResizeMove(e) {
    if (!resizing) return;
    const dx = e.clientX - resizeStartX;
    const dy = e.clientY - resizeStartY;
    modalWidth = Math.max(400, Math.min(window.innerWidth - 40, resizeStartW + dx));
    modalHeight = Math.max(300, Math.min(window.innerHeight - 40, resizeStartH + dy));
  }

  function handleResizeEnd() {
    resizing = false;
  }

  async function handleSubmit() {
    if (!spaceId || !targetEvent) return;

    loading = true;
    error = null;

    try {
      switch (selectedType) {
        case 'agent':
          await eventStore.triggerAgent(spaceId, {
            parent_event_id: targetEvent.event_id,
            role: agentRole,
            llm_profile_id: selectedLlmProfile || undefined,
            message: agentMessage,
          });
          break;
        case 'a2a':
          await eventStore.triggerA2A(spaceId, {
            parent_event_id: targetEvent.event_id,
            agent_url: a2aUrl,
            message: agentMessage,
          });
          break;
        case 'hitl':
          await eventStore.triggerHITL(spaceId, {
            parent_event_id: targetEvent.event_id,
            query: hitlQuery,
          });
          break;
      }
      onclose?.();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') onclose?.();
  }
</script>

<svelte:window
  on:keydown={handleKeydown}
  on:mousemove={(e) => { handleDragMove(e); handleResizeMove(e); }}
  on:mouseup={() => { handleDragEnd(); handleResizeEnd(); }}
/>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="modal-overlay fixed inset-0 z-50"
  onmousemove={(e) => { handleDragMove(e); handleResizeMove(e); }}
  onmouseup={() => { handleDragEnd(); handleResizeEnd(); }}
>
  <div
    bind:this={modalEl}
    class="modal bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden"
    style="position: absolute; left: {modalX}px; top: {modalY}px; width: {modalWidth}px; {modalHeight ? `height: ${modalHeight}px;` : ''}"
    role="dialog"
    aria-modal="true"
  >
    <!-- Header (draggable) -->
    <div
      class="modal-header px-6 py-4 border-b border-gray-100 dark:border-gray-700 cursor-grab active:cursor-grabbing select-none"
      onmousedown={handleDragStart}
    >
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">{t('fork.title')}</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {t('fork.forkFrom', { actor: targetEvent?.actor_id || t('fork.unknown') })}
          </p>
        </div>
        <div class="text-gray-400 dark:text-gray-500 text-xs">⠿ drag</div>
      </div>
    </div>

    <!-- Body (scrollable) -->
    <div class="modal-body px-6 py-4 overflow-auto" style="{modalHeight ? `max-height: ${modalHeight - 160}px;` : ''}">
      <!-- Action type selector -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {t('fork.actionType')}
        </label>
        <div class="flex gap-2">
          <button
            class="flex-1 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-colors
              {selectedType === 'agent'
              ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
              : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 text-gray-700 dark:text-gray-300'}"
            onclick={() => (selectedType = 'agent')}
          >
            🤖 Agent (LLM)
          </button>
          <button
            class="flex-1 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-colors
              {selectedType === 'a2a'
              ? 'border-orange-500 bg-orange-50 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300'
              : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 text-gray-700 dark:text-gray-300'}"
            onclick={() => (selectedType = 'a2a')}
          >
            🔗 A2A Agent
          </button>
          <button
            class="flex-1 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-colors
              {selectedType === 'hitl'
              ? 'border-green-500 bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
              : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 text-gray-700 dark:text-gray-300'}"
            onclick={() => (selectedType = 'hitl')}
          >
            👤 {t('fork.human')}
          </button>
        </div>
      </div>

      <!-- Agent options -->
      {#if selectedType === 'agent'}
        <div class="mb-4">
          <label for="agent-role" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.role')}
          </label>
          <select
            id="agent-role"
            bind:value={agentRole}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-purple-200 dark:focus:ring-purple-800 focus:border-purple-500"
          >
            <option value="strategist">Strategist</option>
            <option value="critic">Critic</option>
            <option value="optimist">Optimist</option>
            <option value="devil">Devil's Advocate</option>
            <option value="mediator">Mediator</option>
            <option value="creative">Creative Thinker</option>
          </select>
        </div>

        <div class="mb-4">
          <label for="llm-profile" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.llmProfile')}
          </label>
          <select
            id="llm-profile"
            bind:value={selectedLlmProfile}
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-purple-200 dark:focus:ring-purple-800 focus:border-purple-500"
          >
            {#if llmProfiles.length === 0}
              <option value="">{t('fork.defaultProfile')}</option>
            {:else}
              {#each llmProfiles as profile}
                <option value={profile.id}>{profile.name || profile.id}</option>
              {/each}
            {/if}
          </select>
        </div>
      {/if}

      <!-- A2A options -->
      {#if selectedType === 'a2a'}
        <div class="mb-4">
          <label for="a2a-url" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {t('fork.agentUrl')}
          </label>
          <input
            id="a2a-url"
            type="url"
            bind:value={a2aUrl}
            placeholder="https://example.com/a2a"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-orange-200 dark:focus:ring-orange-800 focus:border-orange-500"
          />
        </div>
      {/if}

      <!-- Message / Query input -->
      <div class="mb-4">
        <label for="message-input" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {selectedType === 'hitl' ? t('fork.questionForUser') : t('fork.messageInstruction')}
        </label>
        <textarea
          id="message-input"
          value={messageValue}
          oninput={(e) => setMessageValue(e.target.value)}
          rows="8"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-200 dark:focus:ring-blue-800 focus:border-blue-500 resize-y min-h-[12rem]"
          placeholder={selectedType === 'hitl'
            ? t('fork.placeholderHuman')
            : t('fork.placeholderAgent')}
        ></textarea>
      </div>

      {#if error}
        <div class="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="px-6 py-4 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-3">
      <button
        class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
        onclick={onclose}
      >
        {t('common.cancel')}
      </button>
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        onclick={handleSubmit}
        disabled={loading}
      >
        {loading ? t('fork.sending') : t('fork.start')}
      </button>
    </div>

    <!-- Resize handle (bottom-right corner) -->
    <div
      class="resize-handle absolute bottom-0 right-0 w-5 h-5 cursor-nwse-resize opacity-40 hover:opacity-100 transition-opacity"
      onmousedown={handleResizeStart}
    >
      <svg class="w-5 h-5 text-gray-500 dark:text-gray-400" viewBox="0 0 20 20" fill="currentColor">
        <path d="M15.5 15.5L20 20H15.5V15.5ZM11 15.5H7V20H11V15.5ZM15.5 11V7H20V11H15.5Z" opacity="0.3"/>
        <path d="M20 20L14 20L20 14L20 20ZM20 11L20 17L14 17L14 11L20 11ZM11 20L17 20L17 14L11 14L11 20ZM11 11L17 11L17 17L11 17L11 11Z" opacity="0.6"/>
      </svg>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    background: rgba(0, 0, 0, 0.3);
    animation: fadeIn 0.15s ease-out;
  }
  .modal {
    animation: slideUp 0.2s ease-out;
  }
  .modal-header {
    user-select: none;
  }
  .resize-handle {
    touch-action: none;
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes slideUp {
    from { transform: translateY(10px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }
</style>
