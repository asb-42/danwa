<script>
  import { i18n } from '../../lib/i18n/index.js';

  export let currentStep = 0;
  export let totalSteps = 0;
  export let isPlaying = false;
  export let playSpeed = 1;
  export let interjectionMarkers = [];
  export let onPlayPause;
  export let onStepForward;
  export let onStepBack;
  export let onSliderChange;
  export let onSpeedChange;

  $: _ = $i18n;
  $: timestamp = ''; // would be computed from audit log entry
</script>

<div class="replay-controls">
  <!-- Playback buttons -->
  <div class="playback-buttons">
    <button class="btn" on:click={onStepBack} disabled={currentStep === 0}>
      ⏮ {_.replay?.stepBack || 'Back'}
    </button>
    <button class="btn btn-primary" on:click={onPlayPause}>
      {isPlaying ? '⏸ ' + (_.replay?.pause || 'Pause') : '▶ ' + (_.replay?.play || 'Play')}
    </button>
    <button class="btn" on:click={onStepForward} disabled={currentStep >= totalSteps - 1}>
      ⏭ {_.replay?.stepForward || 'Forward'}
    </button>
  </div>

  <!-- Time slider -->
  <div class="slider-container">
    <input
      type="range"
      min="0"
      max={Math.max(totalSteps - 1, 0)}
      value={currentStep}
      on:input={onSliderChange}
      class="time-slider"
    />
    {#if interjectionMarkers.length > 0}
      <div class="interjection-markers">
        {#each interjectionMarkers as marker}
          <div
            class="marker"
            style="left: {(marker / Math.max(totalSteps - 1, 1)) * 100}%"
            title={_.replay?.interjectionMarker || 'Interjection'}
          ></div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Speed selector + counter -->
  <div class="controls-row">
    <label>
      {_.replay?.speed || 'Speed:'}
      <select value={playSpeed} on:change={onSpeedChange}>
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
