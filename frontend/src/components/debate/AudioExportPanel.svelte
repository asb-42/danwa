<script>
  /**
   * AudioExportPanel — TTS audio export for a completed debate session.
   *
   * Self-contained: loads engines, voices, session agents; allows engine,
   * format, language, default voice and optional per-agent voice overrides;
   * starts a render job, polls status, then triggers download.
   */
  import { onDestroy } from 'svelte';
  import {
    startTtsRenderJob,
    getTtsEngines,
    getTtsVoices,
    getSessionAgents,
    getRenderJobStatus,
    getRenderDownloadUrl,
  } from '../../lib/workflowExec.js';

  let {
    sessionId = null,
    initiallyOpen = false,
  } = $props();

  // ─── State ─────────────────────────────────────────────────────────
  let isOpen = $state(false);
  let engines = $state([]);
  let voices = $state([]);
  let agents = $state([]);
  /** Per-agent voice overrides keyed by agent_name (empty = default). */
  let voiceMap = $state({});
  let engine = $state('');
  let defaultVoice = $state('');
  let format = $state('mp3');
  let language = $state('de');
  let loading = $state(false);
  let error = $state('');
  let jobId = $state(null);
  let polling = $state(null);
  let enginesLoading = $state(false);
  let voicesLoading = $state(false);
  let dataLoaded = $state(false);

  const FORMATS = ['mp3', 'wav'];
  const LANGUAGES = ['de', 'en'];

  $effect(() => { if (initiallyOpen && !isOpen) toggleOpen(); });

  async function toggleOpen() {
    isOpen = !isOpen;
    if (isOpen && !dataLoaded) {
      dataLoaded = true;
      await loadAll();
    }
  }

  async function loadAll() {
    error = '';
    enginesLoading = true;
    try {
      const list = await getTtsEngines();
      engines = Array.isArray(list) ? list : [];
      if (!engine && engines.length > 0) {
        const firstAvailable = engines.find((e) => e.available);
        engine = (firstAvailable || engines[0]).engine_id;
      }
    } catch (err) {
      error = err?.message || 'Failed to load TTS engines';
    } finally {
      enginesLoading = false;
    }
    if (sessionId) {
      try {
        const list = await getSessionAgents(sessionId);
        agents = Array.isArray(list) ? list : [];
        const map = {};
        for (const a of agents) map[a.agent_name] = '';
        voiceMap = map;
      } catch {
        // Mapping pre-fill is best-effort.
      }
    }
  }

  // Reload voices when engine (or language) changes; pre-fill defaultVoice
  $effect(() => {
    if (!engine || !isOpen) { voices = []; return; }
    let cancelled = false;
    voicesLoading = true;
    getTtsVoices(engine, {})
      .then((list) => {
        if (cancelled) return;
        voices = Array.isArray(list) ? list : [];
        if (!defaultVoice && voices.length > 0) {
          const pref = voices.find((v) => v.language && v.language.startsWith(language))?.voice_id;
          defaultVoice = pref || voices[0].voice_id;
        }
      })
      .catch(() => { if (!cancelled) voices = []; })
      .finally(() => { if (!cancelled) voicesLoading = false; });
    return () => { cancelled = true; };
  });
  // Re-assign default voice when language changes (falls defaultVoice leer)
  $effect(() => {
    if (voices.length > 0 && !defaultVoice) {
      const pref = voices.find((v) => v.language && v.language.startsWith(language))?.voice_id;
      defaultVoice = pref || voices[0].voice_id;
    }
  });

  const selectedEngine = $derived(engines.find((e) => e.engine_id === engine) || null);

  const TTS_FALLBACK_VOICE = 'de-DE-KatjaNeural';

  async function handleStart() {
    if (!sessionId || loading) return;
    loading = true;
    error = '';
    jobId = null;
    try {
      const overrides = {};
      for (const [name, voice] of Object.entries(voiceMap)) {
        if (voice) overrides[name] = voice;
      }
      const res = await startTtsRenderJob(sessionId, {
        engine,
        output_format: format,
        language,
        default_voice: defaultVoice || TTS_FALLBACK_VOICE,
        voice_mapping: overrides,
      });
      jobId = res.job_id;
      polling = setInterval(async () => {
        try {
          const st = await getRenderJobStatus(jobId);
          if (st.status === 'completed') {
            clearInterval(polling); polling = null; loading = false;
            const url = getRenderDownloadUrl(jobId);
            const a = document.createElement('a');
            a.href = url; a.download = '';
            document.body.appendChild(a); a.click(); a.remove();
          } else if (st.status === 'failed') {
            clearInterval(polling); polling = null; loading = false;
            error = st.error_message || 'Audio export failed';
          }
        } catch (err) {
          clearInterval(polling); polling = null; loading = false;
          error = err?.message || 'Failed to check audio export status';
        }
      }, 2000);
    } catch (err) {
      loading = false;
      error = err?.message || 'Failed to start audio export';
    }
  }

  function setAgentVoice(name, value) {
    voiceMap = { ...voiceMap, [name]: value };
  }

  onDestroy(() => { if (polling) clearInterval(polling); });
