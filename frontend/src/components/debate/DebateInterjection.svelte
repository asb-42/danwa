<script>
  import { tStore } from '../../lib/i18n/index.js';

  let {
    disabled = false,
    sending = false,
    feedback = '',
    onSend = () => {},
  } = $props();

  let text = $state('');

  let t = $derived($tStore);

  function handleSend() {
    if (!text.trim() || sending) return;
    onSend(text.trim());
    text = '';
  }
</script>

<div class="interjection-area">
  <div class="interjection-input-row">
    <input
      type="text"
      class="interjection-input"
      bind:value={text}
      placeholder={t('mvpDebate.interjectionPlaceholder')}
      aria-label={t('mvpDebate.interjectionPlaceholder')}
      onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
      disabled={disabled || sending}
    />
    <button
      class="btn-interject"
      onclick={handleSend}
      disabled={!text.trim() || sending || disabled}
    >
      Send
    </button>
  </div>
  {#if feedback}
    <div class="interjection-feedback" class:consumed={feedback.startsWith('📨')}>
      {feedback}
    </div>
  {/if}
</div>

<style>
  .interjection-area {
    padding: 12px;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 8px;
  }
  :global(.dark) .interjection-area {
    background: #164e63;
    border-color: #155e75;
  }
  .interjection-input-row {
    display: flex;
    gap: 8px;
  }
  .interjection-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    outline: none;
    background: white;
    color: #1f2937;
  }
  :global(.dark) .interjection-input {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .interjection-input:focus { border-color: #3b82f6; }
  .btn-interject {
    background: #0ea5e9;
    color: white;
    padding: 8px 20px;
    border-radius: 8px;
    border: none;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn-interject:hover { background: #0284c7; }
  .btn-interject:disabled { opacity: 0.5; cursor: not-allowed; }
  .interjection-feedback {
    margin-top: 8px;
    padding: 6px 12px;
    background: #dcfce7;
    border: 1px solid #86efac;
    border-radius: 6px;
    font-size: 13px;
    color: #166534;
    animation: fadeIn 0.3s ease-in;
  }
  .interjection-feedback.consumed {
    background: #dbeafe;
    border-color: #93c5fd;
    color: #1e40af;
  }
  :global(.dark) .interjection-feedback {
    background: #14532d;
    border-color: #22c55e;
    color: #bbf7d0;
  }
  :global(.dark) .interjection-feedback.consumed {
    background: #1e3a5f;
    border-color: #3b82f6;
    color: #bfdbfe;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
