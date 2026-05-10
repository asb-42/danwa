<script>
  /**
   * Workflow Template Picker — dropdown for selecting workflow templates.
   *
   * @type {{ templates: any[], selectedId: string, onchange: (id: string) => void }}
   */
  let { templates = [], selectedId = '', onchange } = $props();
</script>

<div class="workflow-picker">
  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="wf-template">
    Workflow Template
  </label>
  <select
    id="wf-template"
    class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
    value={selectedId}
    onchange={(e) => onchange(e.target.value)}
  >
    <option value="">— Select workflow template —</option>
    {#each templates as tpl}
      <option value={tpl.id}>{tpl.name}</option>
    {/each}
  </select>
</div>
