<script>
  /**
   * PipelineEdge — single edge in the WorkflowPipeline.
   * Renders path + optional label + animated particles when active.
   */
  import { EDGE_KIND } from '../../../lib/workflow/pipeline-utils.js';

  let {
    edge,
    path = '',
    labelPos = null,
    active = false,
    mode = 'static',
  } = $props();

  let isFeedback = $derived(edge.kind === EDGE_KIND.FEEDBACK);
  let shouldAnimate = $derived(active && (mode === 'live' || mode === 'replay'));
  let markerEnd = $derived(isFeedback ? 'url(#workflow-pipeline-arrowhead-feedback)' : 'url(#workflow-pipeline-arrowhead)');
  let strokeClass = $derived(
    isFeedback
      ? 'text-amber-500 dark:text-amber-400'
      : 'text-gray-300 dark:text-gray-600'
  );
  let particleFill = $derived(isFeedback ? 'fill-amber-500' : 'fill-blue-500');
  let particleDur = $derived(isFeedback ? '3s' : '2s');
</script>

{#if path}
  <path
    d={path}
    fill="none"
    stroke="currentColor"
    stroke-width={isFeedback ? '1.5' : '2'}
    stroke-dasharray={isFeedback ? '4,3' : null}
    class={strokeClass}
    {markerEnd}
  />

  {#if labelPos && edge.label}
    <text
      x={labelPos.x}
      y={labelPos.y}
      font-size="9"
      font-weight="500"
      class={isFeedback ? 'fill-amber-600 dark:fill-amber-400' : 'fill-gray-500 dark:fill-gray-400'}
      text-anchor="middle"
    >{edge.label}</text>
  {/if}

  {#if shouldAnimate}
    <circle r="3" class={particleFill} opacity="0.8">
      <animateMotion dur={particleDur} repeatCount="indefinite" {path} />
    </circle>
  {/if}
{/if}
