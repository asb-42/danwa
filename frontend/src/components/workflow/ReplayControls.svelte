<script>
  import { tStore } from '../../lib/i18n/index.js';

  let {
    currentStep = 0,
    totalSteps = 0,
    isPlaying = false,
    playSpeed = 1,
    interjectionMarkers = [],
    onPlayPause = () => {},
    onStepForward = () => {},
    onStepBack = () => {},
    onSliderChange = () => {},
    onSpeedChange = () => {},
  } = $props();

  let t = $derived($tStore);
  let timestamp = $derived(''); // would be computed from audit log entry
</script>

<div class="replay-controls">
  <!-- Playback buttons -->
  <div class="playback-buttons">
    <button class="btn" click={onStepBack} disabled={currentStep === 0}>
      ⏮ {t('replay.stepBack')}
    </button>
    <button class="btn btn-primary" click={onPlayPause}>
      {isPlaying ? '⏸ ' + t('replay.pause') : '▶ ' + t('replay.play')}
    </button>
    <button class="btn" click={onStepForward} disabled={currentStep >= totalSteps - 1}>
      ⏭ {t('replay.stepForward')}
    </button>
  </div>

  <!-- Time slider -->
  <div class="slider-container">
    <input
      type="range"
      min="0"
      max={Math.max(totalSteps - 1, 0)}
      value={currentStep}
      input={onSliderChange}
      class="time-slider"
    />
    {#if interjectionMarkers.length > 0}
      <div class="interjection-markers">
        {#each interjectionMarkers as marker}
          <div
            class="marker"
            style="left: {(marker / Math.max(totalSteps - 1, 1)) * 100}%"
            title={t('replay.interjectionMarker')}
          ></div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Speed selector + counter -->
  <div class="controls-row">
    <label>
      {t('replay.speed')}
      <select value={playSpeed} change={onSpeedChange}>
        <option value="0.5">0.5x</option>
        <option value="1">1x</option>
        <option value="2">2x</option>
        <option value="4">4x</option>
      </select>
    </label>
    <span class="counter">
      {currentStep + 1} / {totalSteps}
    </span>
  </div>
</div>

<style>
  .replay-controls {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem;
    background: #f8f9fa;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
  }
  .playback-buttons {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
  }
  .btn {
    padding: 0.4rem 0.8rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
    cursor: pointer;
  }
  .btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .btn-primary {
    background: #007bff;
    color: white;
    border-color: #007bff;
  }
  .slider-container {
    position: relative;
  }
  .time-slider {
    width: 100%;
  }
  .interjection-markers {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 100%;
    pointer-events: none;
  }
  .marker {
    position: absolute;
    top: -4px;
    width: 2px;
    height: 12px;
    background: #e91e63;
    border-radius: 1px;
  }
  .controls-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .counter {
    font-size: 0.85rem;
    color: #666;
  }
</style>
