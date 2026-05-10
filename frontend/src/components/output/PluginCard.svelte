<script>
  /** @type {{ plugin: any, selected: boolean, onclick: () => void }} */
  let { plugin, selected = false, onclick } = $props();

  const formatIcons = {
    pdf: '📄',
    docx: '📝',
    mp3: '🎧',
    wav: '🎵',
  };
</script>

<button
  class="plugin-card p-4 rounded-lg border-2 transition-all cursor-pointer text-left w-full
    {selected
      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 dark:border-blue-400'
      : 'border-gray-200 bg-white dark:bg-gray-800 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500'}"
  {onclick}
>
  <div class="flex items-center gap-3 mb-2">
    <span class="text-2xl">
      {plugin.plugin_key === 'print' ? '🖨️' : plugin.plugin_key === 'tts' ? '🎙️' : '📦'}
    </span>
    <h3 class="font-semibold text-gray-900 dark:text-white">
      {plugin.plugin_name}
    </h3>
  </div>
  <div class="flex gap-2 flex-wrap">
    {#each plugin.supported_formats as fmt}
      <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
        bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
        {formatIcons[fmt] || '📁'} {fmt.toUpperCase()}
      </span>
    {/each}
  </div>
</button>
