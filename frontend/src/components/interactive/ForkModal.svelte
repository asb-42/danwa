<script>
  /**
   * ForkModal — modal for choosing what action to take when forking.
   *
   * Shows options: Agent (LLM), A2A (external agent), HITL (human input).
   * Loads available agent bundles from danwa-modules.
   */
  import { eventStore, spaceStore } from '../../lib/interactive/stores';

  let { targetEvent = null, spaceId = null, onclose = null } = $props();

  let selectedType = $state('agent');
  let agentRole = $state('strategist');
  let agentMessage = $state('');
  let a2aUrl = $state('');
  let hitlQuery = $state('');
  let loading = $state(false);
  let error = $state(null);

  // Computed value for textarea binding
  let messageValue = $derived(selectedType === 'hitl' ? hitlQuery : agentMessage);

  function setMessageValue(val) {
    if (selectedType === 'hitl') {
      hitlQuery = val;
    } else {
      agentMessage = val;
    }
  }

  // Pre-fill message based on context
  $effect(() => {
    if (targetEvent) {
      const content =
        typeof targetEvent.content === 'string'
          ? targetEvent.content
          : JSON.stringify(targetEvent.content);
      agentMessage = `Bezüglich: "${content.slice(0, 100)}..."`;
    }
  });

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

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="modal-overlay fixed inset-0 bg-black/50 flex items-center justify-center z-50"
  onclick={(e) => {
    if (e.target === e.currentTarget) onclose?.();
  }}
>
  <div class="modal bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
    <!-- Header -->
    <div class="px-6 py-4 border-b border-gray-100">
      <h2 class="text-lg font-semibold text-gray-800">Neue Aktion starten</h2>
      <p class="text-sm text-gray-500 mt-1">
        Fork von: {targetEvent?.actor_id || 'Unbekannt'}
      </p>
    </div>

    <!-- Body -->
    <div class="px-6 py-4">
      <!-- Action type selector -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Aktionsart
        </label>
        <div class="flex gap-2">
          <button
            class="flex-1 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-colors
              {selectedType === 'agent'
              ? 'border-purple-500 bg-purple-50 text-purple-700'
              : 'border-gray-200 hover:border-gray-300'}"
            onclick={() => (selectedType = 'agent')}
          >
            🤖 Agent (LLM)
          </button>
          <button
            class="flex-1 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-colors
              {selectedType === 'a2a'
              ? 'border-orange-500 bg-orange-50 text-orange-700'
              : 'border-gray-200 hover:border-gray-300'}"
            onclick={() => (selectedType = 'a2a')}
          >
            🔗 A2A Agent
          </button>
          <button
            class="flex-1 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-colors
              {selectedType === 'hitl'
              ? 'border-green-500 bg-green-50 text-green-700'
              : 'border-gray-200 hover:border-gray-300'}"
            onclick={() => (selectedType = 'hitl')}
          >
            👤 Mensch
          </button>
        </div>
      </div>

      <!-- Agent options -->
      {#if selectedType === 'agent'}
        <div class="mb-4">
          <label for="agent-role" class="block text-sm font-medium text-gray-700 mb-1">
            Rolle
          </label>
          <select
            id="agent-role"
            bind:value={agentRole}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-200 focus:border-purple-500"
          >
            <option value="strategist">Strategist</option>
            <option value="critic">Critic</option>
            <option value="optimist">Optimist</option>
            <option value="devil">Devil's Advocate</option>
            <option value="mediator">Mediator</option>
            <option value="creative">Creative Thinker</option>
          </select>
        </div>
      {/if}

      <!-- A2A options -->
      {#if selectedType === 'a2a'}
        <div class="mb-4">
          <label for="a2a-url" class="block text-sm font-medium text-gray-700 mb-1">
            Agent URL
          </label>
          <input
            id="a2a-url"
            type="url"
            bind:value={a2aUrl}
            placeholder="https://example.com/a2a"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-200 focus:border-orange-500"
          />
        </div>
      {/if}

      <!-- Message / Query input -->
      <div class="mb-4">
        <label for="message-input" class="block text-sm font-medium text-gray-700 mb-1">
          {selectedType === 'hitl' ? 'Frage an den Nutzer' : 'Nachricht / Anweisung'}
        </label>
        <textarea
          id="message-input"
          value={messageValue}
          oninput={(e) => setMessageValue(e.target.value)}
          rows="3"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-500 resize-none"
          placeholder={selectedType === 'hitl'
            ? 'Was soll der Nutzer entscheiden?'
            : 'Was soll der Agent analysieren oder tun?'}
        ></textarea>
      </div>

      {#if error}
        <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
      <button
        class="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
        onclick={onclose}
      >
        Abbrechen
      </button>
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        onclick={handleSubmit}
        disabled={loading}
      >
        {loading ? 'Wird gesendet...' : 'Starten'}
      </button>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    animation: fadeIn 0.15s ease-out;
  }
  .modal {
    animation: slideUp 0.2s ease-out;
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
