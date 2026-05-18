<script>
  /**
   * BundleAgentForm — Inspector form for wf-agent nodes.
   *
   * Shows: label (editable), bundle selector dropdown, resolved bundle info.
   * Save updates node data via canvasStore.updateNodeData().
   */
  import { onMount } from 'svelte';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import { listAgentBundles } from '../../../lib/blueprint/api.js';

  let { node, onsave, ondelete } = $props();

  let label = $state('');
  let bundleId = $state('');
  let bundles = $state([]);
  let loading = $state(false);
  let selectedBundle = $derived(bundles.find((b) => b.id === bundleId));

  $effect(() => {
    label = node?.data?.label || '';
    bundleId = node?.data?.bundle_id || '';
  });

  onMount(async () => {
    loading = true;
    try {
      bundles = await listAgentBundles({ active_only: true });
    } catch (err) {
      console.warn('[BundleAgentForm] Failed to load bundles:', err);
    } finally {
      loading = false;
    }
  });

  function handleSave() {
    const data = { label, bundle_id: bundleId || null };
    canvasStore.updateNodeData(node.id, data);
    onsave?.(data);
  }
</script>

<div class="bundle-agent-form" data-testid="bundle-agent-form">
  <!-- Label (editable) -->
  <div class="form-group">
    <label class="form-label" for="wf-bundle-label">Label</label>
    <input
      id="wf-bundle-label"
      type="text"
      class="form-input"
      bind:value={label}
      placeholder="Agent label"
      onblur={handleSave}
    />
  </div>

  <!-- Bundle selector -->
  <div class="form-group">
    <label class="form-label" for="wf-bundle">Agent Bundle</label>
    {#if loading}
      <div class="form-loading">Loading bundles...</div>
    {:else}
      <select
        id="wf-bundle"
        class="form-select"
        bind:value={bundleId}
        onchange={handleSave}
      >
        <option value="">— None —</option>
        {#each bundles as bundle}
          <option value={bundle.id}>{bundle.name}</option>
        {/each}
      </select>
    {/if}
  </div>

  <!-- Resolved bundle info -->
  {#if selectedBundle}
    <div class="bundle-info">
      <div class="bundle-info-row">
        <span class="bundle-info-label">Role Type</span>
        <span class="bundle-info-value">{selectedBundle.role_type_id || '—'}</span>
      </div>
      <div class="bundle-info-row">
        <span class="bundle-info-label">LLM Profile</span>
        <span class="bundle-info-value">{selectedBundle.llm_profile_id || '—'}</span>
      </div>
      <div class="bundle-info-row">
        <span class="bundle-info-label">Tone Profile</span>
        <span class="bundle-info-value">{selectedBundle.tone_profile_id || '—'}</span>
      </div>
      {#if selectedBundle.system_prompt}
        <div class="bundle-info-row">
          <span class="bundle-info-label">System Prompt</span>
          <span class="bundle-info-value bundle-prompt">{selectedBundle.system_prompt}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .bundle-agent-form {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .form-label {
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  :global(.dark) .form-label { color: #9ca3af; }
  .form-input {
    padding: 6px 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 13px;
    color: #1f2937;
    background: #fff;
    transition: border-color 0.15s;
  }
  .form-input:focus {
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
  }
  :global(.dark) .form-input {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-select {
    padding: 6px 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 13px;
    color: #1f2937;
    background: #fff;
    transition: border-color 0.15s;
  }
  .form-select:focus {
    outline: none;
    border-color: #6366f1;
  }
  :global(.dark) .form-select {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-loading {
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
  }
  .bundle-info {
    padding: 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #f9fafb;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  :global(.dark) .bundle-info {
    background: #1f2937;
    border-color: #374151;
  }
  .bundle-info-row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: 12px;
  }
  .bundle-info-label {
    font-weight: 600;
    color: #6b7280;
  }
  :global(.dark) .bundle-info-label { color: #9ca3af; }
  .bundle-info-value {
    color: #374151;
    text-align: right;
    word-break: break-word;
  }
  :global(.dark) .bundle-info-value { color: #d1d5db; }
  .bundle-prompt {
    max-height: 120px;
    overflow-y: auto;
    white-space: pre-wrap;
    font-family: monospace;
    font-size: 11px;
    line-height: 1.4;
  }
</style>
