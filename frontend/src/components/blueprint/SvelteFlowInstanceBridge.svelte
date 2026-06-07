<script>
import { onMount } from 'svelte';
import { useSvelteFlow } from '@xyflow/svelte';

let { onready = () => {} } = $props();

const flow = useSvelteFlow();

// Fire onready exactly once on mount.  Originally this used $effect,
// which re-ran whenever the parent passed a fresh onready closure
// (BlueprintCanvas wraps it in a new arrow function on every render),
// causing fitView calls to stack.  We then moved the initial fit
// to SvelteFlow's built-in ``fitView`` prop (audit M8) so the bridge
// only needs to expose the flow instance for ``screenToFlowPosition``.
onMount(() => {
  onready(flow);
});
</script>
