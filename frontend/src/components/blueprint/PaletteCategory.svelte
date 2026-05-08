<script>
  /**
   * PaletteCategory — Reusable section in the Palette.
   *
   * Renders a list of draggable palette items from the registry.
   * Inactive items (active: false) are rendered with reduced opacity
   * and cannot be dragged.
   */
  import { i18n } from '../../lib/i18n/index.js';
  import { handlePaletteDragStart } from '../../lib/blueprint/dnd.js';

  /** @type {{ title: string, nodes: Array }} */
  let { title, nodes = [] } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });
</script>

<div class="palette-category" data-testid="palette-category-{title}">
  <h3 class="palette-category-title">{title}</h3>

  {#each nodes as node}
    <div
      class="palette-item"
      class:inactive={!node.active}
      draggable={node.active ? 'true' : 'false'}
      ondragstart={(e) => node.active && handlePaletteDragStart(e, node.type)}
      data-testid="palette-item-{node.type}"
      role="button"
      tabindex="0"
    >
      <span class="palette-item-icon">{node.icon}</span>
      <span class="palette-item-label">{t(node.labelKey)}</span>
      {#if !node.active}
        <span class="palette-item-badge">Soon</span>
      {/if}
    </div>
  {/each}
</div>

<style>
  .palette-category {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .palette-category-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    padding-bottom: 4px;
    border-bottom: 1px solid #e5e7eb;
  }
  :global(.dark) .palette-category-title {
    color: #9ca3af;
    border-color: #374151;
  }
  .palette-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background: white;
    cursor: grab;
    transition: all 0.15s ease;
    font-size: 13px;
  }
  :global(.dark) .palette-item {
    background: #1f2937;
    border-color: #374151;
  }
  .palette-item:hover {
    border-color: #3b82f6;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
  }
  .palette-item:active {
    cursor: grabbing;
    opacity: 0.7;
  }
  .palette-item.inactive {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
  }
  .palette-item-icon {
    font-size: 16px;
  }
  .palette-item-label {
    font-weight: 500;
    color: #374151;
    flex: 1;
  }
  :global(.dark) .palette-item-label {
    color: #e5e7eb;
  }
  .palette-item-badge {
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    color: #9ca3af;
    background: #f3f4f6;
    border-radius: 4px;
    padding: 1px 5px;
  }
  :global(.dark) .palette-item-badge {
    background: #374151;
    color: #6b7280;
  }
</style>
