/**
 * STT Streaming — MediaRecorder + SSE connection management.
 */

let mediaRecorder = null;
let audioStream = null;
let eventSource = null;

export function isRecording() {
  return mediaRecorder !== null && mediaRecorder.state === 'recording';
}

export async function startRecording(onPartial, onFinal) {
  audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm;codecs=opus' });

  mediaRecorder.ondataavailable = async (e) => {
    if (e.data.size > 0) {
      const formData = new FormData();
      formData.append('audio', e.data);
      try {
        const res = await fetch('/api/v1/input/stt/stream', {
          method: 'POST',
          body: formData,
        });
        if (res.ok) {
          const data = await res.json();
          if (data.text) onPartial(data.text);
        }
      } catch { /* ignore */ }
    }
  };

  mediaRecorder.onstop = () => {
    if (audioStream) {
      audioStream.getTracks().forEach(t => t.stop());
      audioStream = null;
    }
    if (onFinal) onFinal();
  };

  mediaRecorder.start(3000); // 3-second chunks
  return true;
}

export function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    mediaRecorder = null;
  }
}
