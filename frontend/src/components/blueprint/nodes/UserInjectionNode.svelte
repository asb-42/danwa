<script>
  /**
   * UserInjectionNode — User injection point in workflow.
   *
   * Indigo (#6366f1) themed, 👤 icon.
   * LEFT target + RIGHT source + BOTTOM interjection handles.
   * Shows label, input_type indicator.
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let inputType = $derived(data?.config?.input_type || data?.input_type || 'user_query');
  const inputTypeLabels = {
    user_query: 'User Query',
    oob_input: 'OOB Input',
    external_event: 'External Event',
  };
</script>

<div
  class="blueprint-node user-injection-node"
  class:selected
  style="border-color: #6366f1; --node-bg: #eef2ff; --node-dark-bg: #1e1b4b; --node-border: #6366f1;"
  data-testid="node-wf-user-injection"
>
  <Handle type="target" position={Position.Left} id="in" />

  <div class="node-header">
    <span class="node-icon">👤</span>
    <span class="node-type-label">User Injection</span>
  </div>

  <div class="node-body">
    <span class="node-name">{data?.label || 'User Input'}</span>
    <div class="input-type-row">
      <span class="input-type-badge">{inputTypeLabels[inputType] || inputType}</span>
    </div>
  </div>

  <Handle type="source" position={Position.Right} id="out" />
  <!-- Interjection handle — external input enters here -->
  <Handle type="target" position={Position.Bottom} id="interjection" />
</div>

<style>
  .blueprint-node {
    background: var(--node-bg, #eef2ff);
    border: 2px solid var(--node-border, #6366f1);
    border-radius: 12px;
    padding: 12px;
    min-width: 180px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .blueprint-node {
    background: var(--node-dark-bg, #1e1b4b);
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px var(--node-border, #6366f1), 0 4px 12px rgba(0,0,0,0.15);
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
  }
  .node-icon { font-size: 16px; }
  .node-type-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
    font-weight: 600;
  }
  .node-body {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .node-name {
    font-weight: 700;
    font-size: 14px;
    color: #1f2937;
  }
  :global(.dark) .node-name { color: #e5e7eb; }
  .input-type-row { margin-top: 2px; }
  .input-type-badge {
    display: inline-block;
    font-size: 10px;
    color: #4338ca;
    background: #e0e7ff;
    border: 1px solid #6366f1;
    border-radius: 4px;
    padding: 1px 6px;
    font-weight: 600;
  }
  :global(.dark) .input-type-badge {
    color: #a5b4fc;
    background: #1e1b4b;
    border-color: #4338ca;
  }
</style>
