<script>
  // Placeholder — will render consensus score gauge in Sprint 4
  let { score = 0, threshold = 0.8 } = $props();
</script>

<div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
  <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Consensus</h4>
  <div class="flex items-center space-x-4">
    <div class="flex-1">
      <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
        <div
          class="h-3 rounded-full transition-all duration-500
            {score >= threshold ? 'bg-green-500' : 'bg-blue-500'}"
          style="width: {Math.min(score * 100, 100)}%"
        ></div>
      </div>
    </div>
    <span class="text-lg font-bold
      {score >= threshold ? 'text-green-600 dark:text-green-400' : 'text-blue-600 dark:text-blue-400'}">
      {(score * 100).toFixed(0)}%
    </span>
  </div>
  <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
    Threshold: {(threshold * 100).toFixed(0)}%
    {#if score >= threshold}
      <span class="text-green-600 dark:text-green-400 ml-1">✓ Reached</span>
    {/if}
  </p>
</div>
