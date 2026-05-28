<script>
  let {
    value = $bindable(''),
    disabled = false,
    placeholder = '',
    onSend = () => {},
  } = $props();

  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  }
</script>

<div class="input-area">
  <textarea
    bind:value
    onkeydown={handleKeydown}
    {placeholder}
    rows="1"
    {disabled}
  ></textarea>
  <button
    class="btn-send"
    onclick={onSend}
    disabled={!value.trim() || disabled}
  >
    ➤
  </button>
</div>

<style>
  .input-area {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid #e5e7eb;
    background: white;
  }

  .input-area textarea {
    flex: 1;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
    resize: none;
    outline: none;
    font-family: inherit;
    max-height: 100px;
    overflow-y: auto;
  }

  .input-area textarea:focus {
    border-color: #667eea;
    box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
  }

  .input-area textarea:disabled {
    background: #f9fafb;
    cursor: not-allowed;
  }

  .btn-send {
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    width: 40px;
    height: 40px;
    cursor: pointer;
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
  }

  .btn-send:hover:not(:disabled) {
    background: #5568d3;
  }

  .btn-send:disabled {
    background: #e5e7eb;
    cursor: not-allowed;
  }

  :global(.dark) .input-area {
    background: #1f2937;
    border-top-color: #4b5563;
  }

  :global(.dark) .input-area textarea {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.dark) .input-area textarea:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }

  :global(.dark) .input-area textarea:disabled {
    background: #1f2937;
  }

  :global(.dark) .btn-send:disabled {
    background: #4b5563;
  }
</style>
