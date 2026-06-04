<script>
  /**
   * PhaseForm — Inspector form for wf-phase container nodes.
   *
   * Shows: phase name, description, assigned roles (multi-select),
   * max rounds, color, and agent node list within this phase.
   */
  
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';

  let { node, onsave, ondelete } = $props();

  const AVAILABLE_ROLES = [
    'analyst', 'creative-thinker', 'socratic-questioner',
    'strategist', 'expert-reviewer', 'steel-manner',
    'devils-advocate', 'fact-checker', 'troll',
    'mediator', 'ethicist', 'synthesizer',
    'moderator', 'critic', 'optimizer',
  ];

  const ROLE_LABELS = {
    'analyst': '📊 Analyst',
    'creative-thinker': '💡 Creative Thinker',
    'socratic-questioner': '❓ Socratic Questioner',
    'strategist': '🧠 Strategist',
    'expert-reviewer': '🔬 Expert Reviewer',
    'steel-manner': '🛡️ Steel Manner',
    'devils-advocate': '👿 Devil\'s Advocate',
    'fact-checker': '✅ Fact Checker',
    'troll': '🤡 Troll',
    'mediator': '🤝 Mediator',
    'ethicist': '⚖️ Ethicist',
    'synthesizer': '🔗 Synthesizer',
    'moderator': '🎯 Moderator',
    'critic': '🔍 Critic',
    'optimizer': '⚡ Optimizer',
  };

  let label = $state('');
  let description = $state('');
  let roles = $state([]);
  let maxRounds = $state(3);
  let color = $state('#6366f1');

  $effect(() => {
    label = node?.data?.label || node?.data?.phase_name || '';
    description = node?.data?.description || '';
    roles = node?.data?.roles || [];
    maxRounds = node?.data?.max_rounds ?? 3;
    color = node?.data?.color || '#6366f1';
  });

  function toggleRole(roleId) {
    if (roles.includes(roleId)) {
      roles = roles.filter(r => r !== roleId);
    } else {
      roles = [...roles, roleId];
    }
  }

  function handleSave() {
    canvasStore.updateNodeData(node.id, {
      label,
      phase_name: label,
      description,
      roles,
      max_rounds: maxRounds,
      color,
    });
    onsave?.();
  }

  // Get child nodes that are inside this phase (based on ELK parent reference)
  let childNodes = $derived(
    canvasStore.nodes.filter(n => n.parentId === node.id && n.id !== node.id)
  );
</script>

<div class="phase-form" data-testid="phase-form">
  <div class="form-group">
    <span class="form-label">Phase Container</span>
    <div class="form-hint">Configures a debate phase with assigned agent roles.</div>
  </div>

  <div class="form-group">
    <label class="form-label" for="phase-label">Phase Name</label>
    <input id="phase-label" type="text" class="form-input" bind:value={label} placeholder="e.g. Problem Framing" oninput={handleSave} />
  </div>

  <div class="form-group">
    <label class="form-label" for="phase-desc">Description</label>
    <textarea id="phase-desc" class="form-textarea" bind:value={description} placeholder="Phase purpose..." rows="2" oninput={handleSave}></textarea>
  </div>

  <div class="form-group">
    <label class="form-label">Assigned Roles</label>
    <div class="role-grid">
      {#each AVAILABLE_ROLES as roleId}
        <button
          class="role-chip"
          class:active={roles.includes(roleId)}
          onclick={() => { toggleRole(roleId); handleSave(); }}
        >
          {ROLE_LABELS[roleId] || roleId}
        </button>
      {/each}
    </div>
  </div>

  <div class="form-group">
    <label class="form-label" for="phase-rounds">Max Rounds</label>
    <input id="phase-rounds" type="number" class="form-input" bind:value={maxRounds} min="1" max="20" oninput={handleSave} />
  </div>

  <div class="form-group">
    <label class="form-label" for="phase-color">Header Color</label>
    <div class="color-row">
      <input id="phase-color" type="color" class="form-color" bind:value={color} oninput={handleSave} />
      <span class="form-value">{color}</span>
    </div>
  </div>

  {#if childNodes.length > 0}
    <div class="form-group">
      <span class="form-label">Child Nodes ({childNodes.length})</span>
      <div class="child-list">
        {#each childNodes as cn}
          <div class="child-item">
            <span class="child-type">{cn.type?.replace('wf-', '') || 'unknown'}</span>
            <span class="child-label">{cn.data?.label || cn.id}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <button class="delete-btn" onclick={() => ondelete?.()}>Remove Phase</button>
</div>

<style>
  .phase-form { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .form-group { display: flex; flex-direction: column; gap: 4px; }
  .form-label { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
  :global(.dark) .form-label { color: #9ca3af; }
  .form-hint { font-size: 11px; color: #9ca3af; font-style: italic; }
  .form-value { font-size: 13px; color: #374151; font-weight: 500; }
  :global(.dark) .form-value { color: #d1d5db; }
  .form-input, .form-textarea {
    padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; color: #1f2937; background: #fff;
    transition: border-color 0.15s; font-family: inherit;
  }
  .form-input:focus, .form-textarea:focus { outline: none; border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,0.15); }
  :global(.dark) .form-input, :global(.dark) .form-textarea { background: #1f2937; border-color: #4b5563; color: #e5e7eb; }
  .form-textarea { resize: vertical; }
  .role-grid { display: flex; flex-wrap: wrap; gap: 4px; max-height: 200px; overflow-y: auto; }
  .role-chip {
    font-size: 10px; padding: 3px 8px; border-radius: 12px; border: 1px solid #d1d5db;
    background: #f9fafb; color: #374151; cursor: pointer; transition: all 0.15s; font-family: inherit;
  }
  .role-chip:hover { border-color: #6366f1; background: #eef2ff; }
  .role-chip.active { border-color: #6366f1; background: #6366f1; color: white; }
  :global(.dark) .role-chip { background: #1f2937; border-color: #4b5563; color: #d1d5db; }
  :global(.dark) .role-chip:hover { border-color: #818cf8; background: #312e81; }
  :global(.dark) .role-chip.active { background: #6366f1; border-color: #818cf8; color: white; }
  .color-row { display: flex; align-items: center; gap: 8px; }
  .form-color { width: 36px; height: 28px; padding: 0; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; }
  .child-list { display: flex; flex-direction: column; gap: 3px; max-height: 150px; overflow-y: auto; }
  .child-item { display: flex; gap: 6px; padding: 3px 6px; border-radius: 4px; background: #f3f4f6; font-size: 11px; }
  :global(.dark) .child-item { background: #374151; }
  .child-type { font-weight: 600; color: #6366f1; text-transform: uppercase; font-size: 10px; }
  .child-label { color: #6b7280; overflow: hidden; text-overflow: ellipsis; }
  :global(.dark) .child-label { color: #9ca3af; }
  .delete-btn {
    margin-top: 8px; padding: 6px 12px; border: 1px solid #fca5a5; border-radius: 6px;
    background: #fef2f2; color: #ef4444; font-size: 12px; font-weight: 600; cursor: pointer;
    transition: all 0.15s; font-family: inherit;
  }
  .delete-btn:hover { background: #fecaca; }
  :global(.dark) .delete-btn { background: #450a0a; border-color: #991b1b; color: #fca5a5; }
  :global(.dark) .delete-btn:hover { background: #7f1d1d; }
</style>
