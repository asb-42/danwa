<script>
  /**
   * PipelineLegend — explains the status colors and feedback edge.
   * Used at the bottom of the visualization card.
   */
  import { tStore } from '../../../lib/i18n/index.js';

  let { compact = false } = $props();
  let t = $derived($tStore);
</script>

<div class="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
  <div class="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400">
    <span class="flex items-center gap-1.5">
      <span class="w-2.5 h-2.5 rounded-full" style="background:#9ca3af"></span>
      {t('workflowPipeline.legend.pending') || 'Pending'}
    </span>
    <span class="flex items-center gap-1.5">
      <span class="w-2.5 h-2.5 rounded-full" style="background:#3b82f6"></span>
      {t('workflowPipeline.legend.running') || 'Running'}
    </span>
    <span class="flex items-center gap-1.5">
      <span class="w-2.5 h-2.5 rounded-full" style="background:#10b981"></span>
      {t('workflowPipeline.legend.done') || 'Done'}
    </span>
    <span class="flex items-center gap-1.5">
      <span class="w-2.5 h-2.5 rounded-full" style="background:#ef4444"></span>
      {t('workflowPipeline.legend.failed') || 'Failed'}
    </span>
    {#if !compact}
      <span class="flex items-center gap-1.5">
        <span class="w-4 h-0 inline-block" style="border-top: 1.5px dashed #f59e0b"></span>
        {t('workflowPipeline.legend.retry') || 'Retry loop'}
      </span>
    {/if}
  </div>
</div>
