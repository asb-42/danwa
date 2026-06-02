<script>
  import { onMount } from 'svelte';
  import { tStore } from '../../lib/i18n/index.js';
  import { getAuditLog } from '../../lib/workflow/auditApi.js';
  import AuditTrail from '../AuditTrail.svelte';

  export let sessionId = '';

  let auditEntries = [];
  let loading = false;
  let error = null;
  let eventTypeFilter = '';
  let searchQuery = '';
  let pageSize = 25;
  let currentPage = 0;
  let expandedRow = null;
  let sortColumn = 'timestamp';
  let sortDirection = 'asc';

  let t = $derived($tStore);

  $: totalEvents = auditEntries.length;
  $: totalTokens = auditEntries.reduce((sum, e) => sum + (e.prompt_tokens || 0) + (e.completion_tokens || 0), 0);
  $: totalLatency = auditEntries.reduce((sum, e) => sum + (e.latency_ms || 0), 0);
  $: eventTypeCounts = auditEntries.reduce((acc, e) => {
    const t = e.event_type || 'unknown';
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {});

  $: filteredEntries = auditEntries
    .filter(e => !eventTypeFilter || e.event_type === eventTypeFilter)
    .filter(e => !searchQuery ||
      (e.actor || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (e.node_id || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

  $: sortedEntries = [...filteredEntries].sort((a, b) => {
    const aVal = a[sortColumn] || '';
    const bVal = b[sortColumn] || '';
    const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortDirection === 'asc' ? cmp : -cmp;
  });

  $: paginatedEntries = sortedEntries.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize
  );

  $: totalPages = Math.ceil(sortedEntries.length / pageSize);

  onMount(async () => {
    if (sessionId) {
      await loadAuditLog();
    }
  });

  async function loadAuditLog() {
    loading = true;
    error = null;
    try {
      auditEntries = await getAuditLog(sessionId, { limit: 1000 });
    } catch (e) {
      error = e.message;
    }
    loading = false;
  }

  function toggleSort(column) {
    if (sortColumn === column) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = column;
      sortDirection = 'asc';
    }
  }

  function toggleRow(idx) {
    expandedRow = expandedRow === idx ? null : idx;
  }

  function exportCSV() {
    const headers = ['Timestamp', 'Event Type', 'Node ID', 'Actor', 'Latency (ms)', 'Prompt Tokens', 'Completion Tokens', 'Input Hash', 'Output Hash'];
    const rows = sortedEntries.map(e => [
      e.timestamp || '',
      e.event_type || '',
      e.node_id || '',
      e.actor || '',
      e.latency_ms || 0,
      e.prompt_tokens || 0,
      e.completion_tokens || 0,
      e.input_hash || '',
      e.output_hash || '',
    ]);
    const csv = [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_${sessionId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  $: eventTypes = [...new Set(auditEntries.map(e => e.event_type).filter(Boolean))];
</script>

<div class="session-audit-tab">
  <!-- Summary stats -->
  <div class="summary">
    <div class="stat">
      <span class="stat-value">{totalEvents}</span>
      <span class="stat-label">{t('audit.summary.totalEvents')}</span>
    </div>
    <div class="stat">
      <span class="stat-value">{totalTokens}</span>
      <span class="stat-label">{t('audit.summary.totalTokens')}</span>
    </div>
    <div class="stat">
      <span class="stat-value">{totalLatency} ms</span>
      <span class="stat-label">{t('audit.summary.totalLatency')}</span>
    </div>
    {#each Object.entries(eventTypeCounts) as [type, count]}
      <div class="stat">
        <span class="stat-value">{count}</span>
        <span class="stat-label">{type}</span>
      </div>
    {/each}
  </div>

  <!-- Filters -->
  <div class="filters">
    <select bind:value={eventTypeFilter}>
      <option value="">{t('audit.filter.eventType')}</option>
      {#each eventTypes as type}
        <option value={type}>{type}</option>
      {/each}
    </select>
    <input
      type="text"
      placeholder={t('audit.filter.search')}
      bind:value={searchQuery}
    />
    <select bind:value={pageSize}>
      <option value="25">25 / page</option>
      <option value="50">50 / page</option>
      <option value="100">100 / page</option>
    </select>
    <button class="btn-export" on:click={exportCSV}>
      {t('audit.export.csv')}
    </button>
  </div>

  {#if loading}
    <p>Loading...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else}
    <!-- Audit table -->
    <AuditTrail
      events={paginatedEntries}
      {sortColumn}
      {sortDirection}
      {expandedRow}
      onSort={toggleSort}
      onRowClick={toggleRow}
    />

    <!-- Pagination -->
    {#if totalPages > 1}
      <div class="pagination">
        <button disabled={currentPage === 0} on:click={() => currentPage--}>←</button>
        <span>{currentPage + 1} / {totalPages}</span>
        <button disabled={currentPage >= totalPages - 1} on:click={() => currentPage++}>→</button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .session-audit-tab {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .summary {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.5rem 1rem;
    background: #f8f9fa;
    border-radius: 4px;
  }
  .stat-value {
    font-size: 1.2rem;
    font-weight: bold;
  }
  .stat-label {
    font-size: 0.75rem;
    color: #666;
  }
  .filters {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .filters select, .filters input {
    padding: 0.3rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  .btn-export {
    margin-left: auto;
    padding: 0.3rem 0.75rem;
    background: #28a745;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
  }
  .error {
    color: #c00;
  }
</style>
