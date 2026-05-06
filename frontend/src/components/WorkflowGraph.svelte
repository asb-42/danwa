<script>
  /**
   * WorkflowGraph — Wrapper around WorkflowCanvas.
   * This file exists for backward compatibility; the actual implementation
   * lives in workflow/WorkflowCanvas.svelte.
   */
  import WorkflowCanvas from './workflow/WorkflowCanvas.svelte';
  import OOBInputPanel from './workflow/OOBInputPanel.svelte';

  /** @type {{ debateId?: string, isRunning?: boolean }} */
  let { debateId = null, isRunning = false } = $props();
</script>

<div class="workflow-graph-container">
  <WorkflowCanvas />

  {#if isRunning && debateId}
    <OOBInputPanel {debateId} />
  {/if}
</div>

<style>
  .workflow-graph-container {
    position: relative;
    width: 100%;
    min-height: 500px;
  }
</style>
