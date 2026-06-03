<script>
  import { onMount } from 'svelte';
  import { routeParams } from '../lib/stores.js';
  import { tStore } from '../lib/i18n/index.js';
  import { getWorkflowSessions } from '../lib/workflow/auditApi.js';
  import DiffNodeDetail from '../components/workflow/DiffNodeDetail.svelte';

  let sessions = $state([]);
  let sessionA = $state($routeParams[0] || '');
  let sessionB = $state($routeParams[1] || '');
  let auditLogA = $state([]);
  let auditLogB = $state([]);
  let loading = $state(false);
  let error = $state(null);
  let selectedNodeId = $state(null);

  let t = $derived($tStore);

  onMount(async () => {
    try {
      sessions = await getWorkflowSessions(null, { status: 'completed', limit: 50 });
    } catch (e) {
      error = e.message;
    }
    if (sessionA && sessionB) {
      await loadDiff();
    }
  });

  async function loadDiff() {
    loading = true;
    error = null;
    try {
      const { getAuditLog } = await import('../lib/workflow/auditApi.js');
      auditLogA = await getAuditLog(sessionA, { limit: 1000 });
      auditLogB = await getAuditLog(sessionB, { limit: 1000 });
    } catch (e) {
      error = e.message;
    }
    loading = false;
  }

  function onSessionAChange(e) {
    sessionA = e.target.value;
    if (sessionA && sessionB) loadDiff();
  }

  function onSessionBChange(e) {
    sessionB = e.target.value;
    if (sessionA && sessionB) loadDiff();
  }

  function onNodeClick(nodeId) {
    selectedNodeId = nodeId;
  }

  let diffPairs = $derived.by(() => {
    const mapA = new Map(auditLogA.filter(e => e.node_id).map(e => [e.node_id, e]));
    const mapB = new Map(auditLogB.filter(e => e.node_id).map(e => [e.node_id, e]));
    const allNodeIds = new Set([...mapA.keys(), ...mapB.keys()]);
    return [...allNodeIds].map(nodeId => ({
      nodeId,
      entryA: mapA.get(nodeId) || null,
      entryB: mapB.get(nodeId) || null,
    }));
  });
</script>

<div class="diff-view">
  <h2>{t('diff.title')}</h2>

  <div class="session-selectors">
    <div class="selector">
      <label for="diff-session-a">{t('diff.selectSessionA')}</label>
      <select id="diff-session-a" value={sessionA} onchange={onSessionAChange}>
        <option value="">--</option>
        {#each sessions as s}
          <option value={s.id}>{s.id}</option>
        {/each}
      </select>
    </div>
    <div class="selector">
      <label for="diff-session-b">{t('diff.selectSessionB')}</label>
      <select id="diff-session-b" value={sessionB} onchange={onSessionBChange}>
        <option value="">--</option>
        {#each sessions as s}
          <option value={s.id}>{s.id}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if loading}
    <p>Loading...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if diffPairs.length > 0}
    <div class="diff-summary">
      {#if diffPairs.every(p => p.entryA && p.entryB && p.entryA.output_hash === p.entryB.output_hash)}
        <p class="no-diff">{t('diff.noDifferences')}</p>
      {:else}
        <p class="diff-found">{t('diff.differencesFound')}</p>
      {/if}
    </div>

    <div class="diff-list">
      {#each diffPairs as pair}
        <div
          class="diff-item"
          class:selected={selectedNodeId === pair.nodeId}
          role="button"
          tabindex="0"
          onclick={() => onNodeClick(pair.nodeId)}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onNodeClick(pair.nodeId); } }}
        >
          <span class="node-id">{pair.nodeId}</span>
          {#if pair.entryA && pair.entryB}
            {#if pair.entryA.output_hash === pair.entryB.output_hash}
              <span class="badge match">✓</span>
            {:else}
              <span class="badge diff">≠</span>
            {/if}
          {:else}
            <span class="badge missing">!</span>
          {/if}
        </div>
      {/each}
    </div>

    {#if selectedNodeId}
      {@const pair = diffPairs.find(p => p.nodeId === selectedNodeId)}
      {#if pair}
        <DiffNodeDetail entryA={pair.entryA} entryB={pair.entryB} nodeId={selectedNodeId} />
      {/if}
    {/if}
  {:else if sessionA && sessionB}
    <p>No data.</p>
  {/if}
</div>

<style>
  .diff-view {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .session-selectors {
    display: flex;
    gap: 2rem;
  }
  .selector {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .selector select {
    min-width: 250px;
    padding: 0.4rem;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  .diff-summary {
    padding: 0.5rem;
    border-radius: 4px;
  }
  .no-diff {
    color: green;
  }
  .diff-found {
    color: #e67e22;
  }
  .diff-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 0.5rem;
  }
  .diff-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.5rem;
    border-radius: 4px;
    cursor: pointer;
  }
  .diff-item:hover, .diff-item.selected {
    background: #f0f0f0;
  }
  .node-id {
    font-family: monospace;
    font-size: 0.85rem;
  }
  .badge {
    font-size: 0.75rem;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }
  .badge.match { background: #d4edda; color: #155724; }
  .badge.diff { background: #fff3cd; color: #856404; }
  .badge.missing { background: #f8d7da; color: #721c24; }
  .error { color: #c00; }
</style>
