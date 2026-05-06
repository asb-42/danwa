<script>
  /**
   * PauseControls — Pause/resume button and status indicator for debates.
   * Shows current pause state and allows toggling.
   */

  import { pauseDebate } from '../../lib/hitl.js';
  import { hitlStatus } from '../../lib/stores/hitl.svelte.js';

  let { debateId = '' } = $props();

  let isToggling = $state(false);
  let error = $state(null);

  let status = $derived($hitlStatus);
  let isPaused = $derived(status.is_paused);
  let isRunning = $derived(status.hitl_enabled);

  async function handleToggle() {
    if (isToggling || !debateId) return;

    isToggling = true;
    error = null;

    try {
      await pauseDebate(debateId, {
        action: isPaused ? 'resume' : 'pause',
      });
    } catch (err) {
      error = err.message || 'Failed to toggle pause';
      setTimeout(() => { error = null; }, 5000);
    } finally {
      isToggling = false;
    }
  }
</script>

{#if isRunning}
  <div class="pause-controls">
    <button
      class="pause-button"
      class:paused={isPaused}
      onclick={handleToggle}
      disabled={isToggling}
      title={isPaused ? 'Resume debate' : 'Pause debate'}
      aria-label={isPaused ? 'Resume debate' : 'Pause debate'}
    >
      {#if isToggling}
        <span class="spinner"></span>
      {:else if isPaused}
        <span class="icon">▶️</span>
        <span class="label">Resume</span>
      {:else}
        <span class="icon">⏸️</span>
        <span class="label">Pause</span>
      {/if}
    </button>

    {#if isPaused}
      <div class="pause-indicator" role="status">
        <span class="pulse-dot"></span>
        <span>Paused</span>
      </div>
    {/if}

    {#if error}
      <div class="pause-error" role="alert">{error}</div>
    {/if}
  </div>
{/if}

<style>
  .pause-controls {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .pause-button {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: var(--color-surface, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 6px;
    color: var(--color-text, #cdd6f4);
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .pause-button:hover:not(:disabled) {
    background: var(--color-surface-hover, #252536);
    border-color: var(--color-primary, #89b4fa);
  }

  .pause-button.paused {
    background: rgba(166, 227, 161, 0.1);
    border-color: rgba(166, 227, 161, 0.3);
    color: #a6e3a1;
  }

  .pause-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .icon {
    font-size: 1rem;
  }

  .label {
    font-size: 0.8rem;
  }

  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(205, 214, 244, 0.2);
    border-top-color: var(--color-text, #cdd6f4);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .pause-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: #f9e2af;
    font-weight: 500;
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    background: #f9e2af;
    border-radius: 50%;
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .pause-error {
    font-size: 0.75rem;
    color: #f38ba8;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
