<script>
  /**
   * ToneProfileNode — Tone/Style configuration node.
   *
   * Blueprint Mode: source port (right) only — connects to Agent Blueprint.
   * Workflow Mode: config ports (left input, bottom output) + sequential output.
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  const STYLE_EMOJIS = {
    heated: '🔥',
    academic: '🎓',
    conversational: '💬',
    socratic: '❓',
    neutral: '⚖️',
  };

  let profileName = $derived(data?.label || data?.name || data?.profileName || 'Tone Profile');
  let style = $derived(data?.inline_profile?.style || data?.style || 'neutral');
  let emoji = $derived(STYLE_EMOJIS[style] || '⚖️');
  let isLinked = $derived(!!data?.tone_profile_id);
  let linkedName = $derived(data?.catalogProfileName || data?.tone_profile_id || '');
  let isWorkflowMode = $derived(data?.type?.startsWith('wf-'));
</script>

<div
  class="tone-profile-node"
  class:selected
  data-testid="node-tone-profile-{data?.blueprint_id || 'draft'}"
>
  <!-- Global badge (workflow mode only) -->
  {#if isWorkflowMode}
    <span class="global-badge">Global</span>
  {/if}

  <!-- Workflow mode: config input port (left) -->
  {#if isWorkflowMode}
    <Handle
      type="target"
      position={Position.Left}
      id="config-in"
      class="config-port port-config"
    />

    <!-- Workflow mode: config output port (bottom) -->
    <Handle
      type="source"
      position={Position.Bottom}
      id="config-out"
      class="config-port port-config"
    />

    <!-- Workflow mode: sequential output port (right) -->
    <Handle
      type="source"
      position={Position.Right}
      id="out"
      class="sequential-port port-sequence"
    />
  {:else}
    <!-- Blueprint mode: source port (right) — connects to Agent Blueprint -->
    <Handle type="source" position={Position.Right} class="port-tone" />
  {/if}

  <div class="node-content">
    <div class="node-header">
      <span class="node-emoji">{emoji}</span>
      <span class="node-type-label">Tone Profile</span>
    </div>

    <div class="node-body">
      <span class="node-name">{profileName}</span>
      {#if isLinked}
        <div class="linked-info">
          <span class="status-linked">✓</span>
          <span class="linked-name">{linkedName}</span>
        </div>
      {:else}
        <span class="style-label">{style}</span>
      {/if}
    </div>
  </div>
</div>

<style>
  .tone-profile-node {
    background: linear-gradient(135deg, #fff7ed, #fef3c7);
    border: 2px solid #f59e0b;
    border-radius: 16px;
    padding: 10px 14px;
    min-width: 140px;
    max-width: 180px;
    font-size: 13px;
    box-shadow: 0 2px 6px rgba(245, 158, 11, 0.15);
    transition: all 0.2s ease;
    position: relative;
  }
  :global(.dark) .tone-profile-node {
    background: linear-gradient(135deg, #451a03, #78350f);
    border-color: #d97706;
  }
  .tone-profile-node.selected {
    box-shadow: 0 0 0 2px #f59e0b, 0 4px 12px rgba(245, 158, 11, 0.25);
  }

  .global-badge {
    position: absolute;
    top: -8px;
    right: 8px;
    background: #f59e0b;
    color: white;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .node-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 2px;
  }
  .node-emoji { font-size: 16px; }
  .node-type-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
    font-weight: 600;
  }

  .node-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .node-name {
    font-weight: 700;
    font-size: 13px;
    color: #92400e;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  :global(.dark) .node-name { color: #fbbf24; }

  .linked-info {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .status-linked {
    font-size: 10px;
    color: #10b981;
    font-weight: 600;
  }
  .linked-name {
    font-size: 10px;
    color: #6b7280;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 120px;
  }
  :global(.dark) .linked-name { color: #9ca3af; }

  .style-label {
    font-size: 10px;
    color: #b45309;
    text-transform: capitalize;
  }
  :global(.dark) .style-label { color: #fbbf24; }

  /* Config port styling (bottom) — orange/yellow, hollow circle */
  :global(.config-port) {
    width: 10px !important;
    height: 10px !important;
    background: white !important;
    border: 2px solid #f59e0b !important;
    border-radius: 50% !important;
    bottom: -5px !important;
  }
  :global(.dark) :global(.config-port) {
    background: #451a03 !important;
  }

  /* Sequential port styling (right) — standard filled */
  :global(.sequential-port) {
    width: 8px !important;
    height: 8px !important;
    background: #f59e0b !important;
    border: 2px solid white !important;
    border-radius: 50% !important;
  }

  /* Blueprint mode: tone port (right) */
  :global(.port-tone) {
    width: 10px !important;
    height: 10px !important;
    background: white !important;
    border: 2px solid #f59e0b !important;
    border-radius: 50% !important;
  }
  :global(.dark) :global(.port-tone) {
    background: #451a03 !important;
  }
</style>
