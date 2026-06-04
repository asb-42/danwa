<script>
  /**
   * AgentCoreForm — Inspector form for agent-core module nodes.
   *
   * Read-only info panel showing module details.
   * Modules are managed in the Modules view; the canvas form is for
   * inspection and connection wiring only.
   */
  import { onMount } from 'svelte';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import { getModule } from '../../../lib/api/module.js';

  /** @type {{ node: any, onsave?: (data: any) => void, ondelete?: () => void }} */
  let { node, onsave = () => {}, ondelete = () => {} } = $props();

  let moduleName = $derived(node?.data?.name || node?.data?.module_name || 'Agent Core');
  let moduleRole = $derived(node?.data?.role || '');
  let moduleDescription = $derived(node?.data?.description || '');
  let moduleId = $derived(node?.data?.module_id || node?.data?.blueprint_id || '');
  let isDraft = $derived(!!node?.data?.isDraft);

  let moduleInfo = $state(null);
  let loading = $state(false);

  const ROLE_ICONS = {
    strategist: '🧠', critic: '🔍', optimizer: '⚡', moderator: '🎯',
    analyst: '📊', creative: '💡', 'fact-checker': '✅',
    'expert-reviewer': '🔬', mediator: '🤝', ethicist: '⚖️',
    synthesizer: '🔗', 'devils-advocate': '👿',
  };
  let nodeIcon = $derived(ROLE_ICONS[moduleRole] || '🧬');

  // Connected AgentBlueprints (from uses_core edges)
  let connectedBlueprints = $state([]);

  $effect(() => {
    if (!node?.id || typeof window === 'undefined') return;
    const edges = canvasStore.edges;
    const nodes = canvasStore.nodes;
    const bpEdges = edges.filter(
      (e) => e.target === node.id && e.type === 'uses_core'
    );
    connectedBlueprints = bpEdges
      .map((e) => nodes.find((n) => n.id === e.source))
      .filter(Boolean)
      .map((n) => n.data);
  });

  onMount(async () => {
    if (!moduleId || isDraft) return;
    loading = true;
    try {
      moduleInfo = await getModule(moduleId);
    } catch (err) {
      if (import.meta.env.DEV) console.warn('[AgentCoreForm] Failed to load module:', err);
    } finally {
      loading = false;
    }
  });

  function handleDelete() {
    canvasStore.removeNode(node.id);
    ondelete();
  }
</script>

