<script>
  /**
   * TransactionalNodePanel — Extra inspector panel for Transactional Drafting nodes.
   *
   * Shows role-specific metadata below the WorkflowNodeForm:
   * - Critic (wf-critic): Structured Output badge + CriticItem schema preview
   * - Builder (wf-builder): Constructivity Score indicator with threshold bar
   * - Pragmatist (wf-pragmatist): reality_score threshold display + blocking_concerns warning
   * - Angel's Advocate (wf-angels-advocate): PreservedElement info
   */
  import { i18n } from '../../../lib/i18n/index.js';

  /** @type {{ nodeType: string }} */
  let { nodeType } = $props();

  let t = $derived((key) => $i18n[key] || key);
</script>

<div class="txn-panel" data-testid="txn-panel-{nodeType}">

  {#if nodeType === 'wf-critic'}
    <!-- Anf. 24: CriticNode — Structured Output Badge + CriticItem Preview -->
    <div class="txn-section">
      <div class="txn-badge structured-output">
        <span class="badge-icon">📋</span>
        <span class="badge-text">Structured Output Mode</span>
        <span class="badge-type">CriticItem[]</span>
      </div>

      <div class="txn-schema-preview">
        <h4 class="txn-schema-title">CriticItem Schema</h4>
        <div class="txn-schema-fields">
          <div class="txn-field">
            <span class="field-name">critic_id</span>
            <span class="field-type">string</span>
            <span class="field-desc">Unique identifier</span>
          </div>
          <div class="txn-field">
            <span class="field-name">severity</span>
            <span class="field-type">blocking | critical | major | minor</span>
          </div>
          <div class="txn-field">
            <span class="field-name">target</span>
            <span class="field-type">string</span>
            <span class="field-desc">What is being criticized</span>
          </div>
          <div class="txn-field">
            <span class="field-name">flaw</span>
            <span class="field-type">string</span>
            <span class="field-desc">Description of the flaw</span>
          </div>
          <div class="txn-field">
            <span class="field-name">principle</span>
            <span class="field-type">string</span>
            <span class="field-desc">Underlying principle violated</span>
          </div>
          <div class="txn-field">
            <span class="field-name">context_quote</span>
            <span class="field-type">string | null</span>
            <span class="field-desc">Optional quote from draft</span>
          </div>
        </div>
        <p class="txn-schema-note">Max 10 items per round. Blocking & critical items are prioritized.</p>
      </div>
    </div>

  {:else if nodeType === 'wf-builder'}
    <!-- Anf. 25: BuilderNode — Constructivity Score Indicator -->
    <div class="txn-section">
      <div class="txn-badge structured-output">
        <span class="badge-icon">🔨</span>
        <span class="badge-text">Structured Output Mode</span>
        <span class="badge-type">BuildResponse[] + BuilderOutput</span>
      </div>

      <div class="txn-score-panel">
        <h4 class="txn-score-title">Constructivity Score</h4>
        <p class="txn-score-desc">
          Measures how constructive the Builder's responses are.
          Each CriticItem MUST be answered with 2–3 solution options.
        </p>
        <div class="txn-score-bar">
          <div class="score-zone score-red" style="width: 40%;" title="0.0 – 0.4: Low">
            <span>{'<'} 0.4</span>
          </div>
          <div class="score-zone score-yellow" style="width: 30%;" title="0.4 – 0.7: Medium">
            <span>0.4 – 0.7</span>
          </div>
          <div class="score-zone score-green" style="width: 30%;" title="0.7 – 1.0: High">
            <span>{'>'} 0.7</span>
          </div>
        </div>
        <div class="txn-score-labels">
          <span class="label-low">⚠️ Unconstructive</span>
          <span class="label-mid">⚠️ Improvable</span>
          <span class="label-high">✅ Constructive</span>
        </div>
      </div>
    </div>

  {:else if nodeType === 'wf-pragmatist'}
    <!-- Anf. 26: PragmatistNode — reality_score + blocking_concerns -->
    <div class="txn-section">
      <div class="txn-badge structured-output">
        <span class="badge-icon">⚖️</span>
        <span class="badge-text">Structured Output Mode</span>
        <span class="badge-type">PragmatistOutput</span>
      </div>

      <div class="txn-verdict-panel">
        <h4 class="txn-verdict-title">Verdict Thresholds</h4>
        <div class="txn-verdict-rules">
          <div class="verdict-rule verdict-accept">
            <span class="verdict-icon">✅</span>
            <span class="verdict-label">accept</span>
            <span class="verdict-threshold">feasibility ≥ 0.7</span>
          </div>
          <div class="verdict-rule verdict-revise">
            <span class="verdict-icon">🔄</span>
            <span class="verdict-label">revise</span>
            <span class="verdict-threshold">feasibility 0.4 – 0.7</span>
          </div>
          <div class="verdict-rule verdict-reject">
            <span class="verdict-icon">❌</span>
            <span class="verdict-label">reject</span>
            <span class="verdict-threshold">feasibility {'<'} 0.4</span>
          </div>
        </div>
      </div>

      <div class="txn-concerns-panel">
        <h4 class="txn-concerns-title">Reality Score & Blocking Concerns</h4>
        <div class="txn-concerns-info">
          <div class="concern-item">
            <span class="concern-icon">📊</span>
            <span><strong>reality_score</strong>: 0.0 – 1.0 aggregate feasibility</span>
          </div>
          <div class="concern-item">
            <span class="concern-icon">🚨</span>
            <span><strong>blocking_concerns</strong>: List of deal-breakers that prevent approval</span>
          </div>
        </div>
        <div class="txn-warning-box">
          <span class="warning-icon">⚠️</span>
          <span>If no build responses are available, the Pragmatist returns reality_score = 0.0 with a blocking concern.</span>
        </div>
      </div>
    </div>

  {:else if nodeType === 'wf-angels-advocate'}
    <!-- Angel's Advocate: PreservedElement info -->
    <div class="txn-section">
      <div class="txn-badge structured-output">
        <span class="badge-icon">🛡️</span>
        <span class="badge-text">Structured Output Mode</span>
        <span class="badge-type">AngelsAdvocateOutput</span>
      </div>

      <div class="txn-schema-preview">
        <h4 class="txn-schema-title">PreservedElement Schema</h4>
        <div class="txn-schema-fields">
          <div class="txn-field">
            <span class="field-name">element_id</span>
            <span class="field-type">string</span>
          </div>
          <div class="txn-field">
            <span class="field-name">source_location</span>
            <span class="field-type">string</span>
            <span class="field-desc">Where in the draft</span>
          </div>
          <div class="txn-field">
            <span class="field-name">preserved_text</span>
            <span class="field-type">string</span>
            <span class="field-desc">The text to preserve</span>
          </div>
          <div class="txn-field">
            <span class="field-name">rationale</span>
            <span class="field-type">string</span>
            <span class="field-desc">Why this must be preserved</span>
          </div>
          <div class="txn-field">
            <span class="field-name">priority</span>
            <span class="field-type">essential | important | useful</span>
          </div>
        </div>
        <p class="txn-schema-note">Preserved elements are injected into the Builder as mandatory constraints.</p>
      </div>
    </div>
  {/if}

</div>

<style>
  .txn-panel {
    border-top: 1px solid #e5e7eb;
    padding: 12px 16px;
  }
  :global(.dark) .txn-panel {
    border-color: #374151;
  }

  .txn-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* ── Badge ── */
  .txn-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
  }
  .txn-badge.structured-output {
    background: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
  }
  :global(.dark) .txn-badge.structured-output {
    background: #1e3a5f;
    color: #93c5fd;
    border-color: #1e40af;
  }
  .badge-icon { font-size: 13px; }
  .badge-type {
    margin-left: auto;
    font-family: monospace;
    font-size: 10px;
    opacity: 0.7;
  }

  /* ── Schema Preview ── */
  .txn-schema-preview {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px 12px;
  }
  :global(.dark) .txn-schema-preview {
    background: #111827;
    border-color: #374151;
  }
  .txn-schema-title, .txn-score-title, .txn-verdict-title, .txn-concerns-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #6b7280;
    margin: 0 0 8px 0;
  }
  :global(.dark) .txn-schema-title,
  :global(.dark) .txn-score-title,
  :global(.dark) .txn-verdict-title,
  :global(.dark) .txn-concerns-title {
    color: #9ca3af;
  }
  .txn-schema-fields {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .txn-field {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: 11px;
    padding: 2px 0;
  }
  .field-name {
    font-family: monospace;
    font-weight: 600;
    color: #374151;
    min-width: 100px;
  }
  :global(.dark) .field-name { color: #d1d5db; }
  .field-type {
    font-family: monospace;
    font-size: 10px;
    color: #7c3aed;
    background: #f5f3ff;
    padding: 1px 4px;
    border-radius: 3px;
  }
  :global(.dark) .field-type {
    color: #c4b5fd;
    background: #2e1065;
  }
  .field-desc {
    font-size: 10px;
    color: #9ca3af;
    font-style: italic;
  }
  .txn-schema-note {
    font-size: 10px;
    color: #6b7280;
    margin: 8px 0 0 0;
    padding-top: 6px;
    border-top: 1px dashed #e5e7eb;
  }
  :global(.dark) .txn-schema-note {
    border-color: #374151;
  }

  /* ── Score Bar ── */
  .txn-score-panel, .txn-verdict-panel, .txn-concerns-panel {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px 12px;
  }
  :global(.dark) .txn-score-panel,
  :global(.dark) .txn-verdict-panel,
  :global(.dark) .txn-concerns-panel {
    background: #111827;
    border-color: #374151;
  }
  .txn-score-desc {
    font-size: 11px;
    color: #6b7280;
    margin: 0 0 8px 0;
  }
  .txn-score-bar {
    display: flex;
    height: 20px;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid #e5e7eb;
  }
  .score-zone {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    font-weight: 600;
    color: white;
  }
  .score-red { background: #ef4444; }
  .score-yellow { background: #f59e0b; }
  .score-green { background: #22c55e; }
  .txn-score-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
    font-size: 9px;
    color: #6b7280;
  }

  /* ── Verdict Rules ── */
  .txn-verdict-rules {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .verdict-rule {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 4px;
  }
  .verdict-accept { background: #f0fdf4; color: #166534; }
  .verdict-revise { background: #fffbeb; color: #92400e; }
  .verdict-reject { background: #fef2f2; color: #991b1b; }
  :global(.dark) .verdict-accept { background: #052e16; color: #86efac; }
  :global(.dark) .verdict-revise { background: #451a03; color: #fcd34d; }
  :global(.dark) .verdict-reject { background: #450a0a; color: #fca5a5; }
  .verdict-icon { font-size: 12px; }
  .verdict-label {
    font-weight: 700;
    font-family: monospace;
    min-width: 60px;
  }
  .verdict-threshold {
    font-family: monospace;
    font-size: 10px;
    opacity: 0.8;
  }

  /* ── Concerns Info ── */
  .txn-concerns-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 8px;
  }
  .concern-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #374151;
  }
  :global(.dark) .concern-item { color: #d1d5db; }
  .concern-icon { font-size: 13px; }
  .txn-warning-box {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 10px;
    color: #92400e;
  }
  :global(.dark) .txn-warning-box {
    background: #451a03;
    border-color: #92400e;
    color: #fcd34d;
  }
  .warning-icon { font-size: 12px; flex-shrink: 0; }
</style>
