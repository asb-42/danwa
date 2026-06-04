<script>
  import { tStore } from '../lib/i18n/index.js';
  import {
    listOutputPlugins,
    startRenderJob,
    searchSessions,
  } from '../lib/output/composerApi.js';
  import { createRenderJobTracker } from '../lib/output/renderJobStore.svelte.js';
  import PluginCard from '../components/output/PluginCard.svelte';
  import ConfigForm from '../components/output/ConfigForm.svelte';
  import VoiceMappingEditor from '../components/output/VoiceMappingEditor.svelte';
  import RenderJobStatus from '../components/output/RenderJobStatus.svelte';
  import { onDestroy } from 'svelte';

  let t = $derived($tStore);

  const STORAGE_KEY = 'danwa.activeRenderJob';

  // -- MiMo TTS Style Types (categorized reference) --
  const MIMO_STYLE_TYPES = [
    {
      category: 'Basic Emotions',
      items: ['Happy', 'Sad', 'Angry', 'Fearful', 'Amazed', 'Excited', 'Wronged', 'Calm', 'Indifferent'],
    },
    {
      category: 'Complex Emotions',
      items: ['Melancholy', 'Relieved', 'Helpless', 'Guilty', 'Jealous', 'Tired', 'Apprehensive', 'Emotional'],
    },
    {
      category: 'Overall Tone',
      items: ['Gentle', 'Cold', 'Lively', 'Serious', 'Lazy', 'Playful', 'Deep', 'Capable', 'Sharp'],
    },
    {
      category: 'Timbre Positioning',
      items: ['Magnetic', 'Mellow', 'Clear', 'Ethereal', 'Innocent', 'Old', 'Sweet', 'Hoarse', 'Elegant'],
    },
    {
      category: 'Character Tone',
      items: ['Clamp voice', 'Big Sister voice', 'Shota voice', 'Uncle voice', 'Taiwanese accent'],
    },
    {
      category: 'Dialect',
      items: ['Northeast dialect', 'Sichuan dialect', 'Henan dialect', 'Cantonese'],
    },
    {
      category: 'Role-playing',
      items: ['Sun Wukong', 'Lin Daiyu'],
    },
    {
      category: 'Singing',
      items: ['singing'],
    },
  ];

  // State
  let plugins = $state([]);
  let selectedPlugin = $state(null);
  let configValues = $state({});
  let sessionSearch = $state('');
  let selectedSessionId = $state('');
  let sessionResults = $state([]);
  let showDropdown = $state(false);
  let loading = $state(false);
  let error = $state(null);
  let activeJob = $state(null);
  let tracker = $state(null);
  let searchLoading = $state(false);
  let ttsVoices = $state([]);
  let sessionAgents = $state([]);

  let searchTimeout = $state(null);

  // Derived: which voice engine is selected
  let voiceEngine = $derived(
    selectedPlugin?.plugin_key === 'tts' ? (configValues.engine || 'edge_tts') : null
  );
  let voiceLanguage = $derived(
    selectedPlugin?.plugin_key === 'tts' ? (configValues.language || '') : ''
  );

  // Derived: MiMo language warning
  let mimoWarning = $derived(
    voiceEngine === 'mimo_tts' && voiceLanguage && !['en', 'zh'].includes(voiceLanguage)
      ? `MiMo TTS unterstützt nur en und zh. Sprache "${voiceLanguage}" hat keine passenden Stimmen.`
      : null
  );

  // Derived: show style type reference for MiMo
  let showStyleTypes = $derived(voiceEngine === 'mimo_tts');

  // Load voices when TTS plugin is selected, engine changes, or language changes
  $effect(() => {
    if (!voiceEngine) return;
    const params = new URLSearchParams();
    if (voiceEngine === 'mimo_tts') params.set('engine', 'mimo_tts');
    if (voiceLanguage) params.set('language', voiceLanguage);
    fetch(`/api/v1/tts-voices?${params}`)
      .then(r => r.json())
      .then(v => { ttsVoices = v; })
      .catch(() => { ttsVoices = []; });
  });

  // Load agent roles when a session is selected
  $effect(() => {
    if (!selectedSessionId) return;
    fetch(`/api/v1/render-sessions/${selectedSessionId}/agents`)
      .then(r => r.json())
      .then(agents => {
        sessionAgents = agents;
        // Pre-populate voice_mapping with detected agent roles
        if (agents.length > 0 && selectedPlugin?.plugin_key === 'tts') {
          const mapping = {};
          for (const a of agents) {
            mapping[a.agent_name] = '';
          }
          configValues = { ...configValues, voice_mapping: mapping };
        }
      })
      .catch(() => { sessionAgents = []; });
  });

  // Restore active job from localStorage on mount
  $effect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const jobData = JSON.parse(saved);
        if (jobData && jobData.job_id) {
          activeJob = jobData;
          tracker = createRenderJobTracker(jobData.job_id);
        }
      }
    } catch (e) { if (import.meta.env.DEV) console.warn('[OutputComposerView] failed to restore active job from localStorage:', e); }

    listOutputPlugins()
      .then((p) => { plugins = p; })
      .catch((e) => { error = e.message; });
  });

  // Stop polling on destroy
  onDestroy(() => {
    if (tracker) tracker.stop();
  });

  function persistJob(jobData) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(jobData));
    } catch (e) { if (import.meta.env.DEV) console.warn('[OutputComposerView] failed to persist active job:', e); }
  }

  function clearPersistedJob() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) { if (import.meta.env.DEV) console.warn('[OutputComposerView] failed to clear persisted job:', e); }
  }

  function onSearchInput(e) {
    sessionSearch = e.target.value;
    selectedSessionId = '';
    if (searchTimeout) clearTimeout(searchTimeout);
    if (sessionSearch.length < 1) {
      sessionResults = [];
      showDropdown = false;
      return;
    }
    searchLoading = true;
    searchTimeout = setTimeout(async () => {
      try {
        sessionResults = await searchSessions(sessionSearch);
        showDropdown = sessionResults.length > 0;
      } catch {
        sessionResults = [];
      } finally {
        searchLoading = false;
      }
    }, 300);
  }

  function selectSession(s) {
    selectedSessionId = s.session_id;
    sessionSearch = s.title;
    showDropdown = false;
  }

  function onSearchBlur() {
    // Delay to allow click on dropdown item
    setTimeout(() => { showDropdown = false; }, 200);
  }

  /**
   * Initialize config values with schema defaults when a plugin is selected.
   * Ensures all fields are sent to the backend even if the user doesn't
   * touch every control.
   */
  function initDefaults(schema) {
    const props = schema.properties || {};
    const defs = schema['$defs'] || {};
    const defaults = {};
    for (const [key, rawProp] of Object.entries(props)) {
      let prop = rawProp;
      if (prop && prop['$ref']) {
        const match = prop['$ref'].match(/^#\/\$defs\/(.+)$/);
        if (match && defs[match[1]]) {
          prop = { ...defs[match[1]], ...prop };
        }
      }
      if (prop.default !== undefined) {
        defaults[key] = prop.default;
      }
    }
    return defaults;
  }

  function selectPlugin(plugin) {
    selectedPlugin = plugin;
    configValues = initDefaults(plugin.config_schema || {});
    // Ensure voice_mapping is always initialized for TTS
    if (plugin.plugin_key === 'tts' && !configValues.voice_mapping) {
      configValues.voice_mapping = {};
    }
    error = null;
  }

  function dismissJob() {
    if (tracker) tracker.stop();
    tracker = null;
    activeJob = null;
    clearPersistedJob();
  }

  async function handleGenerate() {
    if (!selectedSessionId && !sessionSearch.trim()) {
      error = 'Please select or enter a Session ID.';
      return;
    }
    if (!selectedPlugin) {
      error = 'Please select a plugin.';
      return;
    }

    loading = true;
    error = null;

    try {
      const result = await startRenderJob(
        selectedSessionId || sessionSearch.trim(),
        selectedPlugin.plugin_key,
        configValues
      );
      activeJob = result;
      persistJob(result);
      tracker = createRenderJobTracker(result.job_id);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="max-w-4xl mx-auto p-6">
  <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-6">
    🖨️ Output Composer
  </h1>

  <!-- Session Search with Autocomplete -->
  <div class="mb-6 relative">
    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="session-search">
      Session / Debate
    </label>
    <input
      id="session-search"
      type="text"
      value={sessionSearch}
      oninput={onSearchInput}
      onfocus={() => { if (sessionResults.length > 0) showDropdown = true; }}
      onblur={onSearchBlur}
      placeholder="Search by debate title or session ID…"
      autocomplete="off"
      class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-3 py-2 text-sm"
    />
    {#if searchLoading}
      <span class="absolute right-3 top-8 text-xs text-gray-400">Searching…</span>
    {/if}

    <!-- Autocomplete Dropdown -->
    {#if showDropdown && sessionResults.length > 0}
      <ul class="absolute z-10 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg max-h-60 overflow-y-auto">
        {#each sessionResults as s}
          <li>
            <button
              type="button"
              class="w-full text-left px-3 py-2 hover:bg-blue-50 dark:hover:bg-blue-900/30 text-sm border-b border-gray-100 dark:border-gray-700 last:border-b-0"
              onclick={() => selectSession(s)}
            >
              <span class="font-medium text-gray-900 dark:text-white">{s.title}</span>
              <span class="ml-2 text-xs text-gray-500 font-mono">{s.session_id}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    {#if selectedSessionId}
      <p class="mt-1 text-xs text-green-600 dark:text-green-400">
        ✓ Selected: {selectedSessionId}
      </p>
    {/if}
  </div>

  <!-- Plugin Selection -->
  <div class="mb-6">
    <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
      Select Output Format
    </h2>
    {#if plugins.length === 0}
      <p class="text-sm text-gray-500 dark:text-gray-400 italic">Loading plugins…</p>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each plugins as plugin}
          <PluginCard
            {plugin}
            selected={selectedPlugin?.plugin_key === plugin.plugin_key}
            onclick={() => selectPlugin(plugin)}
          />
        {/each}
      </div>
    {/if}
  </div>

  <!-- Config Form -->
  {#if selectedPlugin}
    <div class="mb-6">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
        Configuration — {selectedPlugin.plugin_name}
      </h2>
      <div class="p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
        <ConfigForm
          schema={selectedPlugin.config_schema}
          bind:value={configValues}
        />

        <!-- Voice Mapping Editor (TTS only) -->
        {#if selectedPlugin.plugin_key === 'tts'}
          <div class="mt-4">
            <VoiceMappingEditor
              mapping={configValues.voice_mapping || {}}
              voices={ttsVoices}
              defaultVoice={configValues.default_voice || ''}
              engine={voiceEngine}
              {sessionAgents}
              onchange={(m) => { configValues = { ...configValues, voice_mapping: m }; }}
            />
          </div>

          <!-- MiMo language warning -->
          {#if mimoWarning}
            <div class="mt-3 p-3 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20 text-xs text-amber-700 dark:text-amber-300">
              ⚠️ {mimoWarning}
            </div>
          {/if}

          <!-- MiMo Style Type Reference (collapsible) -->
          {#if showStyleTypes}
            <details class="group mt-3">
              <summary class="text-xs text-gray-500 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 list-none flex items-center gap-1 select-none">
                <span class="transition-transform group-open:rotate-90 text-xs">▶</span>
                <span class="font-medium">MiMo TTS Style Types</span>
                <span class="text-gray-400 ml-1">— Kategorie + Beispielwerte für default_style_hint</span>
              </summary>
              <div class="mt-2 space-y-3">
                {#each MIMO_STYLE_TYPES as group}
                  <div>
                    <p class="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">{group.category}</p>
                    <div class="flex flex-wrap gap-1">
                      {#each group.items as item}
                        <code class="text-xs px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 border border-blue-200 dark:border-blue-800">{item}</code>
                      {/each}
                    </div>
                  </div>
                {/each}
              </div>
            </details>
          {/if}
        {/if}
      </div>
    </div>
  {/if}

  <!-- Error -->
  {#if error}
    <div class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
      {error}
    </div>
  {/if}

  <!-- Generate Button -->
  <div class="mb-6">
    <button
      onclick={handleGenerate}
      disabled={loading || !selectedPlugin || (!selectedSessionId && !sessionSearch.trim())}
      class="px-6 py-2.5 rounded-lg bg-blue-600 text-white font-medium text-sm
        hover:bg-blue-700 disabled:hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      {#if loading}
        🔄 Starting…
      {:else}
        🚀 Generate
      {/if}
    </button>
  </div>

  <!-- Job Status -->
  {#if tracker}
    <div class="mb-6">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
          Render Job
        </h2>
        <button
          onclick={dismissJob}
          class="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          ✕ Dismiss
        </button>
      </div>
      <RenderJobStatus {tracker} />
    </div>
  {/if}
</div>
