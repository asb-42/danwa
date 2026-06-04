<script>
  /**
   * Palette — Left column of the Blueprint Canvas.
   *
   * Shows categorized node types from the registry + saved layouts list.
   * In Workflow Mode, also shows workflow node placeholders.
   * Uses HTML5 Drag API for DnD to canvas.
   */
  import { onMount } from 'svelte';
  import { tStore } from '../../lib/i18n/index.js';
  import { canvasStore } from '../../lib/blueprint/store.svelte.js';
  import { getNodesByCategory } from '../../lib/blueprint/registry.js';
  import { registerAllNodeTypes } from '../../lib/blueprint/registerAll.js';
  import { listCanvasLayouts, deleteCanvasLayout } from '../../lib/blueprint/api.js';
  import { listBlueprintLLMProfiles } from '../../lib/blueprint/api.js';
  import { listRoleDefinitions } from '../../lib/blueprint/api.js';
  import { listPromptTemplates } from '../../lib/blueprint/api.js';
  import { listAgentBlueprints } from '../../lib/blueprint/api.js';
  import { listRoleTypes } from '../../lib/blueprint/api.js';
  import { listToneProfiles } from '../../lib/blueprint/api.js';
  import { listAgentBundles } from '../../lib/blueprint/api.js';
  import { getModules } from '../../lib/api/module.js';
  import PaletteCategory from './PaletteCategory.svelte';
  import PaletteEntityList from './PaletteEntityList.svelte';

  let { onloadlayout = () => {} } = $props();

  let t = $derived($tStore);

  /** @type {Array} */
  let savedLayouts = $state([]);
  let layoutsLoading = $state(false);

  // DB entity lists for palette
  let llmProfiles = $state([]);
  let roleDefinitions = $state([]);
  let promptTemplates = $state([]);
  let agentBlueprints = $state([]);
  let roleTypes = $state([]);
  let toneProfiles = $state([]);
  let agentBundles = $state([]);
  let agentCores = $state([]);
  let entitiesLoading = $state(false);

  // Ensure registry is populated before reading categories
  registerAllNodeTypes();
  const assetNodes = getNodesByCategory('asset');
  const workflowNodes = getNodesByCategory('workflow');

  // Transactional Drafting role nodes
  const TRANSACTIONAL_TYPES = new Set([
    'wf-strategist', 'wf-critic', 'wf-builder', 'wf-pragmatist',
    'wf-angels-advocate', 'wf-moderator',
  ]);
  const transactionalWorkflowNodes = workflowNodes.filter(n => TRANSACTIONAL_TYPES.has(n.type));
  const generalWorkflowNodes = workflowNodes.filter(n => !TRANSACTIONAL_TYPES.has(n.type));
  let isWorkflowMode = $derived(canvasStore.mode === 'workflow');

  async function loadLayouts() {
    layoutsLoading = true;
    try {
      savedLayouts = await listCanvasLayouts();
    } catch (err) {
      if (import.meta.env.DEV) console.warn('[Palette] Failed to load layouts:', err);
    } finally {
      layoutsLoading = false;
    }
  }

  async function loadEntities() {
    entitiesLoading = true;
    try {
      const [lp, rd, pt, ab, rt, tp, bundles, modules] = await Promise.all([
        listBlueprintLLMProfiles().catch(() => []),
        listRoleDefinitions().catch(() => []),
        listPromptTemplates().catch(() => []),
        listAgentBlueprints().catch(() => []),
        listRoleTypes().catch(() => []),
        listToneProfiles().catch(() => []),
        listAgentBundles().catch(() => []),
        getModules().catch(() => []),
      ]);
      llmProfiles = lp;
      roleDefinitions = rd;
      promptTemplates = pt;
      agentBlueprints = ab;
      roleTypes = rt;
      toneProfiles = tp;
      agentBundles = bundles;
      agentCores = (modules || [])
        .filter(m => m.category === 'agent-core' && m.enabled !== false)
        .map(m => ({ id: m.module_id || m.id, name: m.name, role: m.role || '', description: m.description || '' }));
    } catch (err) {
      if (import.meta.env.DEV) console.warn('[Palette] Failed to load entities:', err);
    } finally {
      entitiesLoading = false;
    }
  }

  async function handleDeleteLayout(layoutId) {
    try {
      await deleteCanvasLayout(layoutId);
      savedLayouts = savedLayouts.filter((l) => l.id !== layoutId);
      if (canvasStore.currentLayoutId === layoutId) {
        canvasStore.currentLayoutId = null;
        canvasStore.currentLayoutName = null;
      }
    } catch (err) {
      if (import.meta.env.DEV) console.warn('[Palette] Failed to delete layout:', err);
    }
  }

  // Load layouts and entities once on mount
  onMount(() => {
    loadLayouts();
    loadEntities();
  });
