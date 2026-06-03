<script>
  /**
   * STT Microphone Button — starts/stops audio recording for speech-to-text.
   *
   * @type {{ onPartial: (text: string) => void, onFinal: (text: string) => void, disabled: boolean }}
   */
  let { onPartial, onFinal, disabled = false } = $props();

  let recording = $state(false);
  let error = $state('');

  import { startRecording, stopRecording } from '../../lib/input/sttStream.js';

  async function toggle() {
    error = '';
    if (recording) {
      stopRecording();
      recording = false;
    } else {
      try {
        recording = await startRecording(
          onPartial || (() => {}),
          () => { recording = false; if (onFinal) onFinal(''); }
        );
      } catch (e) {
        error = e.message || 'Microphone access denied';
        recording = false;
      }
    }
  }
</script>

<div class="stt-mic-wrapper inline-flex items-center gap-2">
  <button
    type="button"
    onclick={toggle}
    {disabled}
    class="mic-button flex items-center justify-center w-10 h-10 rounded-full transition-all
      {recording
        ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-300'
        : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-300 disabled:hover:bg-gray-200 dark:hover:bg-gray-600 disabled:hover:bg-gray-500'}
      disabled:opacity-50 disabled:cursor-not-allowed"
    title={recording ? 'Stop recording' : 'Start recording'}
  >
    {recording ? '⏹' : '🎤'}
  </button>
  {#if error}
    <span class="text-xs text-red-500">{error}</span>
  {/if}
</div>
