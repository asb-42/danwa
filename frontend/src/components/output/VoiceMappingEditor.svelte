<!-- VoiceMappingEditor.svelte — Specialized editor for TTS voice_mapping dict.
     Shows a table with Agent → Voice dropdowns loaded from the TTS voices API.
     Svelte 5 runes. -->
<script>
  /** @type {{ mapping: Record<string, string>, voices: Array<{voice_id: string, name: string, language: string, gender: string}>, defaultVoice: string, onchange: (m: Record<string, string>) => void }} */
  let { mapping = $bindable({}), voices = [], defaultVoice = '', onchange } = $props();

  let agentName = $state('');

  function addRow() {
    const name = agentName.trim();
    if (!name || name in mapping) return;
    mapping = { ...mapping, [name]: defaultVoice || '' };
    agentName = '';
    onchange?.(mapping);
  }

  function removeRow(key) {
    const next = { ...mapping };
    delete next[key];
    mapping = next;
    onchange?.(mapping);
  }

  function updateVoice(key, voiceId) {
    mapping = { ...mapping, [key]: voiceId };
    onchange?.(mapping);
  }
</script>

<div class="border rounded p-3 bg-gray-50 dark:bg-gray-900 space-y-2">
  <div class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
    Agent → Voice Mapping
    {#if defaultVoice}
      <span class="text-gray-400 ml-2">(default: {defaultVoice})</span>
    {/if}
  </div>

  {#if Object.keys(mapping).length > 0}
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left text-xs text-gray-500">
          <th class="pb-1">Agent</th>
          <th class="pb-1">Voice</th>
          <th class="pb-1 w-8"></th>
        </tr>
      </thead>
      <tbody>
        {#each Object.entries(mapping) as [agent, voiceId]}
          <tr class="border-t border-gray-200 dark:border-gray-700">
            <td class="py-1 pr-2 font-mono text-xs">{agent}</td>
            <td class="py-1 pr-2">
              <select
                value={voiceId}
                onchange={(e) => updateVoice(agent, e.target.value)}
                class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-xs"
              >
                {#if defaultVoice && !voiceId}
                  <option value="" selected>— default ({defaultVoice}) —</option>
                {/if}
                {#each voices as v}
                  <option value={v.voice_id} selected={v.voice_id === voiceId}>
                    {v.name} ({v.language}) [{v.gender}]
                  </option>
                {/each}
              </select>
            </td>
            <td class="py-1">
              <button
                type="button"
                onclick={() => removeRow(agent)}
                class="text-red-500 hover:text-red-700 text-xs px-1"
                title="Remove"
              >✕</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <p class="text-xs text-gray-400 italic">No voice mappings configured.</p>
  {/if}

  <!-- Add new agent -->
  <div class="flex gap-2 pt-1">
    <input
      type="text"
      bind:value={agentName}
      placeholder="Agent name (e.g. strategist)"
      class="flex-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-xs"
      onkeydown={(e) => e.key === 'Enter' && (e.preventDefault(), addRow())}
    />
    <button
      type="button"
      onclick={addRow}
      class="rounded bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 text-xs"
    >+ Add</button>
  </div>
</div>
