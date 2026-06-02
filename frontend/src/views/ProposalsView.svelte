<!-- ProposalsView.svelte — Standalone page for optimization proposals.
     Shows all proposals across workflows for HITL review.
     Svelte 5 runes. -->
<script>
  import { tStore } from '../lib/i18n/index.js';

  let t = $derived($tStore);

  let proposals = $state([]);
  let loading = $state(false);
  let error = $state('');
  let refreshing = $state(false);

  async function loadProposals() {
    loading = true;
    error = '';
    try {
      const res = await fetch('/api/v1/optimization-proposals');
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

  async function handleRefresh() {
    refreshing = true;
    await loadProposals();
    refreshing = false;
  }

  // Load proposals on mount
  $effect(() => {
    loadProposals();
  });

  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }
</script>

<div class="proposals-view">
  <div class="proposals-header">
    <div class="header-left">
      <h1>🔍 {t('nav.proposals')}</h1>
      <p class="subtitle">{t('proposals.description') || 'Review and approve AI-generated optimization proposals'}</p>
    </div>
    <button class="refresh-btn" onclick={handleRefresh} disabled={refreshing}>
      {refreshing ? '⟳ ' + (t('common.loading') || 'Loading...') : '⟳ ' + (t('proposals.refresh') || 'Refresh')}
    </button>
  </div>

  {#if loading}
    <div class="proposals-loading">
      <div class="spinner"></div>
      <p>{t('common.loading') || 'Loading proposals...'}</p>
    </div>
  {:else if error}
    <div class="proposals-error">
      <p>⚠️ {error}</p>
      <button onclick={loadProposals}>{t('common.retry') || 'Retry'}</button>
    </div>
  {:else if proposals.length === 0}
    <div class="proposals-empty">
      <div class="empty-icon">🔍</div>
      <h3>{t('proposals.noProposals') || 'No proposals yet'}</h3>
      <p>{t('proposals.emptyHint') || 'Optimization proposals will appear here after running debates with reflection enabled.'}</p>
    </div>
  {:else}
    <div class="proposals-stats">
      <div class="stat stat-pending">
        <span class="stat-value">{proposals.filter(p => p.status === 'pending').length}</span>
        <span class="stat-label">{t('proposals.pending') || 'Pending'}</span>
      </div>
      <div class="stat stat-approved">
        <span class="stat-value">{proposals.filter(p => p.status === 'approved').length}</span>
        <span class="stat-label">{t('proposals.approved') || 'Approved'}</span>
      </div>
      <div class="stat stat-rejected">
        <span class="stat-value">{proposals.filter(p => p.status === 'rejected').length}</span>
        <span class="stat-label">{t('proposals.rejected') || 'Rejected'}</span>
      </div>
    </div>

    <div class="proposals-list">
      {#each proposals as proposal}
        <div class="proposal-card" class:pending={proposal.status === 'pending'} class:approved={proposal.status === 'approved'} class:rejected={proposal.status === 'rejected'}>
          <div class="proposal-header">
            <div class="proposal-meta">
              <span class="proposal-id">#{proposal.id}</span>
              {#if proposal.workflow_id}
                <span class="proposal-workflow">Workflow: {proposal.workflow_id}</span>
              {/if}
              {#if proposal.created_at}
                <span class="proposal-date">{formatDate(proposal.created_at)}</span>
              {/if}
            </div>
            <span class="proposal-status status-{proposal.status}">
              {proposal.status === 'pending' ? (t('proposals.pending') || 'Pending') :
               proposal.status === 'approved' ? (t('proposals.approved') || 'Approved') :
               (t('proposals.rejected') || 'Rejected')}
            </span>
          </div>

          {#if proposal.title}
            <h3 class="proposal-title">{proposal.title}</h3>
          {/if}

          {#if proposal.rationale}
            <div class="proposal-section">
              <strong>{t('proposals.rationale') || 'Rationale'}</strong>
              <p class="proposal-rationale">{proposal.rationale}</p>
            </div>
          {/if}

          {#if proposal.risk_assessment}
            <div class="proposal-section">
              <strong>{t('proposals.risk') || 'Risk Assessment'}</strong>
              <p class="proposal-risk">{proposal.risk_assessment}</p>
            </div>
          {/if}

          {#if proposal.estimated_impact}
            <div class="proposal-section">
              <strong>{t('proposals.impact') || 'Estimated Impact'}</strong>
              <p class="proposal-impact">{proposal.estimated_impact}</p>
            </div>
          {/if}

          {#if proposal.status === 'pending'}
            <div class="proposal-actions">
              <button class="btn-approve" onclick={() => handleApprove(proposal.id)}>
                ✓ {t('proposals.approve') || 'Approve'}
              </button>
              <button class="btn-reject" onclick={() => handleReject(proposal.id)}>
                ✗ {t('proposals.reject') || 'Reject'}
              </button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .proposals-view {
    max-width: 900px;
    margin: 0 auto;
    padding: 24px;
  }

  .proposals-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e5e7eb;
  }

  :global(.dark) .proposals-header {
    border-bottom-color: #374151;
  }

  .header-left h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: #111827;
  }

  :global(.dark) .header-left h1 {
    color: #f9fafb;
  }

  .subtitle {
    margin: 4px 0 0;
    font-size: 14px;
    color: #6b7280;
  }

  :global(.dark) .subtitle {
    color: #9ca3af;
  }

  .refresh-btn {
    padding: 8px 16px;
    border-radius: 8px;
    border: 1px solid #d1d5db;
    background: white;
    color: #374151;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s;
  }

  :global(.dark) .refresh-btn {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  .refresh-btn:hover:not(:disabled) {
    background: #f3f4f6;
    border-color: #9ca3af;
  }

  :global(.dark) .refresh-btn:hover:not(:disabled) {
    background: #4b5563;
  }

  .refresh-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .proposals-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px;
    color: #6b7280;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #e5e7eb;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 12px;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .proposals-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 32px;
    color: #dc2626;
    text-align: center;
  }

  .proposals-error button {
    margin-top: 12px;
    padding: 8px 16px;
    border-radius: 6px;
    border: 1px solid #dc2626;
    background: #fee2e2;
    color: #991b1b;
    cursor: pointer;
  }

  .proposals-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 24px;
    text-align: center;
    color: #6b7280;
  }

  .empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }

  .proposals-empty h3 {
    margin: 0 0 8px;
    font-size: 18px;
    color: #374151;
  }

  :global(.dark) .proposals-empty h3 {
    color: #e5e7eb;
  }

  .proposals-stats {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
  }

  .stat {
    flex: 1;
    padding: 16px;
    border-radius: 12px;
    text-align: center;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
  }

  :global(.dark) .stat {
    background: #1f2937;
    border-color: #374151;
  }

  .stat-value {
    display: block;
    font-size: 28px;
    font-weight: 700;
  }

  .stat-label {
    display: block;
    font-size: 12px;
    color: #6b7280;
    margin-top: 4px;
  }

  .stat-pending .stat-value {
    color: #ca8a04;
  }

  .stat-approved .stat-value {
    color: #16a34a;
  }

  .stat-rejected .stat-value {
    color: #dc2626;
  }

  .proposals-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .proposal-card {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    background: white;
  }

  :global(.dark) .proposal-card {
    background: #1f2937;
    border-color: #374151;
  }

  .proposal-card.pending {
    border-color: #fde047;
    background: #fefce8;
  }

  :global(.dark) .proposal-card.pending {
    background: #422006;
    border-color: #854d0e;
  }

  .proposal-card.approved {
    border-color: #86efac;
    background: #f0fdf4;
  }

  :global(.dark) .proposal-card.approved {
    background: #052e16;
    border-color: #166534;
  }

  .proposal-card.rejected {
    border-color: #fca5a5;
    background: #fef2f2;
    opacity: 0.8;
  }

  :global(.dark) .proposal-card.rejected {
    background: #450a0a;
    border-color: #991b1b;
  }

  .proposal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  .proposal-meta {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }

  .proposal-id {
    font-family: monospace;
    font-size: 12px;
    color: #6b7280;
    background: #f3f4f6;
    padding: 2px 8px;
    border-radius: 4px;
  }

  :global(.dark) .proposal-id {
    background: #374151;
    color: #9ca3af;
  }

  .proposal-workflow, .proposal-date {
    font-size: 12px;
    color: #6b7280;
  }

  :global(.dark) .proposal-workflow, :global(.dark) .proposal-date {
    color: #9ca3af;
  }

  .proposal-status {
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 16px;
    font-weight: 600;
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

  .proposal-title {
    margin: 0 0 12px;
    font-size: 16px;
    font-weight: 600;
    color: #111827;
  }

  :global(.dark) .proposal-title {
    color: #f9fafb;
  }

  .proposal-section {
    margin: 8px 0;
  }

  .proposal-section strong {
    display: block;
    font-size: 12px;
    color: #4b5563;
    margin-bottom: 4px;
  }

  :global(.dark) .proposal-section strong {
    color: #9ca3af;
  }

  .proposal-rationale, .proposal-risk, .proposal-impact {
    margin: 0;
    font-size: 14px;
    line-height: 1.6;
    color: #374151;
  }

  :global(.dark) .proposal-rationale, :global(.dark) .proposal-risk, :global(.dark) .proposal-impact {
    color: #e5e7eb;
  }

  .proposal-actions {
    display: flex;
    gap: 12px;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #e5e7eb;
  }

  :global(.dark) .proposal-actions {
    border-top-color: #374151;
  }

  .btn-approve, .btn-reject {
    padding: 8px 20px;
    border-radius: 8px;
    border: 1px solid;
    font-size: 14px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.15s;
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
