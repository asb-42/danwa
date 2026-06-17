<script>
  import { tStore } from '../../lib/i18n/index.js';

  let {
    activityText = '',
    consumedInterjections = [],
    isConnected = false,
    isVisible = false,
  } = $props();

  let t = $derived($tStore);
</script>

{#if isVisible}
  <!-- DEBUG 2026-06-17: visual marker to identify this component on screen -->
  <div data-debug-component="DebateActivityLog" class="px-2 py-0.5 mb-1 inline-block rounded bg-pink-600 text-white text-[10px] font-mono font-bold tracking-wider">DBG: DebateActivityLog.svelte</div>
  <div class="activity-log">
    {#if activityText}
      <div class="activity-current">
        {#if isConnected}
          <span class="activity-dot"></span>
        {/if}
        <span class="activity-text">{activityText}</span>
      </div>
    {/if}

    {#if consumedInterjections.length > 0}
      <div class="activity-interjections">
        {#each consumedInterjections.slice(-5) as inj}
          <div class="activity-inj-item">
            <span class="activity-inj-icon">💬</span>
            <span class="activity-inj-text">
              {inj.role} received {inj.count} interjection{inj.count > 1 ? 's' : ''} (Round {inj.round})
            </span>
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .activity-log {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 14px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    font-size: 13px;
    color: #1e40af;
    animation: fadeIn 0.3s ease;
  }
  :global(.dark) .activity-log {
    background: #1e3a5f;
    border-color: #2563eb;
    color: #93c5fd;
  }

  .activity-current {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .activity-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #3b82f6;
    animation: pulse 1.5s infinite;
    flex-shrink: 0;
  }

  .activity-text {
    font-weight: 500;
  }

  .activity-interjections {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding-top: 6px;
    border-top: 1px solid #bfdbfe;
  }
  :global(.dark) .activity-interjections {
    border-color: #2563eb;
  }

  .activity-inj-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    opacity: 0.85;
  }

  .activity-inj-icon {
    font-size: 12px;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
</style>
