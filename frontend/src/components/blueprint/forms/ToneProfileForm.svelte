<script>
  /**
   * ToneProfileForm — Configuration form for tone_profile workflow nodes.
   *
   * Shows:
   * - Dropdown to select a catalog profile (from /api/v1/tone-profiles)
   * - "Custom" option that reveals inline form fields
   * - Sliders for float values, Dropdowns for enums, Textarea for custom_instructions
   * - "Save to Catalog" button for inline profiles
   * - Validation: XOR between catalog and inline
   */
  import { onMount } from 'svelte';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import { listToneProfiles, createToneProfile } from '../../../lib/blueprint/api.js';

  /** @type {{ node: any, onsave?: Function, ondelete?: Function }} */
  let { node, onsave, ondelete } = $props();

  const STYLES = [
    { value: 'heated', label: '🔥 Heated' },
    { value: 'academic', label: '🎓 Academic' },
    { value: 'conversational', label: '💬 Conversational' },
    { value: 'socratic', label: '❓ Socratic' },
    { value: 'neutral', label: '⚖️ Neutral' },
  ];

  const VERBOSITIES = [
    { value: 'concise', label: 'Concise' },
    { value: 'normal', label: 'Normal' },
    { value: 'verbose', label: 'Verbose' },
  ];

  const RHETORICAL_MODES = [
    { value: 'none', label: 'None' },
    { value: 'questioning', label: 'Questioning' },
    { value: 'assertive', label: 'Assertive' },
    { value: 'dialectic', label: 'Dialectic' },
  ];

  let catalogProfiles = $state([]);
  let loading = $state(false);
  let savingToCatalog = $state(false);
  let saveMessage = $state('');

  // Form state
  let selectedMode = $state('catalog'); // 'catalog' or 'custom'
  let catalogProfileId = $state('');
  let label = $state('');
  let profileName = $state('');
  let description = $state('');
  let style = $state('neutral');
  let formality = $state(0.5);
  let verbosity = $state('normal');
  let emotionalValence = $state(0.5);
  let rhetoricalMode = $state('none');
  let customInstructions = $state('');

  // Initialize from node data
  $effect(() => {
    label = node?.data?.label || '';
    const tpId = node?.data?.tone_profile_id;
    const inline = node?.data?.inline_profile;

    if (tpId) {
      selectedMode = 'catalog';
      catalogProfileId = tpId;
    } else if (inline) {
      selectedMode = 'custom';
      profileName = inline.name || '';
      description = inline.description || '';
      style = inline.style || 'neutral';
      formality = inline.formality ?? 0.5;
      verbosity = inline.verbosity || 'normal';
      emotionalValence = inline.emotional_valence ?? 0.5;
      rhetoricalMode = inline.rhetorical_mode || 'none';
      customInstructions = inline.custom_instructions || '';
    }
  });

  let isCatalogMode = $derived(selectedMode === 'catalog');
  let isCustomMode = $derived(selectedMode === 'custom');

  onMount(async () => {
    loading = true;
    try {
      catalogProfiles = await listToneProfiles({ includeSystem: true });
    } catch (err) {
      if (import.meta.env.DEV) console.warn('[ToneProfileForm] Failed to load tone profiles:', err);
    } finally {
      loading = false;
    }
  });

  function handleSave() {
    const data = { label };

    if (selectedMode === 'catalog') {
      data.tone_profile_id = catalogProfileId || null;
      data.inline_profile = null;
      // Set display data from catalog
      const selected = catalogProfiles.find(p => p.id === catalogProfileId);
      if (selected) {
        data.profileName = selected.name;
        data.style = selected.style;
      }
    } else {
      data.tone_profile_id = null;
      data.inline_profile = {
        name: profileName || 'Custom Tone',
        description,
        style,
        formality,
        verbosity,
        emotional_valence: emotionalValence,
        rhetorical_mode: rhetoricalMode,
        custom_instructions: customInstructions || null,
      };
      data.profileName = profileName || 'Custom Tone';
      data.style = style;
    }

    canvasStore.updateNodeData(node.id, data);
    onsave?.(data);
  }

  async function handleSaveToCatalog() {
    savingToCatalog = true;
    saveMessage = '';
    try {
      const newProfile = {
        name: profileName || 'Custom Tone',
        description,
        style,
        formality,
        verbosity,
        emotional_valence: emotionalValence,
        rhetorical_mode: rhetoricalMode,
        custom_instructions: customInstructions || null,
      };
      const created = await createToneProfile(newProfile);
      // Switch to catalog mode with the new profile
      catalogProfiles = [...catalogProfiles, created];
      catalogProfileId = created.id;
      selectedMode = 'catalog';
      handleSave();
      saveMessage = 'Saved to catalog!';
    } catch (err) {
      saveMessage = `Error: ${err.message}`;
    } finally {
      savingToCatalog = false;
    }
  }

  function handleModeChange(newMode) {
    selectedMode = newMode;
    if (newMode === 'catalog') {
      // Clear inline data
      canvasStore.updateNodeData(node.id, { inline_profile: null });
    } else {
      // Clear catalog reference
      canvasStore.updateNodeData(node.id, { tone_profile_id: null });
    }
    handleSave();
  }
