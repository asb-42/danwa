<script>
  /**
   * PipelineEmptyState — shown when no workflow data is available.
   * Same visual frame as the populated pipeline so the layout doesn't jump.
   */
  import { tStore } from '../../../lib/i18n/index.js';

  let {
    title = '',
    description = '',
    onStartDebate = null,
  } = $props();

  let t = $derived($tStore);

  let resolvedTitle = $derived(title || t('workflowPipeline.empty.title') || 'No workflow yet');
  let resolvedDescription = $derived(
    description || t('workflowPipeline.empty.description') || 'Start a debate to see the workflow visualization.'
  );
</script>

<div class="flex flex-col items-center justify-center gap-3 h-40 text-center">
  <div class="text-4xl opacity-50">🏛️</div>
  <p class="text-sm font-medium text-gray-700 dark:text-gray-200">{resolvedTitle}</p>
  <p class="text-xs text-gray-500 dark:text-gray-400 max-w-sm">{resolvedDescription}</p>
  {#if onStartDebate}
    <button
      type="button"
      class="mt-2 px-4 py-1.5 text-sm rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors"
      onclick={onStartDebate}
    >
      {t('workflowPipeline.empty.startDebate') || 'Start a debate'}
    </button>
  {/if}
</div>
