<script>
  /**
   * WorkflowGraph — thin wrapper around WorkflowPipeline.
   *
   * Kept for backward compatibility with existing call sites
   * (e.g. DebateView.svelte). New code should import WorkflowPipeline
   * directly and pick a mode + adapter.
   */
  import WorkflowPipeline from './workflow/WorkflowPipeline.svelte';
  import OOBInputPanel from './workflow/OOBInputPanel.svelte';
  import { useLiveWorkflowPipeline } from '../lib/workflowPipelineAdapter.svelte.js';

  /** @type {{ debateId?: string, isRunning?: boolean }} */
  let { debateId = null, isRunning = false } = $props();

  const pipeline = useLiveWorkflowPipeline(debateId);
</script>

<div class="workflow-graph-container">
  <WorkflowPipeline
    meta={pipeline.meta}
    nodes={pipeline.nodes}
    edges={pipeline.edges}
    activeNodeId={pipeline.activeNodeId}
    mode="live"
    interactive
    showMetrics
  />

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
