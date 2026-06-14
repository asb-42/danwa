<!--
  InspectorGraphTab — Phase 5.4 / Phase 4 low-risk spike.

  The plan calls for a Cytoscape-powered graph visualisation
  (Konzept §A.5–A.6).  Adding Cytoscape.js bumps the vendor
  bundle by ~1.4 MB raw / ~440 kB gzipped — not a decision
  worth making without a proper spike.

  This component therefore ships a *list-graph* mode that
  consumes the same backend endpoints the Cytoscape view
  would (``/api/v1/graph/local`` and ``/api/v1/graph/edges``)
  and renders the 1-hop subgraph as a connected list of
  cards: center entity at the top, every neighbour as a
  clickable row that drills into the edge detail.  This
  delivers the inspector-graph user value (Phase 5.4) and
  the list-graph browse mode (Phase 4.9) without any
  extra runtime dependency.

  Cytoscape can be swapped in later by replacing the body of
  ``<GraphList>`` with a Cytoscape mount.  The data-flow
  contract (GraphPayload, EdgeDetail) is identical.

  @see plans/2026-06-14_case-space-workspace.md (Phase 4 & 5.4)
-->
<script>
  import { onMount } from 'svelte';
  import { tStore } from '../../lib/i18n/index.js';
  import { currentTenant } from '../../lib/stores/auth.svelte.js';
  import { addToast } from '../../lib/stores.js';
  import {
    getLocalGraph,
    getEdgeDetails,
  } from '../../lib/api/graph.js';

  let { entityType = 'case', entityId, hops = 1 } = $props();

  let t = $derived($tStore);
  let tenantId = $derived($currentTenant?.id);

  let nodes = $state([]);
  let edges = $state([]);
  let centerId = $derived(
    entityType && entityId ? `${entityType}:${entityId}` : null
  );
  let loading = $state(false);
  let error = $state(null);
  let selectedEdge = $state(null);
  let edgeDetail = $state(null);
  let edgeDetailLoading = $state(false);

  // Refs:  computed display values
  let centerNode = $derived(nodes.find((n) => n.id === centerId) || null);
  let neighbours = $derived(
    edges
      .filter((e) => e.src === centerId || e.tgt === centerId)
      .map((e) => {
        const otherId = e.src === centerId ? e.tgt : e.src;
        const other = nodes.find((n) => n.id === otherId);
        return { edge: e, node: other };
      })
  );
  let truncated = $state(false);
  let graphDisabled = $state(false);

  onMount(() => {
    if (entityId) load();
  });

  $effect(() => {
    if (entityId) load();
  });

  async function load() {
    if (!entityId) return;
    loading = true;
    error = null;
    graphDisabled = false;
    try {
      const payload = await getLocalGraph(entityType, entityId, hops);
      nodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
      edges = Array.isArray(payload?.edges) ? payload.edges : [];
      truncated = Boolean(payload?.truncated);
    } catch (err) {
      // Phase 5.4: the graph is feature-gated behind
      // enable_case_space_graph (default False until Phase 4
      // lands).  Rather than yelling at the user with a red
      // toast every time they open the Graph tab, we detect the
      // 404 / flag-off and render a friendly hint instead.
      if (/DANWA_ENABLE_CASE_SPACE_GRAPH/.test(String(err?.message ?? err))) {
        graphDisabled = true;
      } else {
        error = err;
        addToast({
          type: 'error',
          message: t?.caseSpace?.graph?.loadFailed ??
            'Could not load the graph for this entity.',
        });
      }
      nodes = [];
      edges = [];
    } finally {
      loading = false;
    }
  }

  async function showEdgeDetail(edge) {
    selectedEdge = edge;
    edgeDetail = null;
    edgeDetailLoading = true;
    try {
      // Edge payload: ``{src, tgt, type, weight, evidence, created_at}``
      // Pull more details if the backend stub is enabled.
      const detail = await getEdgeDetails(edge.src, edge.tgt);
      edgeDetail = detail;
    } catch {
      // The stub returns 501 on real backends; fall back to the
      // edge summary we already have.
      edgeDetail = { ...edge, note: t?.caseSpace?.graph?.stubNote ??
        'Detailed edge evidence is not available in this build yet.' };
    } finally {
      edgeDetailLoading = false;
    }
  }

  function closeEdgeDetail() {
    selectedEdge = null;
    edgeDetail = null;
  }
