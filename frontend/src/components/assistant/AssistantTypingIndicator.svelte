<script>
</script>

<!-- DEBUG 2026-06-17: visual marker to identify this component on screen -->
<div data-debug-component="AssistantTypingIndicator" class="px-1 py-0.5 mb-1 inline-block rounded bg-pink-600 text-white text-[9px] font-mono font-bold tracking-wider">DBG: AssistantTypingIndicator.svelte</div>
<div class="message assistant">
  <div class="message-content">
    <div class="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  </div>
</div>

<style>
  .message {
    display: flex;
    flex-direction: column;
    max-width: 80%;
  }

  .message.assistant {
    align-self: flex-start;
  }

  .message-content {
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.5;
  }

  .message.assistant .message-content {
    background: #f3f4f6;
    color: #1f2937;
    border-bottom-left-radius: 4px;
  }

  .typing-indicator {
    display: flex;
    gap: 4px;
    padding: 4px 0;
  }

  .typing-indicator span {
    width: 6px;
    height: 6px;
    background: #9ca3af;
    border-radius: 50%;
    animation: typing 1.4s infinite;
  }

  .typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
  }

  .typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes typing {
    0%, 60%, 100% {
      transform: translateY(0);
      opacity: 40%;
    }
    30% {
      transform: translateY(-6px);
      opacity: 100%;
    }
  }

  :global(.dark) .message.assistant .message-content {
    background: #374151;
    color: #e5e7eb;
  }

  :global(.dark) .typing-indicator span {
    background: #6b7280;
  }
</style>
