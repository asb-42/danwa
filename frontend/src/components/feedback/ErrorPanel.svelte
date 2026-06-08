<script>
  /**
   * ErrorPanel — Structured error display with classification.
   *
   * Shows classified errors with icons, user-friendly messages,
   * copy-to-clipboard, and dismiss functionality.
   * Displays as a floating panel that doesn't block the UI.
   */
  import { feedbackStore } from '../../lib/stores/feedback.svelte.js';
  import { tStore } from '../../lib/i18n/index.js';

  let t = $derived($tStore);

  const errorIcons = {
    rate_limit: '⏱',
    timeout: '⌛',
    content_filter: '🛡',
    network: '🌐',
    unknown: '⚠',
  };

  const errorColors = {
    rate_limit: 'border-amber-700 bg-amber-950/80 text-amber-200',
    timeout: 'border-orange-700 bg-orange-950/80 text-orange-200',
    content_filter: 'border-purple-700 bg-purple-950/80 text-purple-200',
    network: 'border-blue-700 bg-blue-950/80 text-blue-200',
    unknown: 'border-red-700 bg-red-950/80 text-red-200',
  };

  const errorTitles = {
    rate_limit: 'Rate Limit',
    timeout: 'Timeout',
    content_filter: 'Content Filter',
    network: 'Connection',
    unknown: 'Error',
  };

  async function copyErrorDetails(error) {
    const details = [
      `Error Class: ${error.errorClass}`,
      `Message: ${error.message}`,
      error.nodeId ? `Node: ${error.nodeId}` : null,
      error.rawError ? `Details: ${error.rawError}` : null,
      `Time: ${new Date(error.timestamp).toISOString()}`,
    ].filter(Boolean).join('\n');

    try {
      await navigator.clipboard.writeText(details);
    } catch {
      // Fallback
      const w = window.open('', '_blank');
      w.document.write(`<pre>${details}</pre>`);
    }
  }
</script>

{#if feedbackStore.activeErrors.length > 0}
  <div
    class="fixed top-16 right-4 z-50 flex flex-col gap-2 max-w-md w-full pointer-events-none"
    role="alert"
    aria-live="assertive"
  >
    {#each feedbackStore.activeErrors as error (error.id)}
      <div
        class="pointer-events-auto rounded-lg border px-4 py-3 shadow-lg backdrop-blur-sm
               {errorColors[error.errorClass] || errorColors.unknown}"
      >
        <div class="flex items-start gap-3">
          <!-- Icon -->
          <span class="text-xl flex-shrink-0 mt-0.5">
            {errorIcons[error.errorClass] || errorIcons.unknown}
          </span>

          <div class="flex-1 min-w-0">
            <!-- Title -->
            <div class="flex items-center gap-2 mb-1">
              <span class="font-semibold text-sm">
                {errorTitles[error.errorClass] || 'Error'}
              </span>
              {#if error.nodeId}
                <span class="px-1.5 py-0.5 rounded bg-black/20 text-[10px] font-mono">
                  {error.nodeId}
                </span>
              {/if}
            </div>

            <!-- Message -->
            <p class="text-sm opacity-90">{error.message}</p>

            <!-- Raw error (collapsed) -->
            {#if error.rawError}
              <details class="mt-2">
                <summary class="text-[11px] opacity-60 cursor-pointer hover:opacity-80">
                  Technical details
                </summary>
                <pre class="mt-1 text-[10px] opacity-50 font-mono whitespace-pre-wrap break-all max-h-24 overflow-y-auto">{error.rawError}</pre>
              </details>
            {/if}
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 flex-shrink-0">
            <button
              class="p-1 rounded hover:bg-black/20 transition-colors"
              onclick={() => copyErrorDetails(error)}
              title="Copy error details"
              aria-label="Copy error details"
            >📋</button>
            <button
              class="p-1 rounded hover:bg-black/20 transition-colors"
              onclick={() => feedbackStore.dismissError(error.id)}
              title="Dismiss"
              aria-label="Dismiss error"
            >✕</button>
          </div>
        </div>
      </div>
    {/each}

    <!-- Dismiss all button when multiple errors -->
    {#if feedbackStore.activeErrors.length > 1}
      <div class="pointer-events-auto text-center">
        <button
          class="px-3 py-1 rounded-full bg-zinc-800/80 text-[11px] text-zinc-400 hover:text-zinc-200
                 border border-zinc-700 transition-colors"
          onclick={() => feedbackStore.dismissAllErrors()}
        >Dismiss all ({feedbackStore.activeErrors.length})</button>
      </div>
    {/if}
  </div>
{/if}
