<script>
  /**
   * Plugin Selector — horizontal button strip for input plugin selection.
   *
   * @type {{ plugins: any[], selectedKey: string, onchange: (key: string) => void }}
   */
  let { plugins = [], selectedKey = '', onchange } = $props();

  const pluginIcons = {
    standard_text: '📝',
    stt: '🎤',
    a2a_inbound: '🤖',
    mcp: '🔧',
  };
</script>

<div class="plugin-selector flex gap-2 flex-wrap">
  {#each plugins as plugin}
    <button
      class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
        {selectedKey === plugin.plugin_key
          ? 'bg-blue-600 text-white shadow-md'
          : plugin.ui_hints?.is_available === false
            ? 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-600 cursor-not-allowed'
            : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}"
      onclick={() => {
        if (plugin.ui_hints?.is_available !== false) onchange(plugin.plugin_key);
      }}
      disabled={plugin.ui_hints?.is_available === false}
      title={plugin.ui_hints?.coming_soon ? 'Coming soon' : plugin.plugin_name}
    >
      <span>{pluginIcons[plugin.plugin_key] || '📦'}</span>
      <span>{plugin.plugin_name}</span>
      {#if plugin.ui_hints?.coming_soon}
        <span class="text-xs bg-yellow-200 text-yellow-800 px-1.5 rounded">Soon</span>
      {/if}
    </button>
  {/each}
</div>
