<script>
  import { Handle, Position } from '@xyflow/svelte';

  let { id, data, selected = false } = $props();

  let phaseName = $derived(data?.label || data?.phase_name || 'Phase');
  let phaseDescription = $derived(data?.description || '');
  let assignedRoles = $derived(data?.roles || []);
  let maxRounds = $derived(data?.max_rounds ?? 3);
  let phaseColor = $derived(data?.color || '#6366f1');
</script>

<div
  class="phase-container"
  class:selected
  style="--phase-color: {phaseColor}; --phase-bg: {phaseColor}15; --phase-border: {phaseColor}40;"
>
  <!-- Phase-level handles for sequential phase transitions -->
  <Handle type="target" position={Position.Left} id="in" class="phase-handle" />
  <Handle type="source" position={Position.Right} id="out" class="phase-handle" />

  <!-- Phase Header -->
  <div class="phase-header" style="background: {phaseColor};">
    <span class="phase-icon">📋</span>
    <span class="phase-label">{phaseName}</span>
    <span class="phase-rounds">{maxRounds}r</span>
  </div>

  <!-- Phase Body -->
  <div class="phase-body">
    {#if phaseDescription}
      <p class="phase-desc">{phaseDescription}</p>
    {/if}

    {#if assignedRoles.length > 0}
      <div class="phase-roles">
        {#each assignedRoles as role}
          <span class="role-tag" style="border-color: {phaseColor};">{role}</span>
        {/each}
      </div>
    {:else}
      <p class="phase-empty">Drop agent nodes inside this phase</p>
    {/if}
  </div>
</div>

<style>
  .phase-container {
    background: var(--phase-bg, #6366f115);
    border: 2px dashed var(--phase-border, #6366f140);
    border-radius: 16px;
    min-width: 280px;
    min-height: 180px;
    font-size: 13px;
    transition: all 0.2s ease;
    position: relative;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .phase-container.selected {
    border-style: solid;
    border-color: var(--phase-color, #6366f1);
    box-shadow: 0 0 0 2px var(--phase-color, #6366f1), 0 4px 16px rgba(0,0,0,0.12);
  }
  .phase-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    color: white;
    font-weight: 700;
    font-size: 14px;
  }
  .phase-icon { font-size: 16px; opacity: 0.9; }
  .phase-label { flex: 1; }
  .phase-rounds {
    font-size: 11px;
    font-weight: 600;
    background: rgba(255,255,255,0.2);
    padding: 2px 8px;
    border-radius: 10px;
  }
  .phase-body {
    padding: 12px 16px;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .phase-desc {
    font-size: 12px;
    color: #6b7280;
    margin: 0;
    line-height: 1.4;
  }
  :global(.dark) .phase-desc { color: #9ca3af; }
  .phase-roles {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .role-tag {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    border: 1px solid;
    background: rgba(255,255,255,0.6);
    color: #374151;
  }
  :global(.dark) .role-tag {
    background: rgba(0,0,0,0.3);
    color: #d1d5db;
  }
  .phase-empty {
    font-size: 11px;
    color: #9ca3af;
    font-style: italic;
    margin: 0;
  }
  :global(.phase-handle) {
    width: 12px !important;
    height: 12px !important;
    background: white !important;
    border: 2px solid #6366f1 !important;
    border-radius: 50% !important;
    transition: all 0.2s ease;
  }
  :global(.phase-handle):hover {
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.25);
  }
</style>