</script>

<div
  class="p-4 border rounded-lg
         bg-white dark:bg-gray-800
         border-gray-200 dark:border-gray-700
         text-gray-900 dark:text-gray-100"
  data-testid="inspector-graph-tab"
>
  <div class="flex items-center justify-between mb-3">
    <h3 class="text-sm font-semibold">
      {t?.caseSpace?.graph?.title ?? '1-hop subgraph'}
    </h3>
    <button
      type="button"
      class="text-xs px-2 py-1 rounded
             bg-gray-100 dark:bg-gray-700
             text-gray-700 dark:text-gray-200
             hover:bg-gray-200 dark:hover:bg-gray-600
             focus:outline-none focus:ring-2 focus:ring-blue-500"
      data-testid="refresh-graph"
      onclick={load}
      disabled={loading}
    >
      {loading ? '…' : (t?.common?.refresh ?? 'Refresh')}
    </button>
  </div>

  {#if graphDisabled}
    <p
      class="text-sm italic
             text-gray-500 dark:text-gray-400"
      data-testid="graph-disabled"
    >
      {t?.caseSpace?.graph?.disabledHint ??
        'The knowledge graph is not enabled on the backend yet. Set DANWA_ENABLE_CASE_SPACE_GRAPH=true to try it.'}
    </p>
  {:else if !entityId}
    <p class="text-sm italic text-gray-500 dark:text-gray-400">
      {t?.caseSpace?.graph?.noEntity ?? 'No entity selected.'}
    </p>
  {:else if loading && nodes.length === 0}
    <p class="text-sm text-gray-500 dark:text-gray-400" role="status">
      {t?.common?.loading ?? 'Loading…'}
    </p>
  {:else if nodes.length === 0}
    <p class="text-sm italic text-gray-500 dark:text-gray-400">
      {t?.caseSpace?.graph?.empty ?? 'No related entities yet.'}
    </p>
  {:else}
    <!-- Center entity -->
    <div
      class="p-3 mb-3 border-2 border-blue-400 dark:border-blue-500 rounded
             bg-blue-50 dark:bg-blue-900/30"
      data-testid="graph-center"
    >
      <div class="text-[0.7rem] uppercase tracking-wider
                  text-blue-700 dark:text-blue-300 font-semibold">
        {t?.caseSpace?.graph?.center ?? 'Center'}
      </div>
      <div class="font-medium">
        {centerNode?.label || `${entityType}:${entityId}`}
      </div>
      <div class="text-xs text-blue-600 dark:text-blue-400">
        {centerNode?.type || entityType}
      </div>
    </div>

    {#if truncated}
      <p
        class="text-xs italic mb-2 px-3 py-1 rounded
               bg-amber-50 dark:bg-amber-900/20
               text-amber-800 dark:text-amber-200"
        data-testid="graph-truncated"
      >
        {t?.caseSpace?.graph?.truncated ??
          'Result was truncated. Try a smaller hop count.'}
      </p>
    {/if}

    <!-- Neighbouring entities -->
    <ul class="space-y-1 list-none p-0" role="list">
      {#each neighbours as { edge, node } (edge.src + '|' + edge.tgt + '|' + edge.type)}
        <li>
          <button
            type="button"
            class="w-full flex items-center gap-2 p-2 border rounded text-left
                   border-gray-200 dark:border-gray-700
                   bg-white dark:bg-gray-700/40
                   hover:border-blue-400 dark:hover:border-blue-500
                   text-gray-900 dark:text-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="graph-edge"
            onclick={() => showEdgeDetail(edge)}
          >
            <span
              class="text-[0.65rem] font-mono px-1.5 py-0.5 rounded
                     bg-gray-100 dark:bg-gray-600
                     text-gray-700 dark:text-gray-200"
            >
              {edge.type || 'related'}
            </span>
            <span class="flex-1 truncate text-sm">
              {node?.label ?? '?'}
            </span>
            <span class="text-[0.7rem] text-gray-500 dark:text-gray-400">
              {node?.type ?? ''}
            </span>
          </button>
        </li>
      {/each}
      {#if neighbours.length === 0}
        <li class="text-sm italic px-2 py-1 text-gray-500 dark:text-gray-400">
          {t?.caseSpace?.graph?.noNeighbours ?? 'No direct neighbours.'}
        </li>
      {/if}
    </ul>
  {/if}
</div>

<!-- Edge-detail dialog -->
{#if selectedEdge}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4
           bg-black/50"
    role="presentation"
    onclick={closeEdgeDetail}
    onkeydown={(e) => e.key === 'Escape' && closeEdgeDetail()}
  >
    <div
      class="w-full max-w-md p-5 border rounded-lg shadow-xl
             bg-white dark:bg-gray-800
             border-gray-200 dark:border-gray-700
             text-gray-900 dark:text-gray-100"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edge-detail-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <h3 id="edge-detail-title" class="text-lg font-semibold mb-2">
        {t?.caseSpace?.graph?.edgeTitle ?? 'Edge detail'}
      </h3>
      {#if edgeDetailLoading}
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {t?.common?.loading ?? 'Loading…'}
        </p>
      {:else if edgeDetail}
        <dl class="text-sm space-y-1">
          <div class="flex gap-2">
            <dt class="text-gray-500 dark:text-gray-400 w-24 shrink-0">
              {t?.caseSpace?.graph?.kind ?? 'Kind'}
            </dt>
            <dd class="font-mono">{edgeDetail.type ?? selectedEdge.type}</dd>
          </div>
          <div class="flex gap-2">
            <dt class="text-gray-500 dark:text-gray-400 w-24 shrink-0">
              {t?.caseSpace?.graph?.weight ?? 'Weight'}
            </dt>
            <dd>{edgeDetail.weight ?? '—'}</dd>
          </div>
          {#if edgeDetail.created_at}
            <div class="flex gap-2">
              <dt class="text-gray-500 dark:text-gray-400 w-24 shrink-0">
                {t?.caseSpace?.graph?.createdAt ?? 'Created'}
              </dt>
              <dd class="font-mono text-xs">{edgeDetail.created_at}</dd>
            </div>
          {/if}
          {#if edgeDetail.evidence?.length}
            <div class="mt-2">
              <dt class="text-gray-500 dark:text-gray-400 mb-1">
                {t?.caseSpace?.graph?.evidence ?? 'Evidence'}
              </dt>
              <dd>
                <ul class="space-y-1 list-disc list-inside text-xs">
                  {#each edgeDetail.evidence as ev}
                    <li>{ev}</li>
                  {/each}
                </ul>
              </dd>
            </div>
          {/if}
          {#if edgeDetail.note}
            <p class="text-xs italic mt-2 text-gray-500 dark:text-gray-400">
              {edgeDetail.note}
            </p>
          {/if}
        </dl>
      {/if}
      <div class="flex justify-end mt-4">
        <button
          type="button"
          class="px-3 py-1.5 rounded text-sm
                 bg-gray-100 dark:bg-gray-700
                 text-gray-700 dark:text-gray-200
                 hover:bg-gray-200 dark:hover:bg-gray-600
                 focus:outline-none focus:ring-2 focus:ring-blue-500"
          onclick={closeEdgeDetail}
        >
          {t?.common?.close ?? 'Close'}
        </button>
      </div>
    </div>
  </div>
{/if}
