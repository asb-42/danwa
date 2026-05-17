<script>
import { useSvelteFlow } from '@xyflow/svelte';

let { onready = () => {} } = $props();

const flow = useSvelteFlow();

$effect(() => {
  onready(flow);
});
</script>
