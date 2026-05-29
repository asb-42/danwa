<script>
  let { label = '', max = 0, icon = '' } = $props();
</script>

<div class="text-center">
  <span class="text-lg">{icon}</span>
  <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-tight">{label}</p>
</div>
