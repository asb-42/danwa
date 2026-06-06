<script>
  /**
   * PhaseNode — Group node for the live workflow canvas.
   *
   * Renders as a semi-transparent colored background that visually
   * groups agent nodes belonging to the same debate phase.
   * Supports runtime highlighting (active/completed).
   *
   * No input/output handles — this is a container, not a flow node.
   */

  /** @type {{ data: any }} */
  let { data } = $props();

  let phaseName = $derived(data?.name || data?.label || 'Phase');
  let phaseColor = $derived(data?.color || '#6366f1');
  let phaseDescription = $derived(data?.description || '');
  let isActive = $derived(data?.isActive || false);
  let isCompleted = $derived(data?.isCompleted || false);
</script>

<div
  class="phase-group"
  class:active={isActive}
  class:completed={isCompleted}
  style="--phase-color: {phaseColor}; --phase-bg: {phaseColor}12; --phase-border: {phaseColor}35;"
>
  <!-- Phase header badge -->
  <div class="phase-badge" style="background: {phaseColor};">
    <span class="phase-icon">📋</span>
    <span class="phase-name">{phaseName}</span>
    {#if isActive}
      <span class="phase-status">●</span>
    {:else if isCompleted}
      <span class="phase-status completed">✓</span>
    {/if}
  </div>

  {#if phaseDescription}
    <div class="phase-description">{phaseDescription}</div>
  {/if}
</div>

<style>
  .phase-group {
    background: var(--phase-bg, #6366f112);
    border: 2px dashed var(--phase-border, #6366f135);
    border-radius: 16px;
    min-width: 280px;
    min-height: 180px;
    font-size: 13px;
    transition: all 0.3s ease;
    position: relative;
    pointer-events: none;
  }
  .phase-group.active {
    border-style: solid;
    border-color: var(--phase-color, #6366f1);
    background: color-mix(in srgb, var(--phase-color, #6366f1) 8%, transparent);
    box-shadow: 0 0 20px color-mix(in srgb, var(--phase-color, #6366f1) 20%, transparent);
    animation: phase-glow 2s ease-in-out infinite alternate;
  }
  .phase-group.completed {
    border-style: solid;
    border-color: var(--phase-color, #6366f1);
    opacity: 0.6;
  }
  .phase-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    color: white;
    font-weight: 700;
    font-size: 13px;
    border-radius: 0 0 12px 0;
    border-radius: 14px;
    margin: 10px 0 0 10px;
    white-space: nowrap;
  }
  .phase-icon { font-size: 14px; opacity: 0.9; }
  .phase-name { letter-spacing: 0.02em; }
  .phase-status {
    font-size: 10px;
    margin-left: 4px;
    animation: pulse-dot 1.5s ease-in-out infinite;
  }
  .phase-status.completed {
    animation: none;
    opacity: 0.9;
  }
  .phase-description {
    position: absolute;
    bottom: 10px;
    left: 10px;
    right: 10px;
    font-size: 11px;
    color: #6b7280;
    font-style: italic;
    pointer-events: none;
  }
  :global(.dark) .phase-description {
    color: #9ca3af;
  }

  @keyframes phase-glow {
    from { box-shadow: 0 0 12px color-mix(in srgb, var(--phase-color, #6366f1) 15%, transparent); }
    to { box-shadow: 0 0 24px color-mix(in srgb, var(--phase-color, #6366f1) 30%, transparent); }
  }
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
</style>
