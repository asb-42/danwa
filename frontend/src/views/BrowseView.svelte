<!--
  BrowseView — Phase 4.9 list-graph browse mode.

  The plan calls for a Toggle "List / Graph" in the Browse view
  with a Cytoscape renderer on the Graph side.  Without a
  Cytoscape bundle spike we ship the *List* half of the
  toggle today: the user gets a tenant-wide list-graph of
  cases / debates / documents / tags with click-to-drill,
  served by the same /api/v1/graph/global endpoint the
  Cytoscape view would consume.

  The Cytoscape renderer is a planned follow-up (Phase 4.5-4.7)
  that will share this component's data flow and switch in
  a Cytoscape mount in place of the list renderer.

  @see plans/2026-06-14_case-space-workspace.md (Phase 4 & 4.9)
-->
<script>
  import { onMount } from 'svelte';
  import { tStore } from '../lib/i18n/index.js';
  import { currentTenant } from '../lib/stores/auth.svelte.js';
  import { addToast } from '../lib/stores.js';
  import { getGlobalGraph } from '../lib/api/graph.js';

  let { navigate } = $props();

  let t = $derived($tStore);
  let tenantId = $derived($currentTenant?.id);

  let mode = $state('list'); // 'list' | 'graph' (Cytoscape spike placeholder)
  let nodes = $state([]);
  let edges = $state([]);
  let loading = $state(false);
  let error = $state(null);
  let selectedNode = $state(null);
  let limit = $state(100);

  let nodesByType = $derived.by(() => {
    const groups = { case: [], debate: [], document: [], tag: [], user: [], audit: [], other: [] };
    for (const n of nodes) {
      const t = (n.type || 'other').toLowerCase();
      if (groups[t]) groups[t].push(n);
      else groups.other.push(n);
    }
    return groups;
  });

  onMount(() => {
    if (tenantId) load();
  });

  $effect(() => {
    if (tenantId) load();
  });

  async function load() {
    if (!tenantId) return;
    loading = true;
    error = null;
    try {
      const payload = await getGlobalGraph(tenantId, limit);
      nodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
      edges = Array.isArray(payload?.edges) ? payload.edges : [];
    } catch (err) {
      error = err;
      nodes = [];
      edges = [];
      addToast({
        type: 'error',
        message: t?.caseSpace?.graph?.globalLoadFailed ??
          'Could not load the global graph.',
      });
    } finally {
      loading = false;
    }
  }

  function openEntity(node) {
    if (!node) return;
    selectedNode = node;
    // The Cytoscape view is the eventual canonical drill-in;
    // for now we just hand the user off to the case workspace.
    if (node.type === 'case' && typeof navigate === 'function') {
      navigate('workspace');
    } else if (node.type === 'debate' && node.id && typeof navigate === 'function') {
      // Debate ids are ``debate:<id>`` per the GraphPayload contract.
      const debateId = String(node.id).split(':').slice(1).join(':');
      navigate('debate', { debateId });
    }
  }

  function closeDetail() {
    selectedNode = null;
  }

  const TYPE_LABELS = {
    case: 'Cases',
    debate: 'Debates',
    document: 'Documents',
    tag: 'Tags',
    user: 'Users',
    audit: 'Audit events',
    other: 'Other',
  };
</script>

