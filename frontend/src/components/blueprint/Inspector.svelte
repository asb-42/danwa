<script>
  /**
   * Inspector — Right column of the Blueprint Canvas.
   *
   * Context-sensitive panel that renders the appropriate form
   * based on the selected node type.
   */
  import { tStore } from '../../lib/i18n/index.js';
  import { canvasStore } from '../../lib/blueprint/store.svelte.js';

  // Forms
  import LLMProfileForm from './forms/LLMProfileForm.svelte';
  import AgentCoreForm from './forms/AgentCoreForm.svelte';
  import WorkflowNodeForm from './forms/WorkflowNodeForm.svelte';
  import ToneProfileForm from './forms/ToneProfileForm.svelte';
  import BundleAgentForm from './forms/BundleAgentForm.svelte';
  import PhaseForm from './forms/PhaseForm.svelte';
  import TransactionalNodePanel from './panels/TransactionalNodePanel.svelte';

  const TRANSACTIONAL_NODE_TYPES = ['wf-critic', 'wf-builder', 'wf-pragmatist', 'wf-angels-advocate'];

  let t = $derived($tStore);

  let selectedNode = $derived(canvasStore.selectedNode);
  let nodeType = $derived(selectedNode?.type);

  function handleSave(data) {
    // Node data already updated in the form component
  }

  function handleDelete() {
    canvasStore.clearSelection();
  }

  function handleClose() {
    canvasStore.clearSelection();
  }
</script>

{#if selectedNode}
  <div class="inspector" data-testid="blueprint-inspector">
    <div class="inspector-header">
      <span class="inspector-title">{t('blueprint.inspector.title') || 'Inspector'}</span>
      <button class="close-btn" onclick={handleClose} data-testid="inspector-close" title="Close">✕</button>
    </div>

    <div class="inspector-content">
      {#if nodeType === 'llm-profile'}
        <LLMProfileForm node={selectedNode} onsave={handleSave} ondelete={handleDelete} />
      {:else if nodeType === 'agent-core'}
        <AgentCoreForm node={selectedNode} onsave={handleSave} ondelete={handleDelete} />
      {:else if nodeType === 'wf-tone-profile' || nodeType === 'tone-profile'}
        <ToneProfileForm node={selectedNode} onsave={handleSave} ondelete={handleDelete} />
      {:else if nodeType === 'wf-agent'}
        <BundleAgentForm node={selectedNode} onsave={handleSave} ondelete={handleDelete} />
      {:else if nodeType === 'wf-phase'}
        <PhaseForm node={selectedNode} onsave={handleSave} ondelete={handleDelete} />
      {:else if ['wf-input', 'wf-initialize', 'wf-strategist', 'wf-critic', 'wf-optimizer', 'wf-moderator', 'wf-user-injection', 'wf-gate', 'wf-analyst', 'wf-creative', 'wf-fact-checker', 'wf-socratic-questioner', 'wf-expert-reviewer', 'wf-steel-manner', 'wf-devils-advocate', 'wf-troll', 'wf-mediator', 'wf-ethicist', 'wf-synthesizer', 'wf-builder', 'wf-pragmatist', 'wf-angels-advocate'].includes(nodeType)}
        <WorkflowNodeForm node={selectedNode} onsave={handleSave} ondelete={handleDelete} />
        {#if TRANSACTIONAL_NODE_TYPES.includes(nodeType)}
          <TransactionalNodePanel {nodeType} />
        {/if}
      {:else}
        <div class="inspector-empty">
          <p>Unknown node type: {nodeType}</p>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .inspector {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
  }
  .inspector-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
  }
  :global(.dark) .inspector-header { border-color: #374151; }
  .inspector-title {
    font-size: 13px;
    font-weight: 700;
    color: #374151;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  :global(.dark) .inspector-title { color: #d1d5db; }
  .close-btn {
    padding: 4px 8px;
    border: none;
    background: transparent;
    color: #9ca3af;
    cursor: pointer;
    font-size: 14px;
    border-radius: 4px;
    transition: all 0.15s ease;
  }
  .close-btn:hover {
    color: #374151;
    background: #f3f4f6;
  }
  :global(.dark) .close-btn:hover {
    color: #e5e7eb;
    background: #374151;
  }
  .inspector-content {
    flex: 1;
    overflow-y: auto;
  }
  .inspector-empty {
    padding: 24px 16px;
    text-align: center;
    color: #9ca3af;
    font-size: 13px;
  }
</style>
