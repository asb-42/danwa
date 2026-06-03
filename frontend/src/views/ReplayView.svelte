<script>
  import { onMount, onDestroy } from 'svelte';
  import { routeParams } from '../lib/stores.js';
  import { tStore } from '../lib/i18n/index.js';
  import { getAuditLog, getWorkflowSessions } from '../lib/workflow/auditApi.js';
  import WorkflowCanvas from '../components/workflow/WorkflowCanvas.svelte';
  import ReplayControls from '../components/workflow/ReplayControls.svelte';
  import ReplayNodeDetail from '../components/workflow/ReplayNodeDetail.svelte';

  let sessions = $state([]);
  let selectedSessionId = $state($routeParams[0] || '');
  let auditLog = $state([]);
  let currentStep = $state(0);
  let isPlaying = $state(false);
  let playSpeed = $state(1);
  let playInterval = $state(null);
  let selectedNode = $state(null);
  let error = $state(null);
  let loading = $state(false);

  let t = $derived($tStore);

  onMount(async () => {
    try {
      sessions = await getWorkflowSessions(null, { status: 'completed', limit: 50 });
    } catch (e) {
      error = e.message;
    }
    if (selectedSessionId) {
      await loadSession(selectedSessionId);
    }
  });

  onDestroy(() => {
    stopPlayback();
  });

  async function loadSession(sessionId) {
    loading = true;
    error = null;
    try {
      auditLog = await getAuditLog(sessionId, { limit: 1000 });
      currentStep = 0;
      updateSelectedNode();
    } catch (e) {
      error = e.message;
      auditLog = [];
    }
    loading = false;
  }

  function updateSelectedNode() {
    if (auditLog.length === 0) {
      selectedNode = null;
      return;
    }
    const entry = auditLog[currentStep];
    selectedNode = entry
      ? { ...entry, step: currentStep + 1, total: auditLog.length }
      : null;
  }

  function stepForward() {
    if (currentStep < auditLog.length - 1) {
      currentStep++;
      updateSelectedNode();
    } else {
      stopPlayback();
    }
  }

  function stepBack() {
    if (currentStep > 0) {
      currentStep--;
      updateSelectedNode();
    }
  }

  function togglePlayback() {
    isPlaying = !isPlaying;
    if (isPlaying) {
      playInterval = setInterval(stepForward, 1000 / playSpeed);
    } else {
      stopPlayback();
    }
  }

  function stopPlayback() {
    isPlaying = false;
    if (playInterval) {
      clearInterval(playInterval);
      playInterval = null;
    }
  }

  function onSliderChange(e) {
    currentStep = parseInt(e.target.value, 10);
    updateSelectedNode();
  }

  function onSpeedChange(e) {
    playSpeed = parseFloat(e.target.value);
    if (isPlaying) {
      stopPlayback();
      playInterval = setInterval(stepForward, 1000 / playSpeed);
    }
  }

  async function onSessionSelect(e) {
    selectedSessionId = e.target.value;
    if (selectedSessionId) {
      await loadSession(selectedSessionId);
    }
  }

  let interjectionMarkers = $derived(
    auditLog
      .map((entry, idx) => (entry.event_type === 'interjection_submitted' ? idx : -1))
      .filter((i) => i >= 0)
  );
</script>

<div class="replay-view">
  <h2>{t('replay.title')}</h2>

  <!-- Session selector -->
  <div class="session-selector">
    <label for="replay-session-select">{t('replay.selectSession')}</label>
    <select id="replay-session-select" value={selectedSessionId} onchange={onSessionSelect}>
      <option value="">-- {t('replay.selectSession')} --</option>
      {#each sessions as session}
        <option value={session.id}>{session.id} ({session.status})</option>
      {/each}
    </select>
  </div>

  {#if loading}
    <p class="loading">Loading...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if auditLog.length > 0}
    <!-- Workflow graph (read-only) -->
    <div class="graph-container">
      <WorkflowCanvas
        nodes={[]}
        edges={[]}
        readOnly={true}
        highlightedNodeId={selectedNode?.node_id}
      />
    </div>

    <!-- Replay controls -->
    <ReplayControls
      {currentStep}
      totalSteps={auditLog.length}
      {isPlaying}
      {playSpeed}
      {interjectionMarkers}
      onPlayPause={togglePlayback}
      onStepForward={stepForward}
      onStepBack={stepBack}
      onSliderChange={onSliderChange}
      onSpeedChange={onSpeedChange}
    />

    <!-- Node detail panel -->
    {#if selectedNode}
      <ReplayNodeDetail node={selectedNode} />
    {/if}
  {:else if selectedSessionId}
    <p class="no-data">{t('replay.noData')}</p>
  {/if}
</div>

<style>
  .replay-view {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    height: 100%;
  }
  .session-selector {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .session-selector select {
    min-width: 300px;
    padding: 0.4rem;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  .graph-container {
    flex: 1;
    min-height: 300px;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow: hidden;
  }
  .loading, .error, .no-data {
    padding: 2rem;
    text-align: center;
  }
  .error {
    color: #c00;
  }
</style>
