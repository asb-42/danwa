<script>
  /**
   * WorkflowNodeForm — Generic form for all workflow node types.
   *
   * Shows: label (editable), node type (read-only), and module-entity selectors.
   * For agent nodes: Agent Core, LLM Profile, Tone Profile, Prompt Modifier,
   *   and Argumentation Pattern dropdowns (all sourced from listComposerComponents).
   * For gate nodes: condition text input.
   * For user-injection nodes: input_type selector.
   * Save updates node data via canvasStore.updateNodeData().
   */
  import { onMount } from 'svelte';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import { listComposerComponents } from '../../../lib/blueprint/api.js';

  /** @type {{ node: any, onsave?: Function, ondelete?: Function }} */
  let { node, onsave, ondelete } = $props();

  const AGENT_NODE_TYPES = [
    'wf-strategist', 'wf-critic', 'wf-fact-checker',
    'wf-optimizer', 'wf-moderator', 'wf-analyst', 'wf-creative',
    'wf-socratic-questioner', 'wf-expert-reviewer', 'wf-steel-manner',
    'wf-devils-advocate', 'wf-troll', 'wf-mediator', 'wf-ethicist', 'wf-synthesizer',
    'wf-builder', 'wf-pragmatist', 'wf-angels-advocate',
  ];

  const NODE_TYPE_LABELS = {
    'wf-input': '📥 Input',
    'wf-initialize': '🚀 Initialize',
    'wf-strategist': '🧠 Strategist',
    'wf-critic': '🔍 Critic',
    'wf-fact-checker': '✅ Fact Checker',
    'wf-optimizer': '⚡ Optimizer',
    'wf-moderator': '🎯 Moderator',
    'wf-analyst': '📊 Analyst',
    'wf-creative': '💡 Creative',
    'wf-socratic-questioner': '❓ Socratic Questioner',
    'wf-expert-reviewer': '🔬 Expert Reviewer',
    'wf-steel-manner': '🛡️ Steel Manner',
    'wf-devils-advocate': '👿 Devil\'s Advocate',
    'wf-troll': '🤡 Troll',
    'wf-mediator': '🤝 Mediator',
    'wf-ethicist': '⚖️ Ethicist',
    'wf-synthesizer': '🔗 Synthesizer',
    'wf-user-injection': '👤 User Injection',
    'wf-gate': '🔀 Gate',
    'wf-builder': '🔨 Builder',
    'wf-pragmatist': '⚖️ Pragmatist',
    'wf-angels-advocate': "🛡️ Angel's Advocate",
  };

  const INPUT_TYPES = [
    { value: 'user_query', label: 'User Query' },
    { value: 'oob_input', label: 'OOB Input' },
    { value: 'external_event', label: 'External Event' },
  ];

  // ─── State ────────────────────────────────────────────────────────
  let label = $state('');
  let agentBlueprintId = $state('');
  let condition = $state('');
  let inputType = $state('user_query');
  let argumentationPattern = $state('');
  let llmProfileId = $state('');
  let toneProfileId = $state('');
  let promptModifierId = $state('');

  // Component lists from the API
  let agentCores = $state([]);
  let llmProfiles = $state([]);
  let toneProfiles = $state([]);
  let promptModifiers = $state([]);
  let argumentationPatterns = $state([]);
  let loading = $state(false);

  // ─── Reactive sync from node data ─────────────────────────────────
  $effect(() => {
    label = node?.data?.label || '';
    agentBlueprintId = node?.data?.agent_blueprint_id || '';
    condition = node?.data?.config?.condition || node?.data?.condition || '';
    inputType = node?.data?.config?.input_type || node?.data?.input_type || 'user_query';
    argumentationPattern = node?.data?.config?.argumentation_pattern || node?.data?.argumentation_pattern || '';
    llmProfileId = node?.data?.config?.llm_profile_id || '';
    toneProfileId = node?.data?.config?.tone_profile_id || '';
    promptModifierId = node?.data?.config?.prompt_modifier_id || '';
  });

  let isAgentNode = $derived(AGENT_NODE_TYPES.includes(node?.type));
  let isGateNode = $derived(node?.type === 'wf-gate');
  let isUserInjectionNode = $derived(node?.type === 'wf-user-injection');

  // ─── Load components on mount ─────────────────────────────────────
  onMount(async () => {
    if (isAgentNode) {
      loading = true;
      try {
        const components = await listComposerComponents();
        agentCores = components.agent_cores || [];
        llmProfiles = components.llm_profiles || [];
        toneProfiles = components.tone_profiles || [];
        promptModifiers = components.prompt_modifiers || [];
        argumentationPatterns = components.argumentation_patterns || [];
      } catch (err) {
        if (import.meta.env.DEV) console.warn('[WorkflowNodeForm] Failed to load composer components:', err);
      } finally {
        loading = false;
      }
    }
  });

  // ─── Save ─────────────────────────────────────────────────────────
  function handleSave() {
    const data = { label };
    if (isAgentNode) {
      // agent_blueprint_id stores the agent-core module UUID
      data.agent_blueprint_id = agentBlueprintId || null;
      // Composition component IDs go into config
      data.config = {
        ...(node?.data?.config || {}),
        argumentation_pattern: argumentationPattern || null,
        llm_profile_id: llmProfileId || null,
        tone_profile_id: toneProfileId || null,
        prompt_modifier_id: promptModifierId || null,
      };
      // Remove legacy mode if present
      delete data.mode;
    }
    if (isGateNode) {
      data.config = { ...(node?.data?.config || {}), condition };
    }
    if (isUserInjectionNode) {
      data.config = { ...(node?.data?.config || {}), input_type: inputType };
    }
    canvasStore.updateNodeData(node.id, data);
    onsave?.(data);
  }
