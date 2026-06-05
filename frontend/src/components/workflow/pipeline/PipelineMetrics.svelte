<script>
  /**
   * PipelineMetrics — small badge beneath a node showing
   * tokens / duration / consensus. Compact mode shows only
   * the most important number.
   */
  import { formatNumber } from '../../../lib/i18n/index.js';



  let { metrics, x = 0, y = 0, compact = false } = $props();

  let tokens = $derived(metrics?.tokens);
  let duration = $derived(metrics?.durationMs);
  let consensus = $derived(metrics?.consensusScore);
  let round = $derived(metrics?.round);

  function fmtDuration(ms) {
    if (ms == null) return '';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const rs = Math.round(s - m * 60);
    return `${m}m${rs}s`;
  }
</script>

{#if compact}
  {#if consensus != null}
    <text
      {x} {y}
      font-size="10"
      font-weight="600"
      text-anchor="middle"
      class="fill-gray-600 dark:fill-gray-300"
    >{Math.round(consensus * 100)}%</text>
  {:else if tokens != null}
    <text
      {x} {y}
      font-size="10"
      font-weight="600"
      text-anchor="middle"
      class="fill-gray-600 dark:fill-gray-300"
    >{formatNumber(tokens, { notation: 'compact' })}</text>
  {/if}
{:else}
  <text
    {x} {y}
    font-size="9"
    text-anchor="middle"
    class="fill-gray-500 dark:fill-gray-400"
  >
    {#if tokens != null}{formatNumber(tokens, { notation: 'compact' })} tok{/if}
    {#if duration != null} · {fmtDuration(duration)}{/if}
    {#if round != null} · R{round}{/if}
    {#if consensus != null} · {Math.round(consensus * 100)}%{/if}
  </text>
{/if}
