<script>
  let {
    sessions = [],
    activeSessionId = null,
    onSelect = () => {},
    onNew = () => {},
    onDelete = () => {},
    t = (key) => key,
  } = $props();
</script>

<div class="session-sidebar">
  <div class="session-header">
    <span>{t('kitsune.sessions')}</span>
    <button class="btn-new" onclick={onNew} title={t('kitsune.newSession')}>+</button>
  </div>
  <div class="session-list">
    {#each sessions as session (session.id)}
      <div
        class="session-item"
        class:active={activeSessionId === session.id}
        onclick={() => onSelect(session)}
      >
        <span class="session-title">{session.title || t('kitsune.newSession')}</span>
        <button class="btn-delete" onclick={(e) => onDelete(session, e)}>×</button>
      </div>
    {/each}
  </div>
</div>

<style>
  .session-sidebar {
    width: 180px;
    border-right: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    background: #f9fafb;
  }

  .session-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 600;
    color: #374151;
    border-bottom: 1px solid #e5e7eb;
  }

  .btn-new {
    background: #667eea;
    color: white;
    border: none;
    width: 22px;
    height: 22px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .btn-new:hover {
    background: #5568d3;
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    cursor: pointer;
    border-bottom: 1px solid #f3f4f6;
    transition: background 0.2s;
  }

  .session-item:hover {
    background: #f3f4f6;
  }

  .session-item.active {
    background: #e0e7ff;
    border-left: 3px solid #667eea;
  }

  .session-title {
    font-size: 12px;
    color: #374151;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .btn-delete {
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    font-size: 16px;
    padding: 0 4px;
    opacity: 0;
    transition: opacity 0.2s, color 0.2s;
  }

  .session-item:hover .btn-delete {
    opacity: 1;
  }

  .btn-delete:hover {
    color: #ef4444;
  }

  :global(.dark) .session-sidebar {
    background: #374151;
    border-right-color: #4b5563;
  }

  :global(.dark) .session-header {
    color: #e5e7eb;
    border-bottom-color: #4b5563;
  }

  :global(.dark) .session-item {
    border-bottom-color: #374151;
  }

  :global(.dark) .session-item:hover {
    background: #4b5563;
  }

  :global(.dark) .session-item.active {
    background: #1e3a5f;
    border-left-color: #60a5fa;
  }

  :global(.dark) .session-title {
    color: #d1d5db;
  }

  @media (max-width: 768px) {
    .session-sidebar {
      width: 140px;
    }
  }
</style>
