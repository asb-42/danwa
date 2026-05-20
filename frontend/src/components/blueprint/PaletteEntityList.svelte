<script>
  /**
   * PaletteEntityList — Collapsible list of existing DB entities in the Palette.
   *
   * Each entity is draggable to the canvas. On drop, the canvas creates
   * a non-draft node with the entity's real data.
   */
  import { handleEntityDragStart } from '../../lib/blueprint/dnd.js';

  /** @type {{ label: string, icon: string, nodeType: string, entities: Array }} */
  let { label, icon, nodeType, entities = [] } = $props();

  let expanded = $state(false);
</script>

{#if entities.length > 0}
  <div class="entity-list" data-testid="palette-entities-{nodeType}">
    <button
      class="entity-list-header"
      onclick={() => expanded = !expanded}
      aria-expanded={expanded}
    >
      <span class="entity-list-icon">{icon}</span>
      <span class="entity-list-label">{label}</span>
      <span class="entity-list-count">{entities.length}</span>
      <span class="entity-list-chevron" class:rotated={expanded}>▸</span>
    </button>

    {#if expanded}
      <div class="entity-list-items">
        {#each entities as entity}
          <div
            class="entity-item"
            draggable="true"
            ondragstart={(e) => handleEntityDragStart(e, nodeType, entity.id)}
            data-testid="palette-entity-{nodeType}-{entity.id}"
            role="button"
            tabindex="0"
          >
            <span class="entity-name">{entity.name || entity.id}</span>
            {#if entity.provider}
              <span class="entity-meta">{entity.provider}</span>
            {/if}
            {#if nodeType === 'role-definition' && entity.role}
              <span class="entity-meta">{entity.role}</span>
            {/if}
            {#if nodeType === 'tone-profile' && entity.tone}
              <span class="entity-meta">{entity.tone}</span>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .entity-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .entity-list-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 12px;
    color: #374151;
    border-radius: 6px;
    transition: background 0.15s ease;
    width: 100%;
    text-align: left;
  }
  :global(.dark) .entity-list-header {
    color: #e5e7eb;
  }
  .entity-list-header:hover {
    background: #f3f4f6;
  }
  :global(.dark) .entity-list-header:hover {
    background: #374151;
  }
  .entity-list-icon {
    font-size: 14px;
  }
  .entity-list-label {
    flex: 1;
    font-weight: 500;
  }
  .entity-list-count {
    font-size: 10px;
    color: #9ca3af;
    background: #f3f4f6;
    border-radius: 10px;
    padding: 1px 6px;
    min-width: 18px;
    text-align: center;
  }
  :global(.dark) .entity-list-count {
    background: #374151;
    color: #6b7280;
  }
  .entity-list-chevron {
    font-size: 10px;
    color: #9ca3af;
    transition: transform 0.2s ease;
  }
  .entity-list-chevron.rotated {
    transform: rotate(90deg);
  }
  .entity-list-items {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding-left: 8px;
  }
  .entity-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid transparent;
    background: white;
    cursor: grab;
    transition: all 0.15s ease;
    font-size: 11px;
  }
  :global(.dark) .entity-item {
    background: #1f2937;
  }
  .entity-item:hover {
    border-color: #3b82f6;
    box-shadow: 0 1px 4px rgba(59, 130, 246, 0.15);
  }
  .entity-item:active {
    cursor: grabbing;
    opacity: 0.7;
  }
  .entity-name {
    flex: 1;
    font-weight: 500;
    color: #374151;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  :global(.dark) .entity-name {
    color: #e5e7eb;
  }
  .entity-meta {
    font-size: 9px;
    color: #9ca3af;
    text-transform: capitalize;
  }
</style>
