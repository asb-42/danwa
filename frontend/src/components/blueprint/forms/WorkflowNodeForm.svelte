<script>
  /**
   * WorkflowNodeForm — Generic form for all workflow node types.
   *
   * Shows: label (editable), node type (read-only), linked AgentBlueprint.
   * For agent nodes: AgentBlueprint selector dropdown (fetched from API).
   * For gate nodes: condition text input.
   * For user-injection nodes: input_type selector.
   * For agent nodes: argumentation_pattern and mode dropdowns.
   * Save updates node data via canvasStore.updateNodeData().
   */
  import { onMount } from 'svelte';
  import { canvasStore } from '../../../lib/blueprint/store.svelte.js';
  import { listAgentBlueprints, listArgumentationPatterns } from '../../../lib/blueprint/api.js';

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

  const MODE_OPTIONS = [
    { value: '', label: '— None —' },
    { value: 'interviewer', label: 'Interviewer' },
    { value: 'advocate', label: 'Advocate' },
    { value: 'adversary', label: 'Adversary' },
    { value: 'mediator', label: 'Mediator' },
    { value: 'referee', label: 'Referee' },
    { value: 'facilitator', label: 'Facilitator' },
    { value: 'devils_advocate', label: "Devil's Advocate" },
  ];

  let label = $state('');
  let agentBlueprintId = $state('');
  let condition = $state('');
  let inputType = $state('user_query');
  let argumentationPattern = $state('');
  let mode = $state('');
  let blueprints = $state([]);
  let availablePatterns = $state([]);
  let loading = $state(false);

  $effect(() => {
    label = node?.data?.label || '';
    agentBlueprintId = node?.data?.agent_blueprint_id || '';
    condition = node?.data?.config?.condition || node?.data?.condition || '';
    inputType = node?.data?.config?.input_type || node?.data?.input_type || 'user_query';
    argumentationPattern = node?.data?.argumentation_pattern || '';
    mode = node?.data?.mode || '';
  });

  let isAgentNode = $derived(AGENT_NODE_TYPES.includes(node?.type));
  let isGateNode = $derived(node?.type === 'wf-gate');
  let isUserInjectionNode = $derived(node?.type === 'wf-user-injection');

  onMount(async () => {
    if (isAgentNode) {
      loading = true;
      try {
        blueprints = await listAgentBlueprints({ active_only: true });
        availablePatterns = await listArgumentationPatterns();
      } catch (err) {
        if (import.meta.env.DEV) console.warn('[WorkflowNodeForm] Failed to load blueprints/patterns:', err);
      } finally {
        loading = false;
      }
    }
  });

  function handleSave() {
    const data = { label };
    if (isAgentNode) {
      data.agent_blueprint_id = agentBlueprintId || null;
      data.argumentation_pattern = argumentationPattern || null;
      data.mode = mode || null;
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

  <!-- Agent Blueprint selector (for agent nodes) -->
  {#if isAgentNode}
    <div class="form-group">
      <label class="form-label" for="wf-blueprint">Agent Blueprint</label>
      {#if loading}
        <div class="form-loading">Loading blueprints...</div>
      {:else}
        <select
          id="wf-blueprint"
          class="form-select"
          bind:value={agentBlueprintId}
          onchange={handleSave}
        >
          <option value="">— None —</option>
          {#each blueprints as bp}
            <option value={bp.id}>{bp.name} ({bp.id})</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- Argumentation Pattern selector (for agent nodes) -->
    <div class="form-group">
      <label class="form-label" for="wf-arg-pattern">Argumentation Pattern</label>
      {#if loading && availablePatterns.length === 0}
        <div class="form-loading">Loading patterns...</div>
      {:else}
        <select
          id="wf-arg-pattern"
          class="form-select"
          bind:value={argumentationPattern}
          onchange={handleSave}
        >
          <option value="">— Default —</option>
          {#each availablePatterns as pattern}
            <option value={pattern}>{pattern}</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- Mode selector (for agent nodes) -->
    <div class="form-group">
      <label class="form-label" for="wf-mode">Mode</label>
      <select
        id="wf-mode"
        class="form-select"
        bind:value={mode}
        onchange={handleSave}
      >
        {#each MODE_OPTIONS as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
      </select>
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
