<script>
  import { tStore } from '../../lib/i18n/index.js';

  let { node = null } = $props();

  let t = $derived($tStore);
</script>

{#if node}
  <div class="node-detail">
    <h3>{t('replay.nodeDetail.title')}</h3>
    <div class="detail-grid">
      <div class="detail-row">
        <span class="label">Node ID:</span>
        <span class="value">{node.node_id || '—'}</span>
      </div>
      <div class="detail-row">
        <span class="label">{t('replay.nodeDetail.actor')}</span>
        <span class="value">{node.actor || '—'}</span>
      </div>
      <div class="detail-row">
        <span class="label">Event Type:</span>
        <span class="value">{node.event_type || '—'}</span>
      </div>
      <div class="detail-row">
        <span class="label">{t('replay.nodeDetail.timestamp')}</span>
        <span class="value">{node.timestamp || '—'}</span>
      </div>
      <div class="detail-row">
        <span class="label">{t('replay.nodeDetail.latency')}</span>
        <span class="value">{node.latency_ms || 0} ms</span>
      </div>
      <div class="detail-row">
        <span class="label">{t('replay.nodeDetail.tokens')}</span>
        <span class="value">
          {(node.prompt_tokens || 0) + (node.completion_tokens || 0)}
          ({node.prompt_tokens || 0} in / {node.completion_tokens || 0} out)
        </span>
      </div>
      <div class="detail-row">
        <span class="label">LLM Profile:</span>
        <span class="value">{node.llm_profile_id || '—'}</span>
      </div>
      <div class="detail-row">
        <span class="label">Input Hash:</span>
        <span class="value hash">{node.input_hash || '—'}</span>
      </div>
      <div class="detail-row">
        <span class="label">Output Hash:</span>
        <span class="value hash">{node.output_hash || '—'}</span>
      </div>
    </div>
    <div class="step-info">
      Step {node.step} of {node.total}
    </div>
  </div>
{/if}

<style>
  .node-detail {
    padding: 1rem;
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
  }
  h3 {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
  }
  .detail-grid {
    display: grid;
    grid-template-columns: 140px 1fr;
    gap: 0.4rem;
  }
  .detail-row {
    display: contents;
  }
  .label {
    color: #666;
    font-size: 0.85rem;
  }
  .value {
    font-size: 0.85rem;
    word-break: break-all;
  }
  .hash {
    font-family: monospace;
    font-size: 0.75rem;
  }
  .step-info {
    margin-top: 0.5rem;
    text-align: right;
    font-size: 0.8rem;
    color: #999;
  }
</style>
