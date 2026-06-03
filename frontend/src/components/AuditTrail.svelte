<script>
  import { tStore } from '../lib/i18n/index.js';

  export let events = [];
  export let sortColumn = 'timestamp';
  export let sortDirection = 'asc';
  export let expandedRow = null;
  export let onSort = (col) => {};
  export let onRowClick = (idx) => {};

  let t = $derived($tStore);

  function handleSort(col) {
    onSort(col);
  }

  function handleRowClick(idx) {
    onRowClick(idx);
  }
</script>

<div class="audit-trail">
  {#if events.length === 0}
    <div class="empty">
      <p>{t('audit.noEvents')}</p>
    </div>
  {:else}
    <table class="audit-table">
      <thead>
        <tr>
          <th click={() => handleSort('timestamp')} class:sort-asc={sortColumn === 'timestamp' && sortDirection === 'asc'} class:sort-desc={sortColumn === 'timestamp' && sortDirection === 'desc'}>
            {t('audit.columns.timestamp')}
          </th>
          <th click={() => handleSort('event_type')} class:sort-asc={sortColumn === 'event_type' && sortDirection === 'asc'} class:sort-desc={sortColumn === 'event_type' && sortDirection === 'desc'}>
            {t('audit.columns.eventType')}
          </th>
          <th click={() => handleSort('node_id')} class:sort-asc={sortColumn === 'node_id' && sortDirection === 'asc'} class:sort-desc={sortColumn === 'node_id' && sortDirection === 'desc'}>
            {t('audit.columns.nodeId')}
          </th>
          <th click={() => handleSort('actor')} class:sort-asc={sortColumn === 'actor' && sortDirection === 'asc'} class:sort-desc={sortColumn === 'actor' && sortDirection === 'desc'}>
            {t('audit.columns.actor')}
          </th>
          <th click={() => handleSort('latency_ms')} class:sort-asc={sortColumn === 'latency_ms' && sortDirection === 'asc'} class:sort-desc={sortColumn === 'latency_ms' && sortDirection === 'desc'}>
            {t('audit.columns.latency')}
          </th>
          <th click={() => handleSort('prompt_tokens')} class:sort-asc={sortColumn === 'prompt_tokens' && sortDirection === 'asc'} class:sort-desc={sortColumn === 'prompt_tokens' && sortDirection === 'desc'}>
            {t('audit.columns.promptTokens')}
          </th>
          <th click={() => handleSort('completion_tokens')} class:sort-asc={sortColumn === 'completion_tokens' && sortDirection === 'asc'} class:sort-desc={sortColumn === 'completion_tokens' && sortDirection === 'desc'}>
            {t('audit.columns.completionTokens')}
          </th>
          <th>{t('audit.columns.inputHash')}</th>
          <th>{t('audit.columns.outputHash')}</th>
        </tr>
      </thead>
      <tbody>
        {#each events as event, idx}
          <tr class:expanded={expandedRow === idx} click={() => handleRowClick(idx)}>
            <td>{event.timestamp ? new Date(event.timestamp).toLocaleString() : '—'}</td>
            <td><span class="badge event-type">{event.event_type || '—'}</span></td>
            <td>{event.node_id || '—'}</td>
            <td>{event.actor || '—'}</td>
            <td>{event.latency_ms || 0} ms</td>
            <td>{event.prompt_tokens || 0}</td>
            <td>{event.completion_tokens || 0}</td>
            <td class="hash" title={event.input_hash || ''}>{(event.input_hash || '—').slice(0, 12)}...</td>
            <td class="hash" title={event.output_hash || ''}>{(event.output_hash || '—').slice(0, 12)}...</td>
          </tr>
          {#if expandedRow === idx}
            <tr class="detail-row">
              <td colspan="9">
                <div class="detail-content">
                  <div><strong>Full Input Hash:</strong> <span class="hash">{event.input_hash || '—'}</span></div>
                  <div><strong>Full Output Hash:</strong> <span class="hash">{event.output_hash || '—'}</span></div>
                  {#if event.llm_profile_id}
                    <div><strong>LLM Profile:</strong> {event.llm_profile_id}</div>
                  {/if}
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .audit-trail {
    overflow-x: auto;
  }
  .empty {
    padding: 2rem;
    text-align: center;
    border: 2px dashed #ccc;
    border-radius: 8px;
    color: #999;
  }
  .audit-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  .audit-table th {
    text-align: left;
    padding: 0.4rem 0.5rem;
    background: #f0f0f0;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  .audit-table th:hover {
    background: #e0e0e0;
  }
  .audit-table th.sort-asc::after {
    content: ' ↑';
  }
  .audit-table th.sort-desc::after {
    content: ' ↓';
  }
  .audit-table td {
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #eee;
  }
  .audit-table tr:hover {
    background: #f8f9fa;
  }
  .audit-table tr.expanded {
    background: #e8f4fd;
  }
  .detail-row td {
    padding: 0.5rem;
    background: #f8f9fa;
  }
  .detail-content {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.75rem;
  }
  .hash {
    font-family: monospace;
    font-size: 0.7rem;
  }
  .badge {
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.7rem;
  }
  .event-type {
    background: #e8eaf6;
    color: #3f51b5;
  }
</style>
