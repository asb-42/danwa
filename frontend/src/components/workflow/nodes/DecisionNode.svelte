<script>
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any }} */
  let { data } = $props();

  let consensusPercent = $derived(
    data.consensus != null ? Math.round(data.consensus * 100) : null
  );
  let thresholdPercent = $derived(
    data.threshold != null ? Math.round(data.threshold * 100) : 80
  );
  let isAboveThreshold = $derived(
    consensusPercent != null && consensusPercent >= thresholdPercent
  );
</script>

<div
  class="workflow-node decision-node"
  class:above={isAboveThreshold}
  class:below={consensusPercent != null && !isAboveThreshold}
>
  <Handle type="target" position={Position.LEFT} />
  <div class="node-header">
    <span class="node-icon">⚖️</span>
    <span class="node-title">Consensus Check</span>
  </div>
  <div class="node-body">
    {#if consensusPercent != null}
      <div class="consensus-bar">
        <div
          class="consensus-fill"
          class:above={isAboveThreshold}
          class:below={!isAboveThreshold}
          style="width: {consensusPercent}%"
        ></div>
      </div>
      <div class="consensus-text">
        <span class="consensus-value">{consensusPercent}%</span>
        <span class="consensus-threshold">/ {thresholdPercent}%</span>
      </div>
    {:else}
      <span class="pending-text">Waiting...</span>
    {/if}
  </div>
  <Handle type="source" position={Position.RIGHT} id="pass" />
  <Handle type="source" position={Position.BOTTOM} id="loop" style="bottom: -4px;" />
</div>

<style>
  .workflow-node {
    background: white;
    border: 2px solid #f59e0b;
    border-radius: 12px;
    padding: 12px;
    min-width: 160px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
  }
  :global(.dark) .workflow-node { background: #1f2937; }
  .workflow-node.above { border-color: #10b981; }
  .workflow-node.below { border-color: #ef4444; }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }
  .node-icon { font-size: 16px; }
  .node-title {
    font-weight: 600;
    color: #92400e;
    font-size: 12px;
  }
  :global(.dark) .node-title { color: #fbbf24; }
  .consensus-bar {
    width: 100%;
    height: 8px;
    background: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 4px;
  }
  :global(.dark) .consensus-bar { background: #374151; }
  .consensus-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
  }
  .consensus-fill.above { background: #10b981; }
  .consensus-fill.below { background: #ef4444; }
  .consensus-text {
    display: flex;
    align-items: baseline;
    gap: 4px;
    font-size: 12px;
  }
  .consensus-value { font-weight: 700; color: #374151; }
  :global(.dark) .consensus-value { color: #e5e7eb; }
  .consensus-threshold { color: #9ca3af; font-size: 10px; }
  .pending-text { color: #9ca3af; font-size: 12px; }
</style>