</script>

<div class="tone-profile-form" data-testid="tone-profile-form">
  <!-- Label -->
  <div class="form-group">
    <label class="form-label" for="tp-label">Label</label>
    <input
      id="tp-label"
      type="text"
      class="form-input"
      bind:value={label}
      placeholder="Node label"
      onblur={handleSave}
    />
  </div>

  <!-- Mode selector -->
  <div class="form-group">
    <span class="form-label">Source</span>
    <div class="mode-toggle">
      <button
        class="mode-btn"
        class:active={isCatalogMode}
        onclick={() => handleModeChange('catalog')}
      >
        Catalog
      </button>
      <button
        class="mode-btn"
        class:active={isCustomMode}
        onclick={() => handleModeChange('custom')}
      >
        Custom
      </button>
    </div>
  </div>

  <!-- Catalog mode: dropdown -->
  {#if isCatalogMode}
    <div class="form-group">
      <label class="form-label" for="tp-catalog">Profile</label>
      {#if loading}
        <div class="form-loading">Loading profiles...</div>
      {:else}
        <select
          id="tp-catalog"
          class="form-select"
          bind:value={catalogProfileId}
          onchange={handleSave}
        >
          <option value="">— None —</option>
          {#each catalogProfiles as p}
            <option value={p.id}>
              {p.is_system ? '🔒 ' : ''}{p.name} ({p.style})
            </option>
          {/each}
        </select>
      {/if}
    </div>
  {/if}

  <!-- Custom mode: inline fields -->
  {#if isCustomMode}
    <div class="form-group">
      <label class="form-label" for="tp-name">Profile Name</label>
      <input
        id="tp-name"
        type="text"
        class="form-input"
        bind:value={profileName}
        placeholder="e.g. Heated Debate"
        onblur={handleSave}
      />
    </div>

    <div class="form-group">
      <label class="form-label" for="tp-desc">Description</label>
      <textarea
        id="tp-desc"
        class="form-textarea"
        bind:value={description}
        placeholder="Describe the tone..."
        rows="2"
        onblur={handleSave}
      ></textarea>
    </div>

    <div class="form-group">
      <label class="form-label" for="tp-style">Style</label>
      <select id="tp-style" class="form-select" bind:value={style} onchange={handleSave}>
        {#each STYLES as s}
          <option value={s.value}>{s.label}</option>
        {/each}
      </select>
    </div>

    <div class="form-group">
      <label class="form-label" for="tp-formality">
        Formality: {formality.toFixed(2)}
      </label>
      <input
        id="tp-formality"
        type="range"
        min="0" max="1" step="0.05"
        bind:value={formality}
        oninput={handleSave}
        class="form-slider"
      />
      <div class="slider-labels">
        <span>Informal</span>
        <span>Formal</span>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label" for="tp-verbosity">Verbosity</label>
      <select id="tp-verbosity" class="form-select" bind:value={verbosity} onchange={handleSave}>
        {#each VERBOSITIES as v}
          <option value={v.value}>{v.label}</option>
        {/each}
      </select>
    </div>

    <div class="form-group">
      <label class="form-label" for="tp-emotion">
        Emotional Valence: {emotionalValence.toFixed(2)}
      </label>
      <input
        id="tp-emotion"
        type="range"
        min="0" max="1" step="0.05"
        bind:value={emotionalValence}
        oninput={handleSave}
        class="form-slider"
      />
      <div class="slider-labels">
        <span>Calm</span>
        <span>Intense</span>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label" for="tp-rhetorical">Rhetorical Mode</label>
      <select id="tp-rhetorical" class="form-select" bind:value={rhetoricalMode} onchange={handleSave}>
        {#each RHETORICAL_MODES as r}
          <option value={r.value}>{r.label}</option>
        {/each}
      </select>
    </div>

    <div class="form-group">
      <label class="form-label" for="tp-custom">Custom Instructions</label>
      <textarea
        id="tp-custom"
        class="form-textarea"
        bind:value={customInstructions}
        placeholder="Additional tone instructions..."
        rows="3"
        onblur={handleSave}
      ></textarea>
    </div>

    <!-- Save to Catalog button -->
    <div class="form-group">
      <button
        class="save-catalog-btn"
        onclick={handleSaveToCatalog}
        disabled={savingToCatalog}
      >
        {savingToCatalog ? 'Saving...' : '💾 Save to Catalog'}
      </button>
      {#if saveMessage}
        <span class="save-message" class:error={saveMessage.startsWith('Error')}>
          {saveMessage}
        </span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .tone-profile-form {
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
  .form-input,
  .form-select,
  .form-textarea {
    padding: 6px 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 13px;
    color: #1f2937;
    background: #fff;
    transition: border-color 0.15s;
  }
  .form-input:focus,
  .form-select:focus,
  .form-textarea:focus {
    outline: none;
    border-color: #f59e0b;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.15);
  }
  :global(.dark) .form-input,
  :global(.dark) .form-select,
  :global(.dark) .form-textarea {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }
  .form-textarea {
    resize: vertical;
    font-family: inherit;
  }
  .form-slider {
    width: 100%;
    accent-color: #f59e0b;
  }
  .slider-labels {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: #9ca3af;
  }
  .form-loading {
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
  }

  /* Mode toggle */
  .mode-toggle {
    display: flex;
    gap: 0;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    overflow: hidden;
  }
  :global(.dark) .mode-toggle { border-color: #4b5563; }
  .mode-btn {
    flex: 1;
    padding: 6px 12px;
    border: none;
    background: transparent;
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .mode-btn.active {
    background: #f59e0b;
    color: white;
  }
  .mode-btn:hover:not(.active) {
    background: #fef3c7;
  }
  :global(.dark) .mode-btn:hover:not(.active) {
    background: #451a03;
  }

  .save-catalog-btn {
    padding: 8px 12px;
    border: 1px solid #f59e0b;
    border-radius: 6px;
    background: #fffbeb;
    color: #92400e;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .save-catalog-btn:hover:not(:disabled) {
    background: #f59e0b;
    color: white;
  }
  .save-catalog-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  :global(.dark) .save-catalog-btn {
    background: #451a03;
    border-color: #d97706;
    color: #fbbf24;
  }
  .save-message {
    font-size: 11px;
    color: #10b981;
    margin-top: 4px;
  }
  .save-message.error {
    color: #ef4444;
  }
</style>