</script>

<div class="workflow-node-form" data-testid="workflow-node-form">
  <!-- Node type (read-only) -->
  <div class="form-group">
    <span class="form-label">Type</span>
    <div class="form-value">{NODE_TYPE_LABELS[node?.type] || node?.type}</div>
  </div>

  <!-- Label (editable) -->
  <div class="form-group">
    <label class="form-label" for="wf-label">Label</label>
    <input
      id="wf-label"
      type="text"
      class="form-input"
      bind:value={label}
      placeholder="Node label"
      onblur={handleSave}
    />
  </div>

  <!-- Agent Core selector (for agent nodes) -->
  {#if isAgentNode}
    <div class="form-group">
      <label class="form-label" for="wf-agent-core">Agent Core</label>
      {#if loading}
        <div class="form-loading">Loading components...</div>
      {:else}
        <select
          id="wf-agent-core"
          class="form-select"
          bind:value={agentBlueprintId}
          onchange={handleSave}
        >
          <option value="">— None —</option>
          {#each agentCores as ac}
            <option value={ac.id}>{ac.name} ({ac.role || ac.id})</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- LLM Profile selector -->
    <div class="form-group">
      <label class="form-label" for="wf-llm-profile">LLM Profile</label>
      {#if loading}
        <div class="form-loading">Loading profiles...</div>
      {:else}
        <select
          id="wf-llm-profile"
          class="form-select"
          bind:value={llmProfileId}
          onchange={handleSave}
        >
          <option value="">— Default —</option>
          {#each llmProfiles as lp}
            <option value={lp.id}>{lp.name} ({lp.model || lp.provider})</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- Argumentation Pattern selector -->
    <div class="form-group">
      <label class="form-label" for="wf-arg-pattern">Argumentation Pattern</label>
      {#if loading && argumentationPatterns.length === 0}
        <div class="form-loading">Loading patterns...</div>
      {:else}
        <select
          id="wf-arg-pattern"
          class="form-select"
          bind:value={argumentationPattern}
          onchange={handleSave}
        >
          <option value="">— Default —</option>
          {#each argumentationPatterns as pattern}
            <option value={pattern.id}>{pattern.name}</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- Tone Profile selector -->
    <div class="form-group">
      <label class="form-label" for="wf-tone-profile">Tone Profile</label>
      {#if loading}
        <div class="form-loading">Loading profiles...</div>
      {:else}
        <select
          id="wf-tone-profile"
          class="form-select"
          bind:value={toneProfileId}
          onchange={handleSave}
        >
          <option value="">— None —</option>
          {#each toneProfiles as tp}
            <option value={tp.id}>{tp.name} ({tp.style || tp.id})</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- Prompt Modifier selector -->
    <div class="form-group">
      <label class="form-label" for="wf-prompt-modifier">Prompt Modifier</label>
      {#if loading}
        <div class="form-loading">Loading modifiers...</div>
      {:else}
        <select
          id="wf-prompt-modifier"
          class="form-select"
          bind:value={promptModifierId}
          onchange={handleSave}
        >
          <option value="">— None —</option>
          {#each promptModifiers as pm}
            <option value={pm.id}>{pm.name}</option>
          {/each}
        </select>
      {/if}
    </div>
  {/if}

  <!-- Condition input (for gate nodes) -->
  {#if isGateNode}
    <div class="form-group">
      <label class="form-label" for="wf-condition">Condition</label>
      <input
        id="wf-condition"
        type="text"
        class="form-input"
        bind:value={condition}
        placeholder="e.g. round >= 3"
        onblur={handleSave}
      />
    </div>
  {/if}

  <!-- Input type selector (for user-injection nodes) -->
  {#if isUserInjectionNode}
    <div class="form-group">
      <label class="form-label" for="wf-input-type">Input Type</label>
      <select
        id="wf-input-type"
        class="form-select"
        bind:value={inputType}
        onchange={handleSave}
      >
        {#each INPUT_TYPES as it}
          <option value={it.value}>{it.label}</option>
        {/each}
      </select>
    </div>
  {/if}
</div>

<style>
  .workflow-node-form {
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
  .form-value {
    font-size: 13px;
    color: #374151;
    font-weight: 500;
  }
  :global(.dark) .form-value { color: #d1d5db; }
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
</style>
