<script>
  /**
   * PromptTemplateNode — Custom Svelte Flow node for Prompt Templates.
   *
   * Displays: name, 3-line content preview, variables count.
   * Handles: LEFT (target), RIGHT (source).
   */
  import { Handle, Position } from '@xyflow/svelte';

  /** @type {{ data: any, selected?: boolean }} */
  let { data, selected = false } = $props();

  let preview = $derived(() => {
    const content = data?.content || '';
    const lines = content.split('\n').filter((l) => l.trim()).slice(0, 3);
    return lines.map((l) => (l.length > 40 ? l.slice(0, 37) + '...' : l));
  });
  let varCount = $derived(data?.variables?.length || 0);
  let isDraft = $derived(!!data?.isDraft);
</script>

<div
  class="blueprint-node prompt-template-node"
  class:selected
  class:draft={isDraft}
  data-testid="node-prompt-template-{data?.blueprint_id || 'draft'}"
>
  <Handle type="target" position={Position.LEFT} />

  <div class="node-header">
    <span class="node-icon">📝</span>
    <span class="node-type-label">Prompt Template</span>
    {#if isDraft}
      <span class="draft-badge">Draft</span>
    {/if}
  </div>

  <div class="node-body">
    <span class="node-name">{data?.name || 'Unnamed'}</span>

    {#if data?.role}
      <span class="role-label">{data.role} · {data?.variant || 'default'}</span>
    {/if}

    {#if preview().length > 0}
      <div class="content-preview">
        {#each preview() as line}
          <span class="preview-line">"{line}"</span>
        {/each}
      </div>
    {/if}

    {#if varCount > 0}
      <span class="var-count">{varCount} variable{varCount !== 1 ? 's' : ''}</span>
    {/if}
  </div>

  <Handle type="source" position={Position.RIGHT} />
</div>

<style>
  .blueprint-node {
    background: #ecfdf5;
    border: 2px solid #10b981;
    border-radius: 12px;
    padding: 12px;
    min-width: 180px;
    max-width: 220px;
    font-size: 13px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
  }
  :global(.dark) .blueprint-node {
    background: #022c22;
  }
  .blueprint-node.selected {
    box-shadow: 0 0 0 2px #10b981, 0 4px 12px rgba(0,0,0,0.15);
  }
  .blueprint-node.draft {
    opacity: 0.8;
    border-style: dashed;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
  }
  .node-icon { font-size: 16px; }
  .node-type-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    font-weight: 600;
  }
  .draft-badge {
    margin-left: auto;
    font-size: 9px;
    background: #f59e0b;
    color: white;
    padding: 1px 6px;
    border-radius: 8px;
    font-weight: 600;
  }
  .node-body {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .node-name {
    font-weight: 700;
    font-size: 14px;
    color: #064e3b;
  }
  :global(.dark) .node-name { color: #a7f3d0; }
  .role-label {
    font-size: 10px;
    color: #6b7280;
    text-transform: capitalize;
  }
  .content-preview {
    display: flex;
    flex-direction: column;
    gap: 1px;
    margin-top: 2px;
  }
  .preview-line {
    font-size: 10px;
    color: #9ca3af;
    font-style: italic;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .var-count {
    font-size: 10px;
    color: #6b7280;
    margin-top: 2px;
  }
</style>
