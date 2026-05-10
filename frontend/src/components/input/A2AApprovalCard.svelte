<script>
  /**
   * A2A Approval Card — shows pending A2A inbound requests for approval.
   *
   * @type {{ jobId: string, agentId: string, topic: string, onApprove: () => void, onReject: () => void }}
   */
  let { jobId = '', agentId = '', topic = '', onApprove, onReject } = $props();
</script>

<div class="a2a-card p-4 rounded-lg border-2 border-orange-300 bg-orange-50 dark:bg-orange-900/20 dark:border-orange-700">
  <div class="flex items-start gap-3">
    <span class="text-2xl">🤖</span>
    <div class="flex-1">
      <p class="font-semibold text-gray-900 dark:text-white">
        Externer Agent möchte eine Debatte starten
      </p>
      {#if agentId}
        <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
          Agent: <code class="bg-gray-200 dark:bg-gray-700 px-1 rounded">{agentId}</code>
        </p>
      {/if}
      {#if topic}
        <p class="text-sm text-gray-700 dark:text-gray-300 mt-1 italic">
          "{topic.slice(0, 200)}{topic.length > 200 ? '…' : ''}"
        </p>
      {/if}
      <div class="flex gap-2 mt-3">
        <button
          onclick={onApprove}
          class="px-3 py-1.5 rounded bg-green-600 text-white text-sm hover:bg-green-700 transition-colors"
        >
          ✅ Annehmen
        </button>
        <button
          onclick={onReject}
          class="px-3 py-1.5 rounded bg-red-600 text-white text-sm hover:bg-red-700 transition-colors"
        >
          ❌ Ablehnen
        </button>
      </div>
    </div>
  </div>
</div>
