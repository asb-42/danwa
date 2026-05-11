<script>
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any }} */
  let { data } = $props();
</script>

<div class="workflow-node input-node" class:active={data.isActive}>
  <div class="node-header">
    <span class="node-icon">📥</span>
    <span class="node-title">Input</span>
  </div>
  <div class="node-body">
    <p class="node-label">{data.label || 'Case Text'}</p>
  </div>
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .workflow-node {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    padding: 12px;
    min-width: 140px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
  }
  :global(.dark) .workflow-node {
    background: #1f2937;
    border-color: #4b5563;
  }
  .workflow-node.active {
    border-color: #3b82f6;
    box-shadow: 0 0 12px rgba(59,130,246,0.3);
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
  }
  .node-icon { font-size: 16px; }
  .node-title {
    font-weight: 600;
    color: #1e40af;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  :global(.dark) .node-title { color: #93c5fd; }
  .node-body { color: #6b7280; font-size: 12px; }
  :global(.dark) .node-body { color: #9ca3af; }
  .node-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 160px;
  }
</style>
