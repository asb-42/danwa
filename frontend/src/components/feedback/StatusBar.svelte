<script>
  /**
   * StatusBar — Thin persistent status bar at the top of the viewport.
   *
   * Displays the current operation status sourced from
   * {@link feedbackStore.statusMessage}. Only visible when an operation
   * is actively in progress (status message is non-null); hidden
   * otherwise to avoid visual noise.
   *
   * **Visual behavior:**
   * - Animated spinner with type-based color coding:
   *   - `llm` → amber/yellow
   *   - `layout` → cyan
   *   - `workflow` → blue
   *   - default → zinc/gray
   * - Elapsed time counter updated every 100 ms.
   * - "⚠ slow" warning badge appears after 15 seconds.
   * - Model and provider badges shown when `llmState` is `'calling'`.
   *
   * **Accessibility:** Uses `role="status"` and `aria-live="polite"`
   * so screen readers announce status changes.
   *
   * **No props** — all state is read reactively from `feedbackStore`.
   */
  import { feedbackStore } from '../../lib/stores/feedback.svelte.js';

  let elapsed = $state(0);
  let timer = $state(null);

  // Start/stop timer when statusMessage changes
  $effect(() => {
    const status = feedbackStore.statusMessage;
    if (timer) { clearInterval(timer); timer = null; }

    if (status) {
      elapsed = Date.now() - status.since;
      timer = setInterval(() => {
        elapsed = Date.now() - status.since;
      }, 100);
    } else {
      elapsed = 0;
    }

    return () => { if (timer) clearInterval(timer); };
  });

  let isVisible = $derived(feedbackStore.statusMessage !== null);

  let statusColor = $derived.by(() => {
    const type = feedbackStore.statusMessage?.type;
    switch (type) {
      case 'llm': return 'text-amber-400 bg-amber-950/50 border-amber-800';
      case 'layout': return 'text-cyan-400 bg-cyan-950/50 border-cyan-800';
      case 'workflow': return 'text-blue-400 bg-blue-950/50 border-blue-800';
      default: return 'text-zinc-400 bg-zinc-900/50 border-zinc-700';
    }
  });

  let spinnerColor = $derived.by(() => {
    const type = feedbackStore.statusMessage?.type;
    switch (type) {
      case 'llm': return 'border-amber-400';
      case 'layout': return 'border-cyan-400';
      case 'workflow': return 'border-blue-400';
      default: return 'border-zinc-400';
    }
  });

  function formatElapsed(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  // Show slow warning after 15s
  let isSlow = $derived(elapsed > 15000);
</script>

{#if isVisible}
  <div
    class="flex items-center gap-2 px-3 py-1 border-b text-xs font-mono {statusColor} transition-all duration-200"
    role="status"
    aria-live="polite"
  >
    <!-- Spinner -->
    <span class="inline-block w-3 h-3 border-2 {spinnerColor} border-t-transparent rounded-full animate-spin"></span>

    <!-- Status text -->
    <span class="font-medium">{feedbackStore.statusMessage?.text}</span>

    <!-- Model/Provider badge for LLM state -->
    {#if feedbackStore.llmState === 'calling' && feedbackStore.llmModel}
      <span class="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] text-zinc-400">
        {feedbackStore.llmModel}
      </span>
      {#if feedbackStore.llmProvider}
        <span class="px-1 py-0.5 rounded bg-zinc-800 text-[9px] text-zinc-500 uppercase">
          {feedbackStore.llmProvider}
        </span>
      {/if}
    {/if}

    <div class="flex-1"></div>

    <!-- Elapsed time -->
    <span class="text-zinc-500">{formatElapsed(elapsed)}</span>

    <!-- Slow warning -->
    {#if isSlow}
      <span class="px-1.5 py-0.5 rounded bg-amber-900/50 text-[10px] text-amber-400">
        ⚠ slow
      </span>
    {/if}
  </div>
{/if}
