<script>
  /**
   * ModeSwitcher — Toggle between Blueprint Mode and Workflow Mode.
   *
   * Blueprint Mode (default): Phase 3 functionality, only asset nodes.
   * Workflow Mode: Shows workflow nodes, allows control flow edges.
   */
  import { i18n } from '../../lib/i18n/index.js';
  import { canvasStore } from '../../lib/blueprint/store.svelte.js';

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let mode = $derived(canvasStore.mode);
</script>

<div
  class="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1"
  style="pointer-events: auto;"
  data-testid="mode-switcher"
>
  <button
    class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors
      {mode === 'blueprint'
        ? 'bg-white dark:bg-gray-600 text-blue-700 dark:text-blue-200 shadow-sm'
        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'}"
    onclick={() => canvasStore.setMode('blueprint')}
    data-testid="mode-blueprint"
    title={t('blueprint.mode.blueprintHint') || 'Asset relationships only — workflow nodes will be removed'}
  >
    🧩 {t('blueprint.mode.blueprint')}
  </button>
  <button
    class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors
      {mode === 'workflow'
        ? 'bg-white dark:bg-gray-600 text-violet-700 dark:text-violet-200 shadow-sm'
        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'}"
    onclick={() => canvasStore.setMode('workflow')}
    data-testid="mode-workflow"
    title={t('blueprint.mode.workflowHint') || 'Full canvas — includes workflow steps, gates, and control flow'}
  >
    ⚙️ {t('blueprint.mode.workflow')}
  </button>
</div>
