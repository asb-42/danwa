<script>
  // Placeholder — will render debate round timeline in Sprint 4
  export let rounds = [];
</script>

<div class="space-y-3">
  {#if rounds.length === 0}
    <div class="flex items-center justify-center h-32 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
      <div class="text-center">
        <p class="text-gray-400 dark:text-gray-500 font-medium">Debate Timeline</p>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Round-by-round view — Sprint 4</p>
      </div>
    </div>
  {:else}
    {#each rounds as round, i}
      <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Round {i + 1}</h4>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
          {round.length} agent output{round.length !== 1 ? 's' : ''}
        </p>
      </div>
    {/each}
  {/if}
</div>