<div class="form-container" data-testid="form-agent-core">
  <div class="form-header">
    <span class="form-icon">{nodeIcon}</span>
    <span class="form-title">Agent Core</span>
    {#if isDraft}
      <span class="draft-badge">Draft</span>
    {/if}
  </div>

  <!-- Connected Agent Blueprints -->
  {#if connectedBlueprints.length > 0}
    <div class="connections-section">
      <span class="connections-label">Connections</span>
      {#each connectedBlueprints as bp}
        <div class="connection-item">
          <span class="connection-edge">uses_core ←</span>
          <span class="connection-entity">🤖 {bp.name || bp.id}</span>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Module name (read-only) -->
  <div class="form-field readonly">
    <span class="field-label">Name</span>
    <span class="field-value">{moduleName}</span>
  </div>

  <!-- Role badge (read-only) -->
  {#if moduleRole}
    <div class="form-field readonly">
      <span class="field-label">Role</span>
      <span class="role-badge">{nodeIcon} {moduleRole}</span>
    </div>
  {/if}

  <!-- Description (read-only) -->
  {#if moduleDescription}
    <div class="form-field readonly">
      <span class="field-label">Description</span>
      <span class="field-value description">{moduleDescription}</span>
    </div>
  {/if}

  <!-- Module details (from API) -->
  {#if moduleInfo}
    {#if moduleInfo.version}
      <div class="form-field readonly">
        <span class="field-label">Version</span>
        <span class="field-value monospace">{moduleInfo.version}</span>
      </div>
    {/if}
    {#if moduleInfo.tags?.length > 0}
      <div class="form-field readonly">
        <span class="field-label">Tags</span>
        <div class="tags-row">
          {#each moduleInfo.tags as tag}
            <span class="tag">{tag}</span>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  <!-- Module ID -->
  {#if moduleId}
    <div class="form-field readonly">
      <span class="field-label">Module ID</span>
      <span class="field-value monospace small">{moduleId}</span>
    </div>
  {/if}

  {#if loading}
    <div class="loading-hint">Loading module details...</div>
  {/if}

  <!-- Edit in Modules link -->
  {#if moduleId && !isDraft}
    <a href="/manage?tab=modules&module={moduleId}" class="modules-link">
      📦 Edit in Modules View
    </a>
  {/if}

  <!-- Actions -->
  <div class="form-actions">
    <button class="btn-delete" onclick={handleDelete} data-testid="form-ac-remove">
      Remove from Canvas
    </button>
  </div>
</div>

<style>
  .form-container { display: flex; flex-direction: column; gap: 12px; padding: 16px; }
  .form-header { display: flex; align-items: center; gap: 8px; }
  .form-icon { font-size: 18px; }
  .form-title { font-weight: 700; font-size: 14px; color: #1f2937; }
  :global(.dark) .form-title { color: #e5e7eb; }
  .draft-badge {
    font-size: 9px; background: #f59e0b; color: white;
    padding: 1px 6px; border-radius: 8px; font-weight: 600;
    margin-left: auto;
  }
  .connections-section { padding: 8px 0; }
  .connections-label {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.05em; color: #6b7280; display: block; margin-bottom: 6px;
  }
  :global(.dark) .connections-label { color: #9ca3af; }
  .connection-item {
    display: flex; align-items: center; gap: 6px;
    padding: 4px 8px; font-size: 12px;
    background: #f9fafb; border-radius: 6px; margin-bottom: 4px;
  }
  :global(.dark) .connection-item { background: #1f2937; }
  .connection-edge { font-size: 10px; color: #0d9488; font-weight: 600; }
  .connection-entity { color: #374151; }
  :global(.dark) .connection-entity { color: #d1d5db; }
  .form-field { display: flex; flex-direction: column; gap: 2px; }
  .form-field.readonly { gap: 1px; }
  .field-label {
    font-size: 11px; font-weight: 600; color: #6b7280;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  :global(.dark) .field-label { color: #9ca3af; }
  .field-value {
    font-size: 13px; color: #374151; line-height: 1.4;
  }
  :global(.dark) .field-value { color: #d1d5db; }
  .field-value.description {
    font-size: 12px; color: #6b7280; line-height: 1.5;
  }
  :global(.dark) .field-value.description { color: #9ca3af; }
  .field-value.monospace {
    font-family: monospace; font-size: 12px; color: #6b7280;
    word-break: break-all;
  }
  .field-value.small { font-size: 10px; }
  .role-badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 12px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; color: #0d9488; background: #ccfbf1;
    padding: 3px 10px; border-radius: 6px; width: fit-content;
  }
  :global(.dark) .role-badge { background: #134e4a; color: #5eead4; }
  .tags-row { display: flex; flex-wrap: wrap; gap: 4px; }
  .tag {
    font-size: 10px; background: #f3f4f6; color: #6b7280;
    padding: 2px 8px; border-radius: 10px;
  }
  :global(.dark) .tag { background: #374151; color: #9ca3af; }
  .loading-hint {
    font-size: 12px; color: #9ca3af; font-style: italic;
    text-align: center; padding: 8px;
  }
  .modules-link {
    display: block; text-align: center; padding: 8px 12px;
    font-size: 12px; color: #6366f1; text-decoration: none;
    background: #eef2ff; border-radius: 6px; font-weight: 500;
    transition: background 0.15s;
  }
  .modules-link:hover { background: #e0e7ff; }
  :global(.dark) .modules-link {
    background: #1e1b4b; color: #a5b4fc;
  }
  :global(.dark) .modules-link:hover { background: #312e81; }
  .form-actions { display: flex; gap: 8px; margin-top: 4px; }
  .btn-delete {
    flex: 1; padding: 8px 12px; border: 1px solid #fca5a5;
    background: #fef2f2; color: #dc2626; border-radius: 8px;
    font-size: 12px; font-weight: 600; cursor: pointer;
    transition: all 0.15s;
  }
  .btn-delete:hover { background: #fee2e2; }
  :global(.dark) .btn-delete {
    background: #450a0a; border-color: #7f1d1d; color: #fca5a5;
  }
  :global(.dark) .btn-delete:hover { background: #7f1d1d; }
</style>
