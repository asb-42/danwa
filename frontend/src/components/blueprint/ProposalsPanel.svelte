<!-- ProposalsPanel.svelte — Displays optimization proposals for a workflow.
     Shown after clicking the Reflect button in the canvas toolbar.
     Svelte 5 runes. -->
<script>
  import { tStore } from '../../lib/i18n/index.js';

  let { workflowId = '', visible = false, onclose = () => {} } = $props();

  let t = $derived($tStore);

  let proposals = $state([]);
  let loading = $state(false);
  let error = $state('');

  async function loadProposals() {
    if (!workflowId) return;
    loading = true;
    error = '';
    try {
      const res = await fetch(`/api/v1/optimization-proposals?workflow_id=${workflowId}`);
      if (!res.ok) {
        error = `HTTP ${res.status}`;
        return;
      }
      proposals = await res.json();
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  async function handleApprove(proposalId) {
    try {
      const res = await fetch(`/api/v1/optimization-proposals/${proposalId}/approve`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        error = body.detail || `Approve failed: HTTP ${res.status}`;
        return;
      }
      await loadProposals();
    } catch (err) {
      error = err.message;
    }
  }

  async function handleReject(proposalId) {
    try {
      const res = await fetch(`/api/v1/optimization-proposals/${proposalId}/reject`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        error = body.detail || `Reject failed: HTTP ${res.status}`;
        return;
      }
      await loadProposals();
    } catch (err) {
      error = err.message;
    }
  }

  // Load proposals when panel becomes visible
  $effect(() => {
    if (visible && workflowId) {
      loadProposals();
    }
  });
</script>

{#if visible}
  <div class="proposals-panel" role="dialog" aria-label="Optimization Proposals">
    <div class="proposals-header">
      <h3>🔍 {t('workflow.reflect.proposals') || 'Optimization Proposals'}</h3>
      <button class="close-btn" onclick={onclose} title="Close">✕</button>
    </div>

    {#if loading}
      <div class="proposals-loading">Loading proposals...</div>
    {:else if error}
      <div class="proposals-error">⚠️ {error}</div>
    {:else if proposals.length === 0}
      <div class="proposals-empty">
        <p>No proposals generated yet.</p>
        <p class="text-xs text-gray-400">Click "Reflect" to generate optimization proposals for this workflow.</p>
      </div>
    {:else}
      <div class="proposals-list">
        {#each proposals as proposal}
          <div class="proposal-card" class:pending={proposal.status === 'pending'} class:approved={proposal.status === 'approved'} class:rejected={proposal.status === 'rejected'}>
            <div class="proposal-header">
              <span class="proposal-id">#{proposal.id}</span>
              <span class="proposal-status status-{proposal.status}">{proposal.status}</span>
            </div>
            {#if proposal.rationale}
              <p class="proposal-rationale">{proposal.rationale}</p>
            {/if}
            {#if proposal.risk_assessment}
              <p class="proposal-risk">
                <strong>Risk:</strong> {proposal.risk_assessment}
              </p>
            {/if}
            {#if proposal.estimated_impact}
              <p class="proposal-impact">
                <strong>Impact:</strong> {proposal.estimated_impact}
              </p>
            {/if}
            {#if proposal.status === 'pending'}
              <div class="proposal-actions">
                <button class="btn-approve" onclick={() => handleApprove(proposal.id)}>✓ Approve</button>
                <button class="btn-reject" onclick={() => handleReject(proposal.id)}>✗ Reject</button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .proposals-panel {
    position: absolute;
    top: 48px;
    right: 8px;
    width: 380px;
    max-height: 70vh;
    overflow-y: auto;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    z-index: 20;
    font-size: 13px;
  }
  :global(.dark) .proposals-panel {
    background: #1f2937;
    border-color: #374151;
  }
  .proposals-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
  }
  .proposals-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }
  .close-btn {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 16px;
    color: #6b7280;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .close-btn:hover {
    background: #f3f4f6;
  }
  .proposals-loading, .proposals-empty, .proposals-error {
    padding: 24px 16px;
    text-align: center;
    color: #6b7280;
  }
  .proposals-error {
    color: #dc2626;
  }
  .proposals-list {
    padding: 8px;
  }
  .proposal-card {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
  }
  .proposal-card.pending {
    border-color: #fde047;
    background: #fefce8;
  }
  .proposal-card.approved {
    border-color: #86efac;
    background: #f0fdf4;
  }
  .proposal-card.rejected {
    border-color: #fca5a5;
    background: #fef2f2;
    opacity: 0.7;
  }
  .proposal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .proposal-id {
    font-family: monospace;
    font-size: 11px;
    color: #6b7280;
  }
  .proposal-status {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 500;
  }
  .status-pending {
    background: #fef9c3;
    color: #854d0e;
  }
  .status-approved {
    background: #dcfce7;
    color: #166534;
  }
  .status-rejected {
    background: #fee2e2;
    color: #991b1b;
  }
  .proposal-rationale, .proposal-risk, .proposal-impact {
    margin: 4px 0;
    font-size: 12px;
    line-height: 1.5;
  }
  .proposal-actions {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }
  .btn-approve, .btn-reject {
    padding: 4px 12px;
    border-radius: 6px;
    border: 1px solid;
    font-size: 12px;
    cursor: pointer;
    font-weight: 500;
  }
  .btn-approve {
    background: #dcfce7;
    border-color: #86efac;
    color: #166534;
  }
  .btn-approve:hover {
    background: #bbf7d0;
  }
  .btn-reject {
    background: #fee2e2;
    border-color: #fca5a5;
    color: #991b1b;
  }
  .btn-reject:hover {
    background: #fecaca;
  }
</style>
