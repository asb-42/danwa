<script>
import { onMount } from 'svelte';
import { useSvelteFlow } from '@xyflow/svelte';

let { onready = () => {} } = $props();

const flow = useSvelteFlow();

// Fire onready exactly once on mount. Previously this used $effect, which
// re-ran whenever the parent passed a fresh onready closure (BlueprintCanvas
// wraps it in a new arrow function on every render), causing the parent's
// setTimeout(..., 100) to stack and fitView to run multiple times.
onMount(() => {
  onready(flow);
});
</script>