<div class="max-w-6xl mx-auto p-6 text-gray-900 dark:text-gray-100">
  <header class="mb-4 flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold">
        {t?.caseSpace?.browse?.title ?? 'Browse'}
      </h1>
      <p class="text-sm text-gray-600 dark:text-gray-400">
        {t?.caseSpace?.browse?.subtitle ??
          'All cases, debates, documents and tags in this tenant.'}
      </p>
    </div>
    <div
      role="tablist"
      aria-label="Browse view"
      class="flex gap-1 p-1 rounded-md
             bg-gray-100 dark:bg-gray-800"
    >
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'list'}
        class="px-3 py-1 rounded text-sm font-medium
               {mode === 'list'
                 ? 'bg-blue-600 text-white'
                 : 'text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700'}"
        onclick={() => (mode = 'list')}
      >
        {t?.caseSpace?.browse?.listMode ?? 'List'}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'graph'}
        class="px-3 py-1 rounded text-sm font-medium
               {mode === 'graph'
                 ? 'bg-blue-600 text-white'
                 : 'text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700'}"
        onclick={() => (mode = 'graph')}
        data-testid="browse-tab-graph"
      >
        {t?.caseSpace?.browse?.graphMode ?? 'Graph'}
      </button>
    </div>
  </header>

  {#if loading}
    <p class="text-sm text-gray-500 dark:text-gray-400" role="status">
      {t?.common?.loading ?? 'Loading…'}
    </p>
  {:else if error}
    <p class="text-sm text-red-600 dark:text-red-400" role="alert">
      {error?.message ?? String(error)}
    </p>
  {:else if mode === 'graph'}
    <div
      class="border rounded-lg p-2
             border-gray-200 dark:border-gray-700
             bg-white dark:bg-gray-800"
    >
      {#await import('../components/case-space/CytoscapeGraphView.svelte') then Mod}
        <Mod.default nodes={nodes} edges={edges} height={520} />
      {/await}
    </div>
  {:else if nodes.length === 0}
    <p class="text-sm italic text-gray-500 dark:text-gray-400">
      {t?.caseSpace?.browse?.empty ?? 'Nothing to display yet.'}
    </p>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
      {#each Object.entries(nodesByType) as [type, list] (type)}
        {#if list.length > 0}
          <section
            class="p-3 border rounded-md
                   bg-white dark:bg-gray-800
                   border-gray-200 dark:border-gray-700"
            aria-labelledby={`browse-section-${type}`}
          >
            <h2
              id={`browse-section-${type}`}
              class="text-xs font-semibold uppercase tracking-wider mb-2
                     text-gray-500 dark:text-gray-400"
            >
              {TYPE_LABELS[type] ?? type} ({list.length})
            </h2>
            <ul class="space-y-1 list-none p-0" role="list">
              {#each list as n (n.id)}
                <li>
                  <button
                    type="button"
                    class="w-full text-left p-2 rounded text-sm
                           hover:bg-gray-100 dark:hover:bg-gray-700/50
                           focus:outline-none focus:ring-2 focus:ring-blue-500
                           text-gray-900 dark:text-gray-100"
                    data-testid={`browse-node-${type}`}
                    onclick={() => openEntity(n)}
                  >
                    {n.label ?? n.id}
                  </button>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<!-- Node-detail drawer -->
{#if selectedNode}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
    role="presentation"
    onclick={closeDetail}
    onkeydown={(e) => e.key === 'Escape' && closeDetail()}
  >
    <div
      class="w-full max-w-md p-5 border rounded-lg shadow-xl
             bg-white dark:bg-gray-800
             border-gray-200 dark:border-gray-700
             text-gray-900 dark:text-gray-100"
      role="dialog"
      aria-modal="true"
      aria-labelledby="browse-detail-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <h3 id="browse-detail-title" class="text-lg font-semibold mb-2">
        {selectedNode.label ?? selectedNode.id}
      </h3>
      <dl class="text-sm space-y-1">
        <div class="flex gap-2">
          <dt class="w-24 shrink-0 text-gray-500 dark:text-gray-400">Type</dt>
          <dd>{selectedNode.type}</dd>
        </div>
        <div class="flex gap-2">
          <dt class="w-24 shrink-0 text-gray-500 dark:text-gray-400">ID</dt>
          <dd class="font-mono text-xs break-all">{selectedNode.id}</dd>
        </div>
      </dl>
      <div class="flex justify-end gap-2 mt-4">
        <button
          type="button"
          class="px-3 py-1.5 rounded text-sm
                 bg-gray-100 dark:bg-gray-700
                 text-gray-700 dark:text-gray-200
                 hover:bg-gray-200 dark:hover:bg-gray-600
                 focus:outline-none focus:ring-2 focus:ring-blue-500"
          onclick={closeDetail}
        >
          {t?.common?.close ?? 'Close'}
        </button>
        {#if selectedNode.type === 'case' && typeof navigate === 'function'}
          <button
            type="button"
            class="px-3 py-1.5 rounded text-sm font-medium
                   bg-blue-600 hover:bg-blue-700 text-white
                   focus:outline-none focus:ring-2 focus:ring-blue-500"
            onclick={() => navigate('workspace')}
          >
            {t?.caseSpace?.browse?.openCase ?? 'Open case →'}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}