</script>

<div class="palette" data-testid="blueprint-palette">
  <!-- Assets section (always visible) -->
  <PaletteCategory
    title={t('blueprint.palette.assets')}
    nodes={assetNodes}
  />

  <!-- Existing DB entities (draggable to canvas) -->
  <div class="palette-section">
    <h3 class="palette-title">
      {t('blueprint.palette.existingEntities')}
      {#if entitiesLoading}
        <span class="loading-dot">⏳</span>
      {/if}
    </h3>
    <PaletteEntityList
      label={t('blueprint.palette.llmProfiles')}
      icon="🧠"
      nodeType="llm-profile"
      entities={llmProfiles}
    />
    <PaletteEntityList
      label={t('blueprint.palette.roleDefinitions')}
      icon="👤"
      nodeType="role-definition"
      entities={roleDefinitions}
    />
    <PaletteEntityList
      label={t('blueprint.palette.promptTemplates')}
      icon="📝"
      nodeType="prompt-template"
      entities={promptTemplates}
    />
    <PaletteEntityList
      label={t('blueprint.palette.agentBlueprints')}
      icon="🤖"
      nodeType="agent-blueprint"
      entities={agentBlueprints}
    />
    <PaletteEntityList
      label={t('blueprint.palette.roleTypes')}
      icon="🏷️"
      nodeType="role-type"
      entities={roleTypes}
    />
    <PaletteEntityList
      label={t('blueprint.palette.toneProfiles')}
      icon="🎵"
      nodeType="tone-profile"
      entities={toneProfiles}
    />
    <PaletteEntityList
      label={t('blueprint.palette.agentCores')}
      icon="🧬"
      nodeType="agent-core"
      entities={agentCores}
    />
    <PaletteEntityList
      label={t('blueprint.palette.agentBundles')}
      icon="📦"
      nodeType="agent-bundle"
      entities={agentBundles}
    />
  </div>

  <!-- Workflow nodes (only in Workflow Mode) -->
  {#if isWorkflowMode}
    {#if transactionalWorkflowNodes.length > 0}
      <PaletteCategory
        title={t('blueprint.palette.transactionalRoles')}
        nodes={transactionalWorkflowNodes}
      />
    {/if}
    {#if generalWorkflowNodes.length > 0}
      <PaletteCategory
        title={t('blueprint.palette.workflowNodes')}
        nodes={generalWorkflowNodes}
      />
    {/if}
  {/if}

  <!-- Saved Layouts section -->
  <div class="palette-section">
    <h3 class="palette-title">{t('blueprint.palette.savedLayouts')}</h3>

    {#if layoutsLoading}
      <p class="palette-empty">Loading...</p>
    {:else if savedLayouts.length === 0}
      <p class="palette-empty">No saved layouts</p>
    {:else}
      {#each savedLayouts as layout}
        <div class="layout-item" data-testid="palette-layout-{layout.id}">
          <button
            class="layout-load-btn"
            onclick={() => onloadlayout(layout)}
            title={t('blueprint.canvas.loadLayout')}
          >
            <span class="layout-icon">📐</span>
            <span class="layout-name">{layout.name}</span>
          </button>
          <button
            class="layout-delete-btn"
            onclick={() => handleDeleteLayout(layout.id)}
            title={t('blueprint.canvas.deleteLayout')}
            data-testid="palette-layout-delete-{layout.id}"
          >
            ✕
          </button>
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .palette {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 12px;
  }
  .palette-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .palette-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    padding-bottom: 4px;
    border-bottom: 1px solid #e5e7eb;
  }
  :global(.dark) .palette-title {
    color: #9ca3af;
    border-color: #374151;
  }
  .loading-dot {
    font-size: 10px;
    margin-left: 4px;
    animation: pulse 1s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .palette-empty {
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
    padding: 4px 0;
  }
  .layout-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .layout-load-btn {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid transparent;
    background: transparent;
    cursor: pointer;
    font-size: 12px;
    color: #374151;
    text-align: left;
    transition: all 0.15s ease;
  }
  :global(.dark) .layout-load-btn { color: #e5e7eb; }
  .layout-load-btn:hover {
    background: #f3f4f6;
    border-color: #e5e7eb;
  }
  :global(.dark) .layout-load-btn:hover {
    background: #374151;
  }
  .layout-icon { font-size: 14px; }
  .layout-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .layout-delete-btn {
    padding: 4px 6px;
    border: none;
    background: transparent;
    color: #9ca3af;
    cursor: pointer;
    font-size: 12px;
    border-radius: 4px;
    transition: all 0.15s ease;
  }
  .layout-delete-btn:hover {
    color: #ef4444;
    background: #fef2f2;
  }
</style>
