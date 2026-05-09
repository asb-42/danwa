<script>
  import { i18n } from '../../lib/i18n/index.js';

  export let entryA = null;
  export let entryB = null;
  export let nodeId = '';

  $: _ = $i18n;
</script>

<div class="diff-detail">
  <h3>{nodeId}</h3>
  <div class="split-panel">
    <div class="panel">
      <h4>{_.diff?.nodeDetail?.sessionA || 'Session A'}</h4>
      {#if entryA}
        <div class="field"><span class="label">Actor:</span> {entryA.actor || '—'}</div>
        <div class="field"><span class="label">Event:</span> {entryA.event_type || '—'}</div>
        <div class="field"><span class="label">Latency:</span> {entryA.latency_ms || 0} ms</div>
        <div class="field"><span class="label">Tokens:</span> {(entryA.prompt_tokens || 0) + (entryA.completion_tokens || 0)}</div>
        <div class="field"><span class="label">Output Hash:</span> <span class="hash">{entryA.output_hash || '—'}</span></div>
      {:else}
        <p class="missing">No data</p>
      {/if}
    </div>
    <div class="panel">
      <h4>{_.diff?.nodeDetail?.sessionB || 'Session B'}</h4>
      {#if entryB}
        <div class="field"><span class="label">Actor:</span> {entryB.actor || '—'}</div>
        <div class="field"><span class="label">Event:</span> {entryB.event_type || '—'}</div>
        <div class="field"><span class="label">Latency:</span> {entryB.latency_ms || 0} ms</div>
        <div class="field"><span class="label">Tokens:</span> {(entryB.prompt_tokens || 0) + (entryB.completion_tokens || 0)}</div>
        <div class="field"><span class="label">Output Hash:</span> <span class="hash">{entryB.output_hash || '—'}</span></div>
      {:else}
        <p class="missing">No data</p>
      {/if}
    </div>
  </div>
  {#if entryA && entryB}
    <div class="comparison">
      <h4>{_.diff?.nodeDetail?.latencyComparison || 'Latency Comparison'}</h4>
      <span>{entryA.latency_ms || 0} ms vs {entryB.latency_ms || 0} ms
        ({(entryA.latency_ms || 0) - (entryB.latency_ms || 0) > 0 ? '+' : ''}{(entryA.latency_ms || 0) - (entryB.latency_ms || 0)} ms)
      </span>
      <h4>{_.diff?.nodeDetail?.tokenComparison || 'Token Comparison'}</h4>
      <span>{(entryA.prompt_tokens || 0) + (entryA.completion_tokens || 0)} vs {(entryB.prompt_tokens || 0) + (entryB.completion_tokens || 0)}</span>
    </div>
  {/if}
</div>

<style>
  .diff-detail {
    padding: 1rem;
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
  }
  h3 {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
  }
  h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
    color: #555;
  }
  .split-panel {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
  .panel {
    padding: 0.75rem;
    background: #f8f9fa;
    border-radius: 4px;
  }
  .field {
    font-size: 0.85rem;
    margin-bottom: 0.3rem;
  }
  .label {
    color: #666;
  }
  .hash {
    font-family: monospace;
    font-size: 0.75rem;
    word-break: break-all;
  }
  .missing {
    color: #999;
    font-style: italic;
  }
  .comparison {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #e0e0e0;
  }
</style>