</script>

<div class="audio-export-panel">
  <button
    class="audio-toggle"
    type="button"
    onclick={toggleOpen}
    aria-expanded={isOpen}
  >
    🔊 {isOpen ? 'Hide audio export' : 'Audio export (TTS)'}
  </button>

  {#if isOpen}
    <div class="audio-body">
      {#if enginesLoading}
        <div class="audio-hint">⏳ Loading TTS engines…</div>
      {:else if engines.length === 0}
        <div class="audio-error">No TTS engines available.</div>
      {:else}
        <div class="audio-grid">
          <label class="audio-field">
            <span class="audio-label">Engine</span>
            <select class="audio-select" bind:value={engine} disabled={loading}>
              {#each engines as eng (eng.engine_id)}
                <option value={eng.engine_id} disabled={eng.available === false}>
                  {eng.display_name}{eng.available === false ? ' (unavailable)' : ''}
                </option>
              {/each}
            </select>
          </label>

          <label class="audio-field">
            <span class="audio-label">Format</span>
            <select class="audio-select" bind:value={format} disabled={loading}>
              {#each FORMATS as f (f)}<option value={f}>{f.toUpperCase()}</option>{/each}
            </select>
          </label>

          <label class="audio-field">
            <span class="audio-label">Language</span>
            <select class="audio-select" bind:value={language} disabled={loading}>
              {#each LANGUAGES as l (l)}<option value={l}>{l === 'de' ? 'Deutsch' : 'English'}</option>{/each}
            </select>
          </label>
        </div>

        {#if selectedEngine?.license?.name}
          <div class="audio-license">
            ⚖️ <strong>{selectedEngine.license.name}</strong>
            {#if selectedEngine.license.type === 'non-commercial'}
              — Non-commercial use only{#if selectedEngine.license.url}. <a href={selectedEngine.license.url} target="_blank" rel="noopener noreferrer">License ↗</a>{/if}
            {/if}
          </div>
        {/if}
        {#if selectedEngine?.license?.attribution}
          <div class="audio-attribution">{selectedEngine.license.attribution}</div>
        {/if}

        <label class="audio-field">
          <span class="audio-label">Default voice</span>
          {#if voicesLoading}
            <span class="audio-hint">⏳ Loading voices…</span>
          {:else if voices.length > 0}
            <select class="audio-select" bind:value={defaultVoice} disabled={loading}>
              {#each voices as v (v.voice_id)}
                <option value={v.voice_id}>{v.name || v.voice_id}{v.language ? ` (${v.language})` : ''}</option>
              {/each}
            </select>
          {:else}
            <input class="audio-select" type="text" bind:value={defaultVoice}
              placeholder="Voice ID (e.g. de-DE-KatjaNeural)" disabled={loading} />
          {/if}
        </label>

        {#if agents.length > 0 && voices.length > 0}
          <div class="audio-agents">
            <div class="audio-agents-title">Voice per agent (optional)</div>
            {#each agents as agent (agent.agent_name)}
              <div class="audio-agent-row">
                <span class="audio-agent-name" title={agent.role_type}>{agent.agent_name}</span>
                <select class="audio-select"
                  value={voiceMap[agent.agent_name] ?? ''}
                  onchange={(e) => setAgentVoice(agent.agent_name, e.currentTarget.value)}
                  disabled={loading}>
                  <option value="">— default —</option>
                  {#each voices as v (v.voice_id)}
                    <option value={v.voice_id}>{v.name || v.voice_id}</option>
                  {/each}
                </select>
              </div>
            {/each}
          </div>
        {/if}

        <div class="audio-actions">
          <button
            type="button"
            class="audio-start"
            onclick={handleStart}
            disabled={loading || !sessionId || !engine || (selectedEngine?.available === false)}
          >
            {loading ? '⏳ Generating…' : '⬇ Generate Audio'}
          </button>
        </div>
      {/if}

      {#if error}
        <div class="audio-error">{error}</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .audio-export-panel {
    margin-top: 8px;
    border-top: 1px dashed #e2e8f0;
    padding-top: 8px;
  }
  :global(.dark) .audio-export-panel { border-color: #374151; }
  .audio-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    font-size: 12px;
    border-radius: 6px;
    background: transparent;
    border: 1px solid #cbd5e1;
    color: #475569;
    cursor: pointer;
  }
  .audio-toggle:hover { background: #f1f5f9; }
  :global(.dark) .audio-toggle { border-color: #475569; color: #cbd5e1; }
  :global(.dark) .audio-toggle:hover { background: #1f2937; }
  .audio-body { margin-top: 8px; }
  .audio-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 8px;
  }
  .audio-field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
  .audio-label { font-size: 11px; font-weight: 600; color: #6b7280; }
  :global(.dark) .audio-label { color: #9ca3af; }
  .audio-select {
    padding: 5px 8px;
    font-size: 12px;
    border-radius: 6px;
    border: 1px solid #cbd5e1;
    background: #fff;
    color: #0f172a;
  }
  :global(.dark) .audio-select { background: #1f2937; border-color: #475569; color: #e5e7eb; }
  .audio-license {
    margin-top: 4px;
    padding: 6px 8px;
    border-radius: 6px;
    background: #fffbeb;
    border: 1px solid #fcd34d;
    font-size: 11px;
    color: #92400e;
  }
  :global(.dark) .audio-license {
    background: rgba(120, 53, 15, 0.25);
    border-color: #78350f;
    color: #fbbf24;
  }
  .audio-license a { color: inherit; text-decoration: underline; }
  .audio-attribution { font-size: 11px; font-style: italic; color: #6b7280; margin-top: 4px; }
  :global(.dark) .audio-attribution { color: #9ca3af; }
  .audio-agents { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
  .audio-agents-title { font-size: 11px; font-weight: 600; color: #6b7280; }
  :global(.dark) .audio-agents-title { color: #9ca3af; }
  .audio-agent-row { display: flex; align-items: center; gap: 8px; }
  .audio-agent-name {
    flex: 0 0 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: 12px; color: #374151;
  }
  :global(.dark) .audio-agent-name { color: #d1d5db; }
  .audio-actions { margin-top: 8px; display: flex; justify-content: flex-end; }
  .audio-start {
    padding: 6px 12px;
    font-size: 12px;
    border-radius: 6px;
    background: #2563eb;
    color: #fff;
    border: none;
    cursor: pointer;
  }
  .audio-start:hover:not(:disabled) { background: #1d4ed8; }
  .audio-start:disabled { opacity: 0.5; cursor: not-allowed; }
  .audio-error { margin-top: 6px; font-size: 12px; color: #ef4444; }
  :global(.dark) .audio-error { color: #f87171; }
  .audio-hint { font-size: 12px; color: #6b7280; }
</style>
