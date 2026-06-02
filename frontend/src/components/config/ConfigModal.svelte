<script>
  /**
   * ConfigModal — Shared modal for creating/editing LLM Profiles and Agent Personas.
   *
   * Extracted from ConfigView to reduce its size.
   */
  import { i18n } from '../../lib/i18n/index.js';
  import {
    createLLMProfile,
    updateLLMProfile,
    createAgentPersona,
    updateAgentPersona,
  } from '../../lib/api.js';

  let {
    visible = false,
    mode = 'create',
    type = 'llm',
    formData = $bindable({}),
    formErrors = $bindable({}),
    llmProfiles = [],
    onClose = () => {},
    onSaved = () => {},
  } = $props();

  let t = $derived((key, params = {}) => {
    let text = $i18n[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
    return text;
  });

  let isSaving = $state(false);
  let tagInput = $state('');

  /** Auto-generate a unique LLM profile ID from provider + model. */
  function generateLLMId() {
    const p = (formData.provider || 'llm').replace(/[^a-z0-9]/g, '');
    const m = (formData.model || 'model').split('/').pop().replace(/[^a-z0-9.-]/g, '');
    const ts = Date.now().toString(36).slice(-4);
    return `${p}-${m}-${ts}`;
  }

  /** Auto-generate agent persona ID from role + name. */
  function generateAgentId() {
    const role = (formData.role || 'agent').replace(/[^a-z0-9]/g, '');
    const name = (formData.name || 'persona').toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
    const ts = Date.now().toString(36).slice(-4);
    return name ? `${role}-${name}-${ts}` : `${role}-${ts}`;
  }

  function validateForm() {
    const errors = {};
    if (type === 'llm') {
      if (!formData.id && mode === 'create') {
        formData.id = generateLLMId();
      }
      if (!formData.name?.trim()) errors.name = t('config.required');
      if (!formData.model?.trim()) errors.model = t('config.required');
      if (formData.temperature < 0 || formData.temperature > 2) errors.temperature = '0–2';
      if (formData.max_tokens < 1) errors.max_tokens = '≥ 1';
    } else {
      if (!formData.id && mode === 'create') {
        formData.id = generateAgentId();
      }
      if (!formData.name?.trim()) errors.name = t('config.required');
      if (!formData.system_prompt?.trim()) errors.system_prompt = t('config.required');
      if (!formData.llm_profile_id) errors.llm_profile_id = t('config.required');
      if (formData.consensus_threshold < 0 || formData.consensus_threshold > 1) errors.consensus_threshold = '0–1';
    }
    formErrors = errors;
    return Object.keys(errors).length === 0;
  }

  async function handleSave() {
    if (!validateForm()) return;
    isSaving = true;
    try {
      if (type === 'llm') {
        const payload = { ...formData };
        if (!payload.api_base) payload.api_base = null;
        if (!payload.context_window) payload.context_window = null;
        if (!payload.cost_per_1k_input) payload.cost_per_1k_input = null;
        if (!payload.cost_per_1k_output) payload.cost_per_1k_output = null;

        if (mode === 'create') {
          await createLLMProfile(payload);
        } else {
          await updateLLMProfile(formData.id, payload);
        }
      } else {
        const payload = { ...formData };
        if (!payload.description) payload.description = null;

        if (mode === 'create') {
          await createAgentPersona(payload);
        } else {
          await updateAgentPersona(formData.id, payload);
        }
      }
      onSaved();
    } catch (e) {
      formErrors = { _submit: e.message };
    } finally {
      isSaving = false;
    }
  }

  function addTag() {
    const tag = tagInput.trim().toLowerCase();
    if (tag && !formData.tags?.includes(tag)) {
      formData = { ...formData, tags: [...(formData.tags || []), tag] };
    }
    tagInput = '';
  }

  function removeTag(tag) {
    formData = { ...formData, tags: (formData.tags || []).filter(t => t !== tag) };
  }
</script>

{#if visible}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onclick={onClose} role="dialog" aria-modal="true" aria-labelledby="config-modal-title" tabindex="-1">
    <div
      class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto mx-4"
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 id="config-modal-title" class="text-lg font-semibold text-gray-800 dark:text-white">
          {#if type === 'llm'}
            {mode === 'create' ? t('config.createLLM') : t('config.editLLM')}
          {:else}
            {mode === 'create' ? t('config.createPersona') : t('config.editPersona')}
          {/if}
        </h3>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none"
          onclick={onClose}
        >
          ✕
        </button>
      </div>

      <!-- Form -->
      <div class="px-6 py-4 space-y-4">
        {#if formErrors._submit}
          <p class="text-sm text-red-500">{formErrors._submit}</p>
        {/if}

        {#if type === 'llm'}
          <!-- LLM Profile Form -->
          {#if mode === 'edit' && formData.id}
            <div class="mb-2">
              <span class="text-xs text-gray-500 dark:text-gray-400">{t('config.id')}: </span>
              <code class="text-xs font-mono text-gray-600 dark:text-gray-400">{formData.id}</code>
            </div>
          {/if}
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label for="form-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.name')} *
              </label>
              <input id="form-name" type="text" bind:value={formData.name}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="My LLM Profile"
              />
              {#if formErrors.name}<p class="text-xs text-red-500 mt-1">{formErrors.name}</p>{/if}
            </div>

            <div>
              <label for="form-profile-type" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.type') || 'Typ'} *
              </label>
              <select id="form-profile-type" bind:value={formData.profile_type}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                <option value="text">Text</option>
                <option value="tts">TTS</option>
                <option value="stt">STT</option>
              </select>
            </div>

            <div>
              <label for="form-provider" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.provider')} *
              </label>
              <select id="form-provider" bind:value={formData.provider}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                <option value="openrouter">OpenRouter</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="deepseek">Deepseek</option>
                <option value="ollama">Ollama</option>
                <option value="opencode-zen">Opencode Zen</option>
                <option value="opencode-go">Opencode Go</option>
                <option value="xiaomi">Xiaomi</option>
                <option value="cloudflare">Cloudflare Workers AI</option>
                <option value="local">Local</option>
              </select>
            </div>

            <div>
              <label for="form-model" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.model')} *
              </label>
              <input id="form-model" type="text" bind:value={formData.model}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.model ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="anthropic/claude-3.5-sonnet"
              />
              {#if formErrors.model}<p class="text-xs text-red-500 mt-1">{formErrors.model}</p>{/if}
            </div>

            <div>
              <label for="form-apibase" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.apiBase')}
              </label>
              <input id="form-apibase" type="text" bind:value={formData.api_base}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="http://localhost:11434/v1"
              />
            </div>

            <div>
              <label for="form-apikey" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.apiKeyEnv')}
              </label>
              <input id="form-apikey" type="text" bind:value={formData.api_key_env}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="OPENROUTER_API_KEY"
              />
            </div>

            {#if formData.provider === 'cloudflare'}
            <div>
              <label for="form-accountid" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.accountIdEnv')}
              </label>
              <input id="form-accountid" type="text" bind:value={formData.account_id_env}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="CLOUDFLARE_ACCOUNT_ID"
              />
            </div>
            {/if}

            <div>
              <label for="form-temp" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.temperature')} *
              </label>
              <input id="form-temp" type="number" bind:value={formData.temperature}
                min="0" max="2" step="0.1"
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.temperature ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              {#if formErrors.temperature}<p class="text-xs text-red-500 mt-1">{formErrors.temperature}</p>{/if}
            </div>

            <div>
              <label for="form-maxtok" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.maxTokens')} *
              </label>
              <input id="form-maxtok" type="number" bind:value={formData.max_tokens}
                min="1" step="256"
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.max_tokens ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              {#if formErrors.max_tokens}<p class="text-xs text-red-500 mt-1">{formErrors.max_tokens}</p>{/if}
            </div>

            <div>
              <label for="form-ctx" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.contextWindow')}
              </label>
              <input id="form-ctx" type="number" bind:value={formData.context_window}
                min="0" step="1024"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="200000"
              />
            </div>

            <div>
              <label for="form-timeout" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.timeout')}
              </label>
              <input id="form-timeout" type="number" bind:value={formData.timeout}
                min="1" step="30"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            <div>
              <label for="form-costin" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.costInput')} (USD/1k)
              </label>
              <input id="form-costin" type="number" bind:value={formData.cost_per_1k_input}
                min="0" step="0.0001"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="0.003"
              />
            </div>

            <div>
              <label for="form-costout" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.costOutput')} (USD/1k)
              </label>
              <input id="form-costout" type="number" bind:value={formData.cost_per_1k_output}
                min="0" step="0.0001"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="0.015"
              />
            </div>
          </div>

        {:else}
          <!-- Agent Persona Form -->
          {#if mode === 'edit' && formData.id}
            <div class="mb-2">
              <span class="text-xs text-gray-500 dark:text-gray-400">{t('config.id')}: </span>
              <code class="text-xs font-mono text-gray-600 dark:text-gray-400">{formData.id}</code>
            </div>
          {/if}
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label for="form-agent-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.name')} *
              </label>
              <input id="form-agent-name" type="text" bind:value={formData.name}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="My Strategist"
              />
              {#if formErrors.name}<p class="text-xs text-red-500 mt-1">{formErrors.name}</p>{/if}
            </div>

            <div>
              <label for="form-agent-role" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.role')} *
              </label>
              <select id="form-agent-role" bind:value={formData.role}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                <option value="strategist">Strategist</option>
                <option value="critic">Critic</option>
                <option value="optimizer">Optimizer</option>
                <option value="moderator">Moderator</option>
              </select>
            </div>

            <div>
              <label for="form-agent-llm" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.llmProfileRef')} *
              </label>
              <select id="form-agent-llm" bind:value={formData.llm_profile_id}
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.llm_profile_id ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                {#each llmProfiles as p}
                  <option value={p.id}>{p.name} ({p.model})</option>
                {/each}
              </select>
              {#if formErrors.llm_profile_id}<p class="text-xs text-red-500 mt-1">{formErrors.llm_profile_id}</p>{/if}
            </div>

            <div>
              <label for="form-agent-rounds" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.maxRounds')}
              </label>
              <input id="form-agent-rounds" type="number" bind:value={formData.max_rounds}
                min="1" max="20"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            <div>
              <label for="form-agent-threshold" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.consensusThreshold')}
              </label>
              <input id="form-agent-threshold" type="number" bind:value={formData.consensus_threshold}
                min="0" max="1" step="0.05"
                class="w-full px-3 py-2 border rounded-lg text-sm
                  {formErrors.consensus_threshold ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              {#if formErrors.consensus_threshold}<p class="text-xs text-red-500 mt-1">{formErrors.consensus_threshold}</p>{/if}
            </div>

            <div class="md:col-span-2">
              <label for="form-agent-desc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.description')}
              </label>
              <input id="form-agent-desc" type="text" bind:value={formData.description}
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="Short description of this persona"
              />
            </div>

            <div class="md:col-span-2">
              <label for="form-agent-tags" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.tags')}
              </label>
              <div class="flex gap-2 mb-2 flex-wrap">
                {#each formData.tags || [] as tag}
                  <span class="inline-flex items-center gap-1 text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                    {tag}
                    <button class="text-gray-400 hover:text-red-500" onclick={() => removeTag(tag)}>✕</button>
                  </span>
                {/each}
              </div>
              <div class="flex gap-2">
                <input id="form-agent-tags" type="text" bind:value={tagInput}
                  class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="Add tag and press Enter"
                  onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                />
                <button
                  class="px-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
                  onclick={addTag}
                >
                  +
                </button>
              </div>
            </div>

            <div class="md:col-span-2">
              <label for="form-agent-prompt" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('config.systemPrompt')} *
              </label>
              <textarea id="form-agent-prompt" bind:value={formData.system_prompt}
                rows="6"
                class="w-full px-3 py-2 border rounded-lg text-sm font-mono resize-y
                  {formErrors.system_prompt ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'}
                  bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="You are a strategic analyst..."
              ></textarea>
              {#if formErrors.system_prompt}<p class="text-xs text-red-500 mt-1">{formErrors.system_prompt}</p>{/if}
            </div>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
        <button
          class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          onclick={onClose}
        >
          {t('common.cancel')}
        </button>
        <button
          class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors
                 disabled:opacity-50 disabled:cursor-not-allowed"
          onclick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? '...' : t('common.save')}
        </button>
      </div>
    </div>
  </div>
{/if}
